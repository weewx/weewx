#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate JSON time series, for a page that draws its own charts.

This generator is the data-only counterpart to `weewx.imagegenerator`. It reads the same
plot definitions, fetches the same series through `weewx.xtypes.get_series()`, applies the
same unit conversion and label lookup, then writes the result as JSON instead of rendering
it into a PNG.

The syntax is the ImageGenerator's, so a plot already defined for a PNG is available as
JSON without any change to the configuration.

"The page", throughout this module, means whatever reads these files and draws the chart.
For the skin that ships with WeeWX that is JavaScript running in the reader's browser.

Configuration

  By default the generator reads section `[ImageGenerator]`, so an existing skin needs no
  new configuration at all. Add it to a skin like this:

    [Generators]
        generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.jsongenerator.JSONGenerator

  Options, all optional, and all honouring the usual inheritance down the section tree:

    source          = ImageGenerator   # which section holds the plot definitions
    json_dest_dir   = data             # subdirectory of HTML_ROOT to write into
    round           = 3                # decimal places; None to keep full precision
    json_indent     = None             # passed to json.dump(); 2 for readable output
    include_daynight = true            # emit sunrise/sunset transitions for shading

The output for a plot named 'daytempdew' lands in `<HTML_ROOT>/<json_dest_dir>/daytempdew.json`
and looks like this:

    {
      "name": "daytempdew",
      "generated": 1755950000,
      "start": 1755863600, "stop": 1755950000,
      "aggregate_interval": null,
      "unit": "degree_C", "unit_label": " °C",
      "daynight": {"first": "night", "transitions": [...]},
      "series": [
        {"obs_type": "outTemp", "label": "Outside Temperature", "plot_type": "line",
         "color": "#4282b4", "time": [...], "values": [...]}
      ]
    }

Times and values are written as two arrays of the same length rather than as a list of
pairs. That is about 30% smaller, and it is the shape charting libraries take.
"""

import calendar
import datetime
import json
import logging
import os
import time

import weeplot.utilities
import weeutil.logger
import weeutil.weeutil
import weedb
import weewx.accum
import weewx.reportengine
import weewx.units
import weewx.xtypes
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_bool, to_int, TimeSpan
# The ImageGenerator's helpers, used rather than copied, so that a fix to "is this plot
# empty?" reaches both generators.
from weewx.imagegenerator import _get_check_domain, _skip_if_empty, _skip_this_plot
from weewx.units import ValueTuple

log = logging.getLogger(__name__)


class JSONGenerator(weewx.reportengine.ReportGenerator):
    """Generate JSON time series from plot definitions."""

    def run(self):
        self.setup()
        self.gen_json(self.gen_ts)
        self.gen_archive(self.gen_ts)

    def setup(self):
        # ReportGenerator gained stop_event in v5.5.0. Earlier versions do not set
        # it, and this generator runs under them as an extension.
        if not hasattr(self, 'stop_event'):
            self.stop_event = None

        # Generic labels, such as "Outside Temperature":
        try:
            self.generic_dict = self.skin_dict['Labels']['Generic']
        except KeyError:
            self.generic_dict = {}
        # Translated text strings:
        self.text_dict = self.skin_dict.get('Texts', {})

        # An empty section, not an empty dict: search_up() climbs the tree through
        # .parent, which a plain dict does not have.
        if 'JSONGenerator' not in self.skin_dict:
            self.skin_dict['JSONGenerator'] = {}
        self.gen_dict = self.skin_dict['JSONGenerator']

        # Where the plot definitions are. This section, when the skin puts them
        # here, which is what a skin drawing only charts does. Otherwise
        # [ImageGenerator], so that a skin drawing both defines each plot once and
        # a skin written before this generator existed needs no new configuration.
        self.plot_dict = {}
        for name in ('JSONGenerator', 'ImageGenerator'):
            section = self.skin_dict.get(name)
            if section is not None and _holds_plots(section):
                self.plot_dict = section
                break
        else:
            log.error("No plot definitions found, in [JSONGenerator] or "
                      "[ImageGenerator]. JSON generation skipped.")

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

    def gen_json(self, gen_ts):
        """Walk the plot definitions and write one JSON file per plot.

        One file per plot per time span, holding every reading in it. These follow the
        ImageGenerator's plot definitions, so they cover whatever the PNGs cover: the
        last day, week, month and year, each ending now.

        A skin whose archive covers the same spans does not need them, and says so
        with 'periods = false'.

        Args:
            gen_ts (int | None): The time the report is being run for.
        """
        t1 = time.time()
        ngen = 0

        if not self.plot_dict:
            return
        # 'periods = false' turns off the data files, not the manifest. The manifest
        # says what the skin is: which spans it offers and how long each one is, which
        # units its readings can be shown in, whether there are PNGs to link to. A
        # page needs all of that whatever it draws the readings from.
        write_periods = to_bool(self.gen_dict.get('periods', True))

        log_success = to_bool(search_up(self.gen_dict, 'log_success', True))

        # Where to write. Default to a 'data' subdirectory so JSON does not litter the
        # top level next to the HTML.
        dest_dir = self.gen_dict.get('json_dest_dir', 'data')
        indent = to_int(self.gen_dict.get('json_indent'))

        # One entry per plot written. At the end of this method they go into
        # 'index.json', with each plot's title, units and observation types. The page
        # reads it first and lays out its charts from that, rather than requesting
        # each plot to find out whether it is there. A station without a UV sensor
        # has no UV plot, and nothing asks for the file.
        manifest = []
        manifest_root = None
        nskipped = 0
        # How many seconds each time span covers, from 'time_length' in the plot
        # definitions: 86400 for [[day_images]], and so on. It goes into index.json
        # because the page draws the x axis itself, and this is the only statement of
        # how wide a "day" plot is meant to be.
        span_lengths = {}
        # Observation types the skin plots, gathered from the definitions when there
        # are no files to read them off.
        described = set()

        # Last run's index.json. A plot skipped as unchanged still belongs in the new
        # index. Its entry is copied from here, rather than rebuilt by opening the
        # file it describes.
        previous = {}
        try:
            prev_path = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     search_up(self.skin_dict, 'HTML_ROOT', 'public_html'),
                                     dest_dir, 'index.json')
            with open(prev_path, encoding='utf-8') as fd:
                for entry in json.load(fd).get('plots', []):
                    previous[entry['name']] = entry
        except (OSError, ValueError, KeyError):
            pass

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.plot_dict.sections:

            # Loop over all plot names in this time span class:
            for plotname in self.plot_dict[timespan].sections:

                if self.stop_event and self.stop_event.is_set():
                    log.debug("Stop event set. Stopping JSON for plot '%s'", plotname)
                    return

                plot_options = accumulateLeaves(self.plot_dict[timespan][plotname])

                plotgen_ts = gen_ts
                if not plotgen_ts:
                    db_manager = self.db_binder.get_manager(plot_options['data_binding'])
                    plotgen_ts = db_manager.lastGoodStamp() or time.time()

                json_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                         plot_options['HTML_ROOT'],
                                         dest_dir)
                json_file = os.path.join(json_root, '%s.json' % plotname)

                if not write_periods:
                    # No data file, but the manifest still has to describe the skin.
                    # The span's length is where the page gets how wide a "week" is,
                    # and the observation types are what the unit switch is built
                    # from. Both come from the definitions, not from any reading.
                    manifest_root = json_root
                    span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                        plot_options.get('time_length', 86400)))
                    for line_name in self.plot_dict[timespan][plotname].sections:
                        line_options = accumulateLeaves(
                            self.plot_dict[timespan][plotname][line_name])
                        described.add(line_options.get('data_type', line_name))
                    continue

                # An aggregated plot only changes when its aggregation interval
                # rolls over: a year plot of daily averages says the same thing at
                # 10:05 as it did at 10:00. Rewriting it costs a database read, and
                # on a station publishing over FTP, an upload every cycle. This is
                # the test the ImageGenerator applies to its PNGs.
                if _skip_this_plot(plotgen_ts, plot_options, json_file) \
                        and plotname in previous:
                    nskipped += 1
                    # Still advertise it: the file is there, just unchanged.
                    manifest.append(previous[plotname])
                    manifest_root = json_root
                    span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                        plot_options.get('time_length', 86400)))
                    continue

                payload = self.gen_plot_data(plotgen_ts,
                                             plot_options,
                                             self.plot_dict[timespan][plotname],
                                             plotname)

                # 'payload' is None if skip_if_empty was truthy and nothing had data.
                if payload is None:
                    continue

                try:
                    _write_json(json_file, payload, indent)
                    ngen += 1
                    manifest_root = json_root
                    manifest.append({
                        'name': plotname,
                        'group': timespan,
                        'title': ', '.join(s['label'] for s in payload['series']),
                        'unit': payload['unit'],
                        'unit_label': payload['unit_label'],
                        'obs_types': [s['obs_type'] for s in payload['series']],
                    })
                    span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                        plot_options.get('time_length', 86400)))
                except OSError as e:
                    log.error("Unable to save to file '%s': %s", json_file, e)

        # index.json: the list described at the top of this method.
        if manifest_root:
            index_file = os.path.join(manifest_root, 'index.json')
            obs_types = set(described)
            units_seen = set()
            for entry in manifest:
                obs_types.update(entry.get('obs_types') or [])
                if entry.get('unit'):
                    units_seen.add(entry['unit'])
            # Without files there is nothing to read a unit off, so ask the converter
            # what these readings would have been written in.
            for obs in described:
                try:
                    unit = self.converter.getTargetUnit(obs)[0]
                except (KeyError, TypeError, weewx.UnknownType):
                    continue
                if unit:
                    units_seen.add(unit)
            try:
                _write_json(index_file,
                            {'generated': int(gen_ts or time.time()),
                             'spans': span_lengths,
                             # Whether the PNGs of these plots are being written at
                             # all. A page that offers a link to the PNG has to know
                             # before it points at a file nobody writes.
                             'images': self._images_are_generated(),
                             # What it takes to show these readings in another unit.
                             # The files hold one unit each, whichever the skin asked
                             # for, so without this a page cannot offer a second.
                             'units': _unit_choices(obs_types, units_seen,
                                                    self.formatter, self.converter),
                             'plots': manifest},
                            indent)
            except OSError as e:
                log.error("Unable to save to file '%s': %s", index_file, e)

        t2 = time.time()
        if log_success:
            log.info("Generated %d JSON files (%d unchanged) for report %s in %.2f seconds",
                     ngen, nskipped, self.skin_dict['REPORT_NAME'], t2 - t1)

    def gen_archive(self, gen_ts):
        """Write the whole record, one file per plot group and calendar year.

        Where gen_json() writes four windows each ending now, this covers the whole
        database. A year that has ended never changes, so its file is written once and
        skipped from then on, and a page fetches only the years it is showing. See "The
        JSON generator" in the Customization Guide for the format and the cost.

        A file is rewritten when its newest reading moves into the next slot, not when
        it reaches a given age. The two agree while the station is running. They differ
        after a catch-up import, where the file is minutes old and hours behind, and an
        age test would find nothing to do.

        Rewriting is not recalculating. The file on disk holds every slot but its last,
        so only the slots from there on are worked out: the month in progress at
        five-minute spacing is 8640 slots, and the next report adds one. Once a day
        `rebuild` does the whole span anyway, which picks up anything that changed
        further back than the last report. See _rebuild_due().

        Args:
            gen_ts (int | None): The time the report is being run for.
        """
        arch_dict = self.gen_dict.get('Archive', {})
        if not to_bool(arch_dict.get('enable', False)):
            return

        t1 = time.time()

        source_group = arch_dict.get('source_group', 'day_images')
        strip_prefix = arch_dict.get('strip_prefix', 'day')
        aggregate_type = arch_dict.get('aggregate_type', 'avg')
        max_days = to_int(arch_dict.get('max_days', 0))

        # The coarsest of the three tiers: one file per calendar year. Reading a year
        # by the hour is worth having while it is the year people look at. Reading
        # 2016 that way is 8760 points nobody asked for. So the recent years get
        # 'resolution', and everything older gets 'coarse_resolution'.
        resolution = to_int(weeutil.weeutil.nominal_spans(arch_dict.get('resolution', 3600)))
        coarse_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('coarse_resolution', resolution)))
        recent_years = to_int(arch_dict.get('recent_years', 0))

        # The middle tier: one file per calendar month, for stepping back through
        # single days. An hourly grid flattens a day, and a day is what the range bar
        # offers.
        fine_months = to_int(arch_dict.get('fine_months', 0))
        fine_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('fine_resolution', 900)))
        if fine_months and fine_resolution >= resolution:
            # An easy mistake: in a duration suffix 'm' means months, not minutes, so
            # '5m' asks for readings five months apart.
            log.warning("Ignoring fine_months: fine_resolution (%d seconds) is not "
                        "finer than resolution (%d seconds)",
                        fine_resolution, resolution)
            fine_months = 0
        if coarse_resolution < resolution:
            log.warning("coarse_resolution (%d seconds) is finer than resolution "
                        "(%d seconds). Using resolution for both.",
                        coarse_resolution, resolution)
            coarse_resolution = resolution

        # The finest tier: the station's own readings, one file per day. This is what
        # the day view is drawn from, so it is as fine as the record itself. A
        # 'raw_resolution' of 0 means the archive interval, whatever the hardware
        # turned out to be using.
        raw_days = to_int(arch_dict.get('raw_days', 0))
        raw_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('raw_resolution', 0)))

        # How long to spend on the coarse tiers before leaving the rest for the next
        # report. Building years of history in one go is a report that runs for
        # minutes and delays the one behind it. The index knows what is missing, so
        # stopping early costs nothing but time. 0 does the lot in one run.
        budget = to_int(weeutil.weeutil.nominal_spans(arch_dict.get('budget', 0)))

        # Some types need more than an average. A gust is the whole point of a wind
        # series, and averaging it into a four hour slot turns a storm into a breeze,
        # so the types named here carry their lowest and highest reading in each slot
        # as well. Each name costs another query per slot, which is why they have to
        # be asked for rather than done for everything.
        extrema = set(weeutil.weeutil.option_as_list(
            arch_dict.get('extremes', [])) or [])
        dest_dir = arch_dict.get('dest_dir',
                                 os.path.join(self.gen_dict.get('json_dest_dir', 'data'),
                                              'archive'))
        indent = to_int(self.gen_dict.get('json_indent'))
        rounding = to_int(arch_dict.get('round', self.gen_dict.get('round', 2)))
        # How often a file is built from the whole database again rather than carried
        # forward from the one on disk. See _rebuild_due().
        rebuild_after = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('rebuild', '1d')))

        try:
            group_dict = self.plot_dict[source_group]
        except KeyError:
            log.error("Archive: no section [%s]. Skipped.", source_group)
            return

        # Kept in a dict because write_tier() below adds to them, and a closure that
        # rebinds a name needs 'nonlocal' for each one.
        counters = {'written': 0, 'skipped': 0, 'extended': 0, 'deferred': 0,
                    'spent': 0.0, 'slots': 0, 'root': None,
                    'first': None, 'last': None, 'daynight': False}
        index = {}

        # What already exists, from the index the last run left behind. One file, read
        # once, the way gen_json() reads its own index.
        known = self._read_archive_index(dest_dir)
        self._reconcile_index(known, os.path.join(
            self.config_dict['WEEWX_ROOT'],
            search_up(self.skin_dict, 'HTML_ROOT', 'public_html'), dest_dir))
        previous_first = known['first']
        now_ts = int(gen_ts or time.time())
        rebuilding = _rebuild_due(known['rebuilt'], now_ts, rebuild_after)

        def write_index():
            """Publish what exists so far.

            Called after each pass. The page reads this to find out which files are
            there, so a file the index does not name might as well not have been
            written.
            """
            groups = []
            for name in sorted(index):
                entry = index[name]
                if not any(entry[kind] for kind, _ in TIERS):
                    # This group has no file in any tier. There is nothing the page
                    # could draw, and naming it would only send the reader after a 404.
                    continue
                group = {
                    'name': name,
                    'title': entry['title'] or name,
                    'unit_label': entry['unit_label'] or '',
                    'years': sorted(entry['covered']),
                }
                for kind, grids in TIERS:
                    # JSON has no integer keys, so a year is written as a string and
                    # read back as one. The grid goes per file: files written years
                    # apart, or under different settings, are not all on the same one.
                    group[kind] = {str(s): c for s, c in entry[kind].items()}
                    group[grids] = {str(s): g for s, g in entry[grids].items()}
                groups.append(group)
            try:
                _write_json(os.path.join(counters['root'], 'index.json'),
                            # 'interval' and 'fine_interval' are what a file is written
                            # at now. They are the fallback for a reader that does not
                            # know about the per file grids above.
                            {'interval': resolution,
                             'fine_interval': fine_resolution if fine_months else None,
                             'first': counters['first'],
                             'last': counters['last'],
                             # Records when the files last came from the database in
                             # full. The next run reads it to decide whether it may
                             # extend them.
                             'rebuilt': now_ts if rebuilding else known['rebuilt'],
                             'groups': groups},
                            indent)
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        # Two passes over the groups: the day tier for all of them, then the rest,
        # with the index written in between. One pass would leave the day view
        # invisible until the last year of history had been worked out.
        for pass_name in ('raw', 'rest'):
          for plotname in group_dict.sections:
            if self.stop_event and self.stop_event.is_set():
                return

            plot_options = accumulateLeaves(group_dict[plotname])
            db_manager = self.db_binder.get_manager(plot_options['data_binding'])

            db_first = db_manager.firstGoodStamp()
            last_ts = gen_ts or db_manager.lastGoodStamp()
            if not db_first or not last_ts:
                continue
            first_ts = max(db_first, last_ts - max_days * 86400) if max_days else db_first

            # The database now reaches further back than it did last run, which means
            # somebody imported history. Every year has to be built again. The test
            # cannot use 'first_ts': under 'max_days' that moves forward on its own as
            # the record grows, and would report an import every day.
            reimported = previous_first is not None and int(db_first) < previous_first

            # The span covered comes from the database, not from the files rewritten
            # this run. On a second run in the same minute, no file is rewritten.
            if counters['first'] is None or first_ts < counters['first']:
                counters['first'] = int(first_ts)
            if counters['last'] is None or last_ts > counters['last']:
                counters['last'] = int(last_ts)

            group_name = plotname[len(strip_prefix):] \
                if strip_prefix and plotname.startswith(strip_prefix) else plotname

            arch_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     plot_options['HTML_ROOT'], dest_dir)

            this_year = time.localtime(int(last_ts)).tm_year

            def write_tier(spans, kind, grids, stamp_of, name_of, grid_of, tier_from,
                           metered=True):
                """Write one tier's files for this group.

                The three tiers differ in how the record is cut into files, which
                grid each goes on, and what the index calls them. When to skip, what
                to carry forward and what to record are the same for all of them.

                'metered' tiers are held to the budget. The raw tier is not one:
                it is cheap, and it is what the day view is drawn from, so a report
                that deferred it would leave the page without today.

                Newest span first, so that a run giving up partway leaves the far end
                of the record unbuilt rather than this year.

                Args:
                    spans (Iterable[weeutil.weeutil.TimeSpan]): The spans to write,
                        one file each.
                    kind (str): Which tier, as the index names it.
                    grids (str): The index key holding the grid each file was written on.
                    stamp_of (Callable[[weeutil.weeutil.TimeSpan], int | str]): Called
                        as ``stamp_of(span)``. Returns the index stamp for a span.
                    name_of (Callable[[int | str], str]): Called as ``name_of(stamp)``.
                        Returns the JSON file name for a stamp.
                    grid_of (Callable[[int | str, int | None], int]): Called as
                        ``grid_of(stamp, existing)``. Returns the grid, in seconds, for
                        a stamp. ``existing`` is the grid recorded for that stamp in the
                        previous index, or None if there is none.
                    tier_from (int): The oldest instant this tier reaches.
                    metered (bool): Whether the budget applies. The raw tier is not
                        metered.
                """
                for span in reversed(list(spans)):
                    afford = _affordable(budget, counters) if metered else None
                    if afford == 0:
                        counters['deferred'] += 1
                        continue
                    stamp = stamp_of(span)
                    out_file = os.path.join(arch_root, name_of(stamp))
                    grid = grid_of(stamp, known[grids].get(group_name, {}).get(stamp))
                    entry = index.setdefault(group_name, _new_entry())

                    # The newest reading this file holds. For a span that has ended it
                    # is the last instant of it and never moves again, so the file is
                    # written once. For the one in progress it advances with the
                    # database, and the file is rewritten once it reaches the next slot.
                    covered = min(int(span.stop), int(last_ts))
                    was = known[kind].get(group_name, {}).get(stamp)
                    if os.path.exists(out_file) and was is not None and not reimported \
                            and was // grid == covered // grid:
                        counters['skipped'] += 1
                        entry[kind][stamp] = was
                        entry[grids][stamp] = grid
                        counters['root'] = arch_root
                        continue

                    # Everything before the last slot the file holds is already worked
                    # out. Handing it over means only the slots since the last report
                    # get calculated, instead of every slot in the span.
                    carry = None if rebuilding or reimported or was is None \
                        else _read_archive_file(out_file)
                    if carry is not None:
                        counters['extended'] += 1

                    started = time.time()
                    before = carry['count'] if carry else 0
                    payload = self._archive_span(
                        group_dict[plotname], plot_options, span, grid, aggregate_type,
                        rounding, group_name, tier_from, last_ts, carry, afford,
                        extrema)
                    counters['spent'] += time.time() - started
                    if payload is None:
                        continue
                    # What a slot costs, so the next file can be sized to the budget
                    # that is left. Measured rather than assumed: it is a database
                    # query per slot, and databases differ.
                    counters['slots'] += max(0, payload['count'] - before)
                    try:
                        _write_json(out_file, payload, indent)
                        counters['written'] += 1
                        counters['root'] = arch_root
                        entry[kind][stamp] = payload['covered']
                        entry[grids][stamp] = grid
                        entry['title'] = ', '.join(s['label'] for s in payload['series'])
                        entry['unit_label'] = payload['unit_label']
                    except OSError as e:
                        log.error("Unable to save to file '%s': %s", out_file, e)

            # Finest first. A station building its history for the first time has the
            # day view within a second or two, and fills in the years behind it over
            # the reports that follow.
            if raw_days and pass_name == 'raw':
                # The raw tier: one file per day, for the day view and for stepping
                # back through days. This is the one tier whose files are not kept
                # forever. A day at a minute apiece is a lot of small files, and
                # nobody steps back a year one day at a time.
                grid = raw_resolution or _archive_interval(db_manager, last_ts)
                raw_from = max(int(first_ts),
                               weeutil.weeutil.startOfDay(int(last_ts))
                               - (raw_days - 1) * 86400)
                write_tier(
                    weeutil.weeutil.genDaySpans(raw_from, last_ts), 'raw',
                    'raw_intervals',
                    lambda span: time.strftime('%Y-%m-%d', time.localtime(span.start)),
                    lambda stamp: '%s-raw-%s.json' % (group_name, stamp),
                    lambda stamp, existing: grid,
                    raw_from, metered=False)
                _drop_stale_raw(arch_root, group_name,
                                set(index.get(group_name, {}).get('raw', {})))

            if fine_months and pass_name == 'rest':
                fine_from = _months_back(int(last_ts), fine_months, int(first_ts))
                write_tier(
                    weeutil.weeutil.genMonthSpans(fine_from, last_ts),
                    'fine', 'fine_intervals',
                    lambda span: time.strftime('%Y-%m', time.localtime(span.start)),
                    lambda stamp: '%s-fine-%s.json' % (group_name, stamp),
                    lambda stamp, existing: fine_resolution,
                    fine_from)

            if pass_name == 'rest':
              write_tier(
                weeutil.weeutil.genYearSpans(first_ts, last_ts), 'covered', 'intervals',
                lambda span: time.localtime(span.start).tm_year,
                lambda year: '%s-%d.json' % (group_name, year),
                # The recent years are the ones people read closely. A file already
                # finer than the answer keeps what it has: coarsening it would mean
                # working out a whole year to end up with less than is on disk.
                lambda year, existing: _year_grid(year, this_year, recent_years,
                                                  resolution, coarse_resolution,
                                                  existing),
                first_ts)

            _carry_over_index(index, known, group_name)
            if index.get(group_name) \
                    and any(index[group_name][kind] for kind, _ in TIERS):
                counters['root'] = arch_root

          # Sunrise and sunset go with the first index, so the shading is there as
          # soon as the charts are. They depend on the location alone, so one file per
          # year serves every group.
          if counters['root']:
              # Once, at the first pass that has anything to show. The shading is
              # then there as soon as the charts are, and a run where the day tier
              # is off still gets it.
              if not counters['daynight'] and to_bool(arch_dict.get(
                      'include_daynight', self.gen_dict.get('include_daynight', True))):
                  counters['daynight'] = True
                  self._archive_daynight(counters['root'], counters['first'],
                                         counters['last'], indent)
              write_index()

        if to_bool(search_up(self.gen_dict, 'log_success', True)):
            log.info("Generated %d archive files (%d extended, %d already current) "
                     "for report %s in %.2f seconds",
                     counters['written'], counters['extended'], counters['skipped'],
                     self.skin_dict['REPORT_NAME'], time.time() - t1)

    def _images_are_generated(self):
        """Is the ImageGenerator in this report's generator list?

        [Generators] is where the skin says whether it draws PNGs. Reading the
        answer from there, rather than from a second option that says the same
        thing, means there is nothing that can disagree with it.
        """
        try:
            generators = self.skin_dict['Generators']['generator_list']
        except (KeyError, TypeError):
            return False
        # The dots are deliberate: a generator whose name merely holds the word
        # 'image' is not one that writes a PNG per plot.
        return any('.imagegenerator.' in str(g).lower()
                   for g in weeutil.weeutil.option_as_list(generators))

    def _read_archive_index(self, dest_dir):
        """What the previous run left behind, as a record of what already exists.

        This is the archive's memory. A file it names is a file that does not have to
        be worked out again, whatever the current settings say should be written now.

        Args:
            dest_dir (str): The archive directory.

        Returns:
            dict: With keys

                covered:        {group: {year: timestamp}}, the newest reading each
                                year's file holds
                fine:           the same for the closely spaced months, keyed 'YYYY-MM'
                intervals:      {group: {year: seconds}}, the grid each year's file is
                                on. Files written at different times can be on
                                different grids, and a file is never rewritten just to
                                coarsen it.
                fine_intervals: the same for the months
                first:          the oldest reading in the database when the last run
                                read it, or None if there was no index
                rebuilt:        when the files last came from the database in full
        """
        empty = {'first': None, 'rebuilt': None}
        for kind, grids in TIERS:
            empty[kind] = {}
            empty[grids] = {}
        empty['labels'] = {}
        found = {kind: {} for kind, _ in TIERS}
        found.update({grids: {} for _, grids in TIERS})
        found['labels'] = {}
        first = None
        rebuilt = None
        try:
            path = os.path.join(self.config_dict['WEEWX_ROOT'],
                                search_up(self.skin_dict, 'HTML_ROOT', 'public_html'),
                                dest_dir, 'index.json')
            with open(path, encoding='utf-8') as fd:
                index = json.load(fd)
            first = to_int(index.get('first'))
            rebuilt = to_int(index.get('rebuilt'))
            # An index written before the grid could vary per file says so once, at
            # the top. Read it as the grid every file in it is on.
            defaults = {'intervals': to_int(index.get('interval')),
                        'fine_intervals': to_int(index.get('fine_interval')),
                        'raw_intervals': None}
            # Years are numbers, months and days are strings, and JSON has neither as
            # a key. Each tier says which it wants them back as.
            as_key = {'covered': int, 'fine': str, 'raw': str}
            for group in index.get('groups', []):
                name = group['name']
                # A run that does not get to a group still has to be able to name it
                # in the index it writes, and these do not come from the files.
                found['labels'][name] = (group.get('title'), group.get('unit_label'))
                for kind, grids in TIERS:
                    spans = {}
                    for stamp, ts in (group.get(kind) or {}).items():
                        spans[as_key[kind](stamp)] = int(ts)
                    if spans:
                        found[kind][name] = spans
                    seen = {}
                    for stamp, seconds in (group.get(grids) or {}).items():
                        seen[as_key[kind](stamp)] = int(seconds)
                    for stamp in spans:
                        seen.setdefault(stamp, defaults[grids])
                    seen = {s: g for s, g in seen.items() if g}
                    if seen:
                        found[grids][name] = seen
        except (OSError, ValueError, KeyError, TypeError):
            # No index, or one this version cannot read. Report that nothing is
            # current, so everything is rebuilt. That costs a run; the other way
            # round would leave stale files in place.
            return empty
        found['first'] = first
        found['rebuilt'] = rebuilt
        return found

    def _span_extreme(self, var_type, tail, mgr, which, resolution, option_dict,
                      plot_options, unit):
        """One slot's lowest or highest reading, across a span.

        Args:
            var_type (str): The observation type.
            tail (str): Which end is wanted, `min` or `max`.
            mgr (weewx.manager.Manager): The open database.
            which (weeutil.weeutil.TimeSpan): The span to look in.
            resolution (int): The grid, in seconds.
            option_dict (dict[str, Any]): The options of the line being written.
            plot_options (dict[str, Any]): The options of the plot it belongs to.
            unit (str): The unit the readings are wanted in.

        Returns:
            list|None: The values, in the order get_series() gave them, or None if the
                database cannot answer that for this type.
        """
        try:
            _, _, data_vec_t = weewx.xtypes.get_series(
                var_type, tail, mgr, aggregate_type=which,
                aggregate_interval=resolution, **option_dict)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            return None
        if plot_options.get('unit'):
            conv = weewx.units.convert(data_vec_t, plot_options['unit'])
        else:
            conv = self.converter.convert(data_vec_t)
        # A different unit here than in the values it sits beside would be a chart
        # drawn from two scales. Leave it out rather than draw that.
        if unit is not None and conv[1] is not None and conv[1] != unit:
            return None
        return conv[0]

    @staticmethod
    def _reconcile_index(known, arch_root):
        """Make what the index claims agree with what is on disk.

        The index is the fast path; the directory is the truth. A file the index does
        not name is invisible to the page, and an index naming a file that has gone
        sends the reader after a 404. Losing it would otherwise mean working out the
        whole record again, with every answer already sitting in the files.

        Only files the index does not account for are opened, so a run that finds it
        intact pays one listdir.

        Args:
            known (dict[str, dict[str, Any]]): The index as it was read.
            arch_root (str): The directory it names files in.
        """
        try:
            names = os.listdir(arch_root)
        except OSError:
            return

        seen = {kind: set() for kind, _ in TIERS}
        for filename in names:
            if not filename.endswith('.json') or filename == 'index.json' \
                    or filename.startswith('daynight-'):
                continue
            stem = filename[:-len('.json')]
            if '-fine-' in stem:
                group, _, stamp = stem.partition('-fine-')
                kind, key, grids = 'fine', stamp, 'fine_intervals'
            elif '-raw-' in stem:
                group, _, stamp = stem.partition('-raw-')
                kind, key, grids = 'raw', stamp, 'raw_intervals'
            else:
                group, _, tail = stem.rpartition('-')
                if not tail.isdigit():
                    continue
                kind, key, grids = 'covered', int(tail), 'intervals'
            if not group:
                continue
            seen[kind].add((group, key))
            if key in known[kind].get(group, {}):
                continue
            # The index does not know this file. Its own header says what it holds.
            payload = _read_archive_file(os.path.join(arch_root, filename))
            if not payload:
                continue
            covered = to_int(payload.get('covered'))
            interval = to_int(payload.get('interval'))
            if covered is None or not interval:
                continue
            known[kind].setdefault(group, {})[key] = covered
            known[grids].setdefault(group, {})[key] = interval

        # And drop what the index remembers but the directory does not have.
        for kind, grids in TIERS:
            for group in list(known[kind]):
                for key in list(known[kind][group]):
                    if (group, key) not in seen[kind]:
                        known[kind][group].pop(key, None)
                        known[grids].get(group, {}).pop(key, None)

    def _archive_daynight(self, root, first_ts, last_ts, indent):
        """Write sunrise and sunset times, one file per calendar year.

        Sunrise and sunset depend on the station's latitude and longitude and on
        nothing else, so one file serves every plot group. Like the data files, a year
        that has ended is written once and then left alone.

        Args:
            root (str): The archive directory.
            first_ts (int): The oldest reading in the database.
            last_ts (int): The newest reading in it.
            indent (int | None): Indentation for the files.
        """
        if not first_ts or not last_ts:
            return
        try:
            lat = self.stn_info.latitude_f
            lon = self.stn_info.longitude_f
        except AttributeError:
            return

        for year_span in weeutil.weeutil.genYearSpans(first_ts, last_ts):
            year = time.localtime(year_span.start).tm_year
            out_file = os.path.join(root, 'daynight-%d.json' % year)
            if os.path.exists(out_file) and year_span.stop <= last_ts:
                continue
            try:
                dn = _daynight(year_span.start, min(year_span.stop, int(last_ts)), lat, lon)
                if dn is None:
                    continue
                dn['start'] = int(year_span.start)
                _write_json(out_file, dn, indent)
            except Exception as e:
                log.warning("Could not write day/night file for %d: %s", year, e)

    def _archive_span(self, plot_section, plot_options, span, resolution,
                      aggregate_type, rounding, group_name, first_ts, last_ts,
                      previous=None, max_slots=None, extrema=()):
        """Build the contents of one archive file: one plot group, one span.

        The same for all three tiers. A day, a month and a year differ in how long
        they are and how finely they are cut, and in nothing else.

        There are no timestamps in the result: `start` is the first instant,
        `interval` the seconds between readings, `count` how many there are, so
        `values[i]` is at `start + i * interval`. A null is a reading the station did
        not take.

        Args:
            plot_section (dict): The plot's section, holding one subsection per
                line.
            plot_options (dict[str, Any]): The options that apply to it.
            span (weeutil.weeutil.TimeSpan): The span the file covers.
            resolution (int): The grid it is written on, in seconds.
            aggregate_type (str): How readings are combined into a slot.
            rounding (int | None): Decimal places, or None to leave them alone.
            group_name (str): The plot group, which the file is named after.
            first_ts (int): The oldest reading in the database.
            last_ts (int): The newest reading in it.
            previous (dict[str, Any] | None): The file this one replaces, as it was read back
                from disk. Given one it can carry over, only the slots after the newest one it
                holds are calculated, which is the difference between one statement per slot in
                the year and one per slot since the last report. Anything that makes the old
                file unusable, from a changed series list to a changed unit, falls back to
                calculating the whole span.
            max_slots (int | None): At most this many slots may be worked out. The file is
                written short if that is not enough to reach the end of the span, and the next
                run continues from where this one stopped. None does the whole span however long
                it takes.
            extrema (set[str] | tuple[str, ...]): The observation types that also
                carry the lowest and highest reading in each slot, not only the
                aggregate.

        Returns:
            dict|None: The file's contents, or None if the year holds nothing worth
                writing. For a temperature group over an hour-spaced 2025::

                    {'name': 'tempdew', 'start': 1735725600, 'interval': 3600,
                     'count': 8760, 'covered': 1767261599,
                     'unit': 'degree_C', 'unit_label': '°C',
                     'yscale': [-10.0, 35.0, 5.0],
                     'series': [{'obs_type': 'outTemp', 'label': 'Outside Temperature',
                                 'aggregate_type': 'avg', 'color': '#4282b4',
                                 'values': [3.1, 2.8, None, 2.4, ...]}]}
        """
        # Clip to the readings that exist, then move both ends onto a multiple of
        # 'resolution'. Every series of every year then falls on the same instants, and
        # the page can put two years end to end without resampling either.
        lo = max(span.start, int(first_ts))
        hi = min(span.stop, int(last_ts) + resolution)
        start = int(lo // resolution * resolution)
        # Round 'stop' up to the next multiple of 'resolution'. Rounding down and then
        # adding one resolution would give a slot too many whenever 'hi' already sits
        # on a boundary, which it does for every finished day. Nothing could ever fill
        # that slot: the next run finds 'covered' unchanged, skips the file, and the
        # slot stays null for good. That instant belongs to the next file anyway.
        stop = int(-(-hi // resolution) * resolution)
        slots = int((stop - start) / resolution)
        if slots < 2:
            return None

        # Where to pick up from, or None to do the lot.
        resume = _resume_from(previous, start, resolution, slots)

        # Stop short if only so many slots can be afforded. The file is then written
        # holding less than the span it is named for, which is what a file still
        # filling up looks like: 'covered' says how far it got, and the next run
        # carries on from there. A year builds itself over several short reports.
        if max_slots is not None:
            done = resume[1] if resume else 0
            if done + max_slots < slots:
                slots = done + max_slots
                stop = start + slots * resolution
                last_ts = min(int(last_ts), stop - resolution)

        domain = TimeSpan(start, stop)
        tail = TimeSpan(resume[0], stop) if resume else domain

        series_out = []
        unit = unit_label = None
        # The boundary the last slot of this file starts on, and which slot that is.
        # Written into the file so the next run can carry on from exactly here.
        resume_ts = resume_slot = None
        # Set when the file on disk turns out not to match what is being built after
        # all. Only the loop below can see that, so it stops and the whole span is
        # calculated instead.
        stale = False

        for line_name in plot_section.sections:
            line_options = accumulateLeaves(plot_section[line_name])
            var_type = line_options.get('data_type', line_name)
            mgr = self.db_binder.get_manager(line_options['data_binding'])

            if _skip_if_empty(mgr, var_type, domain):
                continue

            # A wind vector is a pair, not a number. It is kept as one: the magnitude
            # goes in 'values' like any other series, and the two components go beside
            # it, which is what the page needs to draw the arrows.
            is_vector = line_options.get('plot_type', 'line').lower() == 'vector'

            # The plot's own aggregate_type wins. 'none' is how a skin asks for raw
            # samples, which cannot be placed at a fixed spacing, so use the default.
            agg = line_options.get('aggregate_type')
            if agg in (None, '', 'None', 'none'):
                agg = aggregate_type
            # Which types are totals rather than levels is already recorded, once, in
            # the accumulator defaults: 'rain', 'ET', 'lightning_strike_count' and
            # 'windrun' all carry 'extractor = sum'. Reading it from there rather than
            # from a list here means a type the station added under [Accumulator] is
            # summed too.
            if weewx.accum.accum_dict.get(var_type, {}).get('extractor') == 'sum':
                agg = 'sum'
            elif var_type in ('windDir', 'windGustDir'):
                # An arithmetic mean of compass bearings says the wrong thing: 350
                # and 10 degrees average to due south, where the wind never blew
                # from. The 'vecdir' aggregate averages the vectors and then takes
                # the bearing. It reads the 'wind' daily summary, so the observation
                # type has to change with the aggregate.
                var_type = 'wind'
                agg = 'vecdir'

            # Find the series this one replaces, matched by position. The order comes
            # from the skin's plot section, so it only moves when the skin does.
            carried = None
            if resume is not None:
                carried = _carried_series(previous, len(series_out), var_type,
                                          previous['count'])
                if carried is None:
                    stale = True
                    break

            # A bar's interval is part of what it says. An hour's rain in one bar,
            # and a sixtieth of it in each of sixty, are different statements under
            # the same label. So a bar asking for a coarser interval than the tier's
            # grid gets it, and its readings sit every nth slot.
            #
            # Only bars. On a line 'aggregate_interval' is a drawing decision rather
            # than a claim about the number, and honouring it would leave the finest
            # grid holding a reading every fifth slot with nothing in between.
            step = resolution
            asked = to_int(weeutil.weeutil.nominal_spans(
                line_options.get('aggregate_interval')))
            if agg and asked and asked > resolution \
                    and line_options.get('plot_type', 'line').lower() == 'bar':
                step = asked

            option_dict = dict(line_options)
            option_dict.pop('aggregate_type', None)
            option_dict.pop('aggregate_interval', None)

            try:
                start_vec_t, stop_vec_t, data_vec_t = weewx.xtypes.get_series(
                    var_type, tail, mgr,
                    aggregate_type=agg,
                    aggregate_interval=step,
                    **option_dict)
            except (weewx.UnknownType, weewx.UnknownAggregation):
                continue

            if plot_options.get('unit'):
                conv = weewx.units.convert(data_vec_t, plot_options['unit'])
            else:
                conv = self.converter.convert(data_vec_t)

            # A span with no readings in it has no unit to report. Letting that
            # overwrite a unit an earlier series established would put a null in the
            # file, and on the extending path it would read as a changed unit and
            # rebuild the whole span every report.
            if conv[1] is not None:
                unit = conv[1]
                unit_label = line_options.get(
                    'y_label', self.formatter.get_label_string(conv[1]))

            if carried is not None:
                if conv[1] is not None and conv[1] != previous.get('unit'):
                    stale = True
                    break
                if unit is None:
                    unit = previous.get('unit')
                    unit_label = previous.get('unit_label')

            # A vector comes back as complex numbers. The page draws the arrows from
            # the components and labels them with the magnitude, so both are kept.
            values, components, bearings = conv[0], None, None
            if is_vector:
                components = _vector_components(conv[0])
                if components:
                    # The speed goes in 'values' like any other series, so a reader
                    # that knows nothing about vectors still has a line. The bearing
                    # is what the legend puts beside it, and the components are what
                    # the arrows are drawn from.
                    values, bearings = _split_vectors(conv[0])

            # Put each value where its timestamp belongs. get_series() returns nothing
            # at all for an interval with no readings, so the position is computed from
            # the timestamp rather than taken from the loop counter.
            def new_grid(carried_values):
                if carried_values is None:
                    return [None] * slots
                # Everything before the resume point stands. From there on the file is
                # rewritten, including slots this run finds nothing for.
                return list(carried_values[:resume[1]]) + [None] * (slots - resume[1])

            def fill(grid, seq):
                for begin, val in zip(start_vec_t[0], seq):
                    if begin is None or val is None:
                        continue
                    # Where the interval began, as get_series() reports it. Counting
                    # back from its end assumes every interval is a whole step long,
                    # which intervalgen() does not promise: it clips the last one to
                    # the end of the span.
                    slot = int((begin - start) // resolution)
                    if 0 <= slot < slots:
                        grid[slot] = round(val, rounding) if rounding is not None else val
                return grid

            grid = fill(new_grid(carried['values'] if carried else None), values)

            # Where this series stopped. Its last aggregation interval was still
            # filling up when it was worked out, so it is where the next run starts.
            # The earliest across the series wins: none of them may be left behind.
            if stop_vec_t[0]:
                last_slot = int((start_vec_t[0][-1] - start) // resolution)
                if resume_ts is None or start_vec_t[0][-1] < resume_ts:
                    resume_ts = int(start_vec_t[0][-1])
                if resume_slot is None or last_slot < resume_slot:
                    resume_slot = max(0, min(last_slot, slots - 1))

            label = line_options.get('label')
            label = self.text_dict.get(label, label) if label \
                else self.generic_dict.get(var_type, var_type)

            entry = {
                'obs_type': var_type,
                'label': label,
                'aggregate_type': agg,
                'values': grid,
            }
            if step != resolution:
                # Its readings sit every nth slot, and a bar of one has to be drawn
                # n slots wide or it is a hairline where an hour was meant.
                entry['aggregate_interval'] = step
            color = line_options.get('color')
            if color:
                entry['color'] = _normalize_color(color)
            if line_options.get('plot_type', 'line').lower() == 'bar':
                entry['plot_type'] = 'bar'

            if components:
                entry['vector_x'] = fill(new_grid(carried and carried.get('vector_x')),
                                         components[0])
                entry['vector_y'] = fill(new_grid(carried and carried.get('vector_y')),
                                         components[1])
                if bearings is not None:
                    entry['directions'] = fill(
                        new_grid(carried and carried.get('directions')), bearings)
                entry['plot_type'] = 'vector'
                rotate = line_options.get('vector_rotate')
                if rotate is not None:
                    entry['vector_rotate'] = -float(rotate)

            # The lowest and highest reading in each slot, for the types named by
            # the 'extremes' option. See where it is read, in gen_archive().
            if var_type in extrema and agg not in ('min', 'max'):
                for which in ('min', 'max'):
                    seq = self._span_extreme(var_type, tail, mgr, which, resolution,
                                             option_dict, plot_options, conv[1])
                    if seq is None:
                        continue
                    entry[which] = fill(
                        new_grid(carried and carried.get(which)), seq)

            series_out.append(entry)

        # A series that has appeared since the file was written leaves the two lists
        # different lengths, and the loop above cannot see that until it has finished.
        if resume is not None and len(series_out) != len(previous['series']):
            stale = True

        if stale:
            # Rare, and worth being able to find: the file on disk was written for a
            # different set of series, or in a different unit, than the one the skin
            # now asks for. It cannot be carried forward, so do the span in full.
            log.debug("Archive file for '%s' does not match the plot it is for. "
                      "Rebuilding it.", group_name)
            return self._archive_span(plot_section, plot_options, span, resolution,
                                      aggregate_type, rounding, group_name, first_ts,
                                      last_ts, extrema=extrema)

        if not series_out:
            return None

        # These are the colours the skin sets for every plot. They apply to any series
        # that names none of its own.
        default_colors = weeutil.weeutil.option_as_list(
            plot_options.get('chart_line_colors', [])) or []
        for i, s in enumerate(series_out):
            if 'color' not in s and default_colors:
                s['color'] = _normalize_color(default_colors[i % len(default_colors)])

        return {
            'name': group_name,
            'start': start,
            'interval': resolution,
            'yscale': _yscale(plot_options, series_out),
            'count': slots,
            # The newest reading in this file. The next run compares it with the
            # database to decide whether the file has to be written again.
            'covered': min(int(span.stop), int(last_ts)),
            # The aggregation boundary the last slot starts on, and the slot it fills.
            # Together they are where the next run carries on from. See _resume_from().
            'resume_ts': resume_ts,
            'resume_slot': resume_slot,
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }

    def gen_plot_data(self, plotgen_ts, plot_options, plot_dict, plotname):
        """Assemble the data for a single plot.

        Mirrors ImageGenerator.gen_plot(), minus everything to do with drawing. Unlike
        _archive_span() above, every reading carries its own timestamp here, because
        the readings are as the station took them and not evenly spaced.

        Args:
            plotgen_ts (int): The time the plot is being drawn for.
            plot_options (dict[str, Any]): The options that apply to it.
            plot_dict (dict): Its section, holding one subsection per line.
            plotname (str): Its name, which the file is named after.

        Returns:
            dict|None: The file's contents, in the shape shown at the top of this
                module. None if no series had data and skip_if_empty was set.
        """
        time_length = weeutil.weeutil.nominal_spans(plot_options.get('time_length', 86400))
        # Move the ends of the span onto round boundaries, using the same function the
        # ImageGenerator calls. Taken unrounded, a "day" starts at whatever minute the
        # last record happened to land on, and the axis labels fall between the hours.
        minstamp, maxstamp, timeinc = weeplot.utilities.scaletime(plotgen_ts - time_length,
                                                                  plotgen_ts)
        x_domain = TimeSpan(int(minstamp), int(maxstamp))

        # Override the tick interval if the user has given an explicit one, exactly as
        # the ImageGenerator does.
        timeinc_user = to_int(weeutil.weeutil.nominal_spans(plot_options.get('x_interval')))
        if timeinc_user is not None:
            timeinc = timeinc_user

        check_domain = _get_check_domain(plot_options.get('skip_if_empty', False), x_domain)

        # Default colors, so the client can inherit the skin's palette instead of
        # inventing its own.
        default_colors = weeutil.weeutil.option_as_list(
            plot_options.get('chart_line_colors', [])) or []
        default_fills = weeutil.weeutil.option_as_list(
            plot_options.get('chart_fill_colors', [])) or []

        rounding = to_int(plot_options.get('round', 3))

        series_out = []
        unit = unit_label = None
        aggregate_interval_out = None

        for idx, line_name in enumerate(plot_dict.sections):

            line_options = accumulateLeaves(plot_dict[line_name])
            var_type = line_options.get('data_type', line_name)

            db_manager = self.db_binder.get_manager(line_options['data_binding'])

            if _skip_if_empty(db_manager, var_type, check_domain):
                continue

            # Look for aggregation type:
            aggregate_type = line_options.get('aggregate_type')
            if aggregate_type in (None, '', 'None', 'none'):
                aggregate_type = aggregate_interval = None
            else:
                try:
                    aggregate_interval = weeutil.weeutil.nominal_spans(
                        line_options['aggregate_interval'])
                except KeyError:
                    log.error("Aggregate interval required for aggregate type %s",
                              aggregate_type)
                    log.error("Line type %s skipped", var_type)
                    continue

            # Pass the remaining line options through to the xtype, exactly as the
            # ImageGenerator does.
            option_dict = dict(line_options)
            option_dict.pop('aggregate_type', None)
            option_dict.pop('aggregate_interval', None)
            option_dict['plotgen_ts'] = plotgen_ts

            try:
                start_vec_t, stop_vec_t, data_vec_t = weewx.xtypes.get_series(
                    var_type,
                    x_domain,
                    db_manager,
                    aggregate_type=aggregate_type,
                    aggregate_interval=aggregate_interval,
                    **option_dict)
            except (weewx.UnknownType, weewx.UnknownAggregation):
                log.debug("Unknown type or aggregation for '%s'. Skipped.", var_type)
                continue

            plot_type = line_options.get('plot_type', 'line').lower()
            if plot_type not in {'line', 'bar', 'vector'}:
                log.error("Unknown plot type '%s'. Ignored", plot_type)
                continue

            # get_series() timestamps an aggregate at the end of its interval. For a
            # line, the point belongs in the middle of the interval it averages, which
            # is where the ImageGenerator puts it.
            if aggregate_type and plot_type != 'bar':
                stop_vec_t = ValueTuple(
                    [x - aggregate_interval / 2.0 for x in stop_vec_t[0]],
                    stop_vec_t[1], stop_vec_t[2])

            # Convert to the requested units:
            if plot_options.get('unit'):
                new_data_vec_t = weewx.units.convert(data_vec_t, plot_options['unit'])
            else:
                new_data_vec_t = self.converter.convert(data_vec_t)

            unit = new_data_vec_t[1]
            unit_label = line_options.get(
                'y_label', self.formatter.get_label_string(new_data_vec_t[1]))

            # Resolve the label, preferring an explicit one, then a translation, then
            # the observation type itself.
            label = line_options.get('label')
            if label:
                label = self.text_dict.get(label, label)
            else:
                label = self.generic_dict.get(var_type, var_type)

            color = line_options.get('color')
            if color is None and default_colors:
                color = default_colors[idx % len(default_colors)]
            fill_color = line_options.get('fill_color')
            if fill_color is None and plot_type == 'bar' and default_fills:
                fill_color = default_fills[idx % len(default_fills)]

            times = [None if t is None else int(t) for t in stop_vec_t[0]]

            # Wind arrives as complex numbers (x + yj). Split each into a speed and a
            # compass bearing, which is what the vector plot draws and what a reader
            # of the JSON can use without knowing WeeWX's internal representation.
            magnitudes, directions = _split_vectors(new_data_vec_t[0])
            values = _round_seq(magnitudes, rounding)
            components = _vector_components(new_data_vec_t[0])

            entry = {
                'obs_type': var_type,
                'label': label,
                'plot_type': plot_type,
                'unit': new_data_vec_t[1],
                'unit_label': (unit_label or '').strip(),
                'time': times,
                'values': values,
            }
            if directions is not None:
                entry['directions'] = _round_seq(directions, 1)
            if color:
                entry['color'] = _normalize_color(color)
            if fill_color:
                entry['fill_color'] = _normalize_color(fill_color)
            if aggregate_type:
                entry['aggregate_type'] = aggregate_type
                entry['aggregate_interval'] = aggregate_interval
                aggregate_interval_out = aggregate_interval
            if plot_type == 'bar':
                # How many seconds each bar spans, so the page can draw it that wide.
                # Bars are not all one width: an aggregate over a month is wider than
                # one over February.
                entry['bar_width'] = [b - a for a, b in zip(start_vec_t[0], stop_vec_t[0])]
            if plot_type == 'vector':
                # A vector plot draws each reading as an arrow from the zero line, so
                # the page needs the two components and not just the speed. Sending
                # them saves it computing them back from speed and bearing.
                if components:
                    entry['vector_x'] = _round_seq(components[0], rounding)
                    entry['vector_y'] = _round_seq(components[1], rounding)
                vr = line_options.get('vector_rotate')
                if vr is not None:
                    # Negated, as the ImageGenerator negates it. The option is written
                    # for PIL, which turns the other way round from a canvas.
                    entry['vector_rotate'] = -float(vr)
                # The letter on the compass rose the PNGs draw in the corner. Without
                # it nothing on the plot says which bearing the arrows point from.
                entry['rose_label'] = self.text_dict.get(
                    'rose_label', plot_options.get('rose_label', 'N'))

            # Last, so that 'directions', 'bar_width' and the rest are already in
            # 'entry' and get shortened along with the values they belong to.
            _drop_empty_points(entry, plot_options.get('time_length', 86400),
                               line_options.get('line_gap_fraction'))

            series_out.append(entry)

        if not series_out:
            return None

        payload = {
            'name': plotname,
            'generated': int(plotgen_ts),
            'start': int(x_domain.start),
            'stop': int(x_domain.stop),
            'x_interval': int(timeinc),
            'yscale': _yscale(plot_options, series_out),
            'aggregate_interval': aggregate_interval_out,
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }

        # The PNGs shade the hours of darkness. Send what the page needs to do the same.
        if to_bool(plot_options.get('show_daynight', False)) \
                and to_bool(self.gen_dict.get('include_daynight', True)):
            try:
                dn = _daynight(x_domain.start, x_domain.stop,
                               self.stn_info.latitude_f, self.stn_info.longitude_f)
                if dn:
                    payload['daynight'] = dn
            except Exception as e:
                # Night shading is decorative, so a failure here must not stop the
                # report. Log it: without a line in the log, a plot that quietly
                # loses its shading looks like a skin problem.
                log.warning("Could not compute day/night for '%s': %s", plotname, e)

        return payload


def _linear(convert, from_unit, to_unit):
    """The factor and offset that turn a reading in one unit into the other.

    weewx.units holds a function per pair of units, which is no use to a page doing
    the same arithmetic. Almost every one is linear, so measuring it at 0 and at 1
    gives the factor and the offset exactly. Checking again at 10 catches the ones
    that are not, and those are left out rather than approximated.

    Args:
        convert (Callable[[weewx.units.ValueTuple, str], weewx.units.ValueTuple]):
            Called as ``convert(val_t, to_unit)``, normally `weewx.units.convert`.
            Returns the ValueTuple converted to ``to_unit``.
        from_unit (str): The unit the reading is in.
        to_unit (str): The unit it is wanted in.

    Returns:
        list|None: [factor, offset], such that to = from * factor + offset. None if
            the conversion is not linear, or if there is no way from one to the other.
    """
    try:
        at_zero = float(convert((0.0, from_unit, None), to_unit)[0])
        at_one = float(convert((1.0, from_unit, None), to_unit)[0])
        at_ten = float(convert((10.0, from_unit, None), to_unit)[0])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    factor = at_one - at_zero
    if abs(10.0 * factor + at_zero - at_ten) > 1e-6 * max(1.0, abs(at_ten)):
        return None
    return [round(factor, 12), round(at_zero, 12)]


def _unit_choices(obs_types, units_seen, formatter, converter):
    """What the page needs in order to show these readings in another unit.

    Everything a plot file carries is already converted, into whatever the skin asked
    for, and a page offering Fahrenheit next to Celsius cannot get there from the
    numbers alone. This is the missing half: which group each observation belongs to,
    which unit each system uses for that group, and the arithmetic between any two of
    them. It is written once, into index.json, and is about a kilobyte.

    Args:
        obs_types (set[str]): The observation types the page shows.
        units_seen (set[str]): The units those readings were written in.
        formatter (weewx.units.Formatter): The formatter the report was rendered with.
        converter (weewx.units.Converter): The converter it was rendered with.

    Returns:
        dict: Six keys. 'groups' maps an observation type to its unit group.
            'systems' maps a system name to the unit it uses for each group, and
            'report' does the same for the report itself, so that a reading the
            page adds after rendering can be put in the unit the server would have
            used. 'convert' maps a unit to each unit it can be turned into, as
            [factor, offset]. 'labels' and 'formats' give the label and the number
            format for each unit, so that the page writes "18.5 °C" the way the
            server would have.
    """
    # The unit systems WeeWX has, taken from it rather than listed here, so that a
    # fourth one would need no change. The name is the one the user writes in
    # weewx.conf, and it is what the page puts in front of the reader.
    systems = [(name, weewx.units.std_groups[constant])
               for name, constant in sorted(weewx.units.unit_constants.items(),
                                            key=lambda pair: pair[1])]

    # Every observation type WeeWX knows a group for, not only the ones that appear
    # in a plot. The card at the top of the Horizon skin carries rain rate, UV and
    # half a dozen others no chart draws, and leaving those out would move some
    # readings on a page and not the ones beside them. The table is 3.5 kB.
    groups = {}
    for obs_type, group in weewx.units.obs_group_dict.items():
        if group:
            groups[str(obs_type)] = str(group)
    for obs_type in sorted(obs_types):
        group = weewx.units.getUnitGroup(obs_type)
        if group:
            groups[obs_type] = group

    # Which units the page may have to deal with. That is more than the units the
    # plot files were written in: a viewer can switch the page to any unit system,
    # so every unit that any system uses for any group that appears has to be here.
    wanted = set(units_seen)
    by_system = {}
    for name, table in systems:
        chosen = {}
        for group in sorted(set(groups.values())):
            unit = table.get(group)
            if unit:
                chosen[group] = unit
                wanted.add(unit)
        by_system[name] = chosen

    # Iterate over weewx.units.conversionDict, rather than over every pair of units
    # in 'wanted'. Asking weewx.units.convert() for a pair it cannot convert logs a
    # DEBUG line, and most pairs cannot be converted.
    #
    # This is where the extra units above pay off. The Walter and Lieth diagram on
    # the climate page is always drawn in degree_C and mm, no matter what units the
    # rest of the page is showing, because the 2:1 ratio it depends on is defined in
    # those units. On a US station the readings arrive as degree_F and inch, so
    # 'convert' has to carry the rows that turn them into metric.
    convert = {}
    for from_unit in sorted(wanted):
        pairs = {}
        for to_unit in sorted(weewx.units.conversionDict.get(from_unit, {})):
            if to_unit not in wanted:
                continue
            steps = _linear(weewx.units.convert, from_unit, to_unit)
            if steps:
                pairs[to_unit] = steps
        if pairs:
            convert[from_unit] = pairs

    labels = {}
    formats = {}
    for unit in sorted(wanted):
        labels[unit] = (formatter.get_label_string(unit) or '').strip()
        fmt = formatter.get_format_string(unit)
        if fmt:
            formats[unit] = fmt

    # What the report itself renders in. Everything the server writes is already in
    # these units, but a reading the page fetches for itself is not: the forecast
    # arrives in Celsius whatever the station uses. Without this the page can only
    # convert once a reader has picked a system by hand, and "Default" then means
    # metric rather than what the skin is set to.
    report = {}
    for group in sorted(set(groups.values())):
        unit = converter.group_unit_dict.get(group)
        if unit:
            report[group] = unit

    return {'groups': groups, 'systems': by_system, 'report': report,
            'convert': convert, 'labels': labels, 'formats': formats}


def _write_json(path, payload, indent):
    """Write one JSON file, so that a reader never sees half of it.

    The files are written while a browser may be fetching them, and a reader arriving
    mid-write gets a truncated document. index.json is the one that matters: half a
    list will not parse, so the browser concludes the station publishes no plots and
    draws nothing until the next poll.

    A temporary file in the same directory, renamed over the target, fixes that. The
    rename is atomic within one filesystem, so a reader sees either the old file or
    the new one.

    Args:
        path (str): Where to write the file.
        payload (dict[str, Any]): What to write.
        indent (int | None): Indentation, or None for the compact form.
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fd:
        json.dump(payload, fd, indent=indent, ensure_ascii=False,
                  separators=(',', ':') if indent is None else None)
    os.replace(tmp, path)


# The three grids, as the index names them: what each file covers, and which grid it
# is on. One entry per tier, finest last.
TIERS = (('covered', 'intervals'), ('fine', 'fine_intervals'),
         ('raw', 'raw_intervals'))


def _new_entry():
    """A blank index entry for one plot group."""
    entry = {'title': None, 'unit_label': None}
    for kind, grids in TIERS:
        entry[kind] = {}
        entry[grids] = {}
    return entry


def _year_grid(year, this_year, recent_years, resolution, coarse_resolution, existing):
    """The interval one calendar year's file is written at.

    The recent years get the finer grid, because those are the ones people read
    closely. Older ones get the coarse one: a year read at a glance does not need 8760
    points, and the difference is what a long record costs to build and to fetch.

    A file already finer than the answer keeps what it has. Rewriting a year to hold
    less than it does would be a year of aggregate queries spent going backwards.

    Args:
        year (int): The calendar year the file covers.
        this_year (int): The year the report is being run in.
        recent_years (int): How many years, counting back, use the finer grid.
        resolution (int): That finer grid, in seconds.
        coarse_resolution (int): The grid the older years use, in seconds.
        existing (int | None): The grid the file on disk was written at, if there is one.
    """
    if recent_years and year <= this_year - recent_years:
        grid = coarse_resolution
    else:
        grid = resolution
    if existing and existing < grid:
        return existing
    return grid


def _months_back(last_ts, months, floor_ts):
    """The start of the calendar month 'months - 1' before the one holding last_ts.

    Counted in calendar months rather than days, because that is how the files are
    cut. 'fine_months = 2' means the month in progress and the one before it, whole,
    however long they are.

    Args:
        last_ts (int): The newest reading in the database.
        months (int): How many calendar months to reach back.
        floor_ts (int): The oldest reading, which the answer never precedes.
    """
    tt = time.localtime(last_ts)
    year, month = tt.tm_year, tt.tm_mon
    month -= max(0, months - 1)
    while month < 1:
        month += 12
        year -= 1
    start = int(time.mktime((year, month, 1, 0, 0, 0, 0, 0, -1)))
    return max(start, floor_ts)


def _rebuild_due(rebuilt, now_ts, after):
    """Is this the run that builds every file from the database again?

    Extending a file forward keeps whatever the run before put in it, so anything that
    changes the past stays: a reading corrected by an import, a series that only starts
    reporting now, a unit the configuration has since changed. Doing the whole span
    again at a fixed cadence bounds how long any of that survives.

    The test is on the calendar rather than on elapsed seconds, so a station reporting
    every five minutes and one reporting every hour both rebuild on the first report
    after midnight, and one switched off over midnight rebuilds when it comes back.

    Args:
        rebuilt (int | None): When the last rebuild ran, or None for never.
        now_ts (int): The time this report is being run for.
        after (int): How many seconds between rebuilds. Zero never rebuilds.
    """
    if not after:
        return False
    if rebuilt is None:
        return True
    # Under a day there are no calendar boundaries to hang this on, so it goes back
    # to elapsed time.
    if after < 86400:
        return now_ts - rebuilt >= after
    then = datetime.date.fromtimestamp(rebuilt)
    now = datetime.date.fromtimestamp(now_ts)
    return (now - then).days >= int(after // 86400)


def _affordable(budget, counters):
    """How many slots are left in this run's budget, or None for no limit.

    The cost of a slot is one database query, and how long that takes is the machine's
    business rather than something to guess at here. So it is measured: what this run
    has spent, over the slots it spent it on. Until there is something to measure, a
    deliberately pessimistic guess stands in.

    Args:
        budget (int): How many seconds this report may spend. Zero removes the limit.
        counters (dict[str, Any]): What the run has spent so far, and on how many
            slots.

    Returns:
        int|None: Slots that fit in what is left, at least one so that a run always
            gets somewhere. None if there is no budget at all.
    """
    if not budget:
        return None
    left = budget - counters['spent']
    if left <= 0:
        return 0
    per_slot = counters['spent'] / counters['slots'] if counters['slots'] else 0.005
    return max(1, int(left / per_slot))


def _carry_over_index(index, known, group_name):
    """Name every file that exists, not only the ones this run touched.

    A run writes the spans that are due and leaves the rest alone, and a run with a
    budget leaves more than that. Both are right on disk and wrong in the index: what
    it does not name, the page cannot see. 'known' has already been checked against
    the directory, so anything in it is really there.

    Args:
        index (dict[str, dict[str, Any]]): The index being written.
        known (dict[str, dict[str, Any]]): The files that are really on disk.
        group_name (str): The plot group to carry over.
    """
    entry = index.setdefault(group_name, _new_entry())
    for kind, grids in TIERS:
        for stamp, ts in known[kind].get(group_name, {}).items():
            if stamp in entry[kind]:
                continue
            entry[kind][stamp] = ts
            grid = known[grids].get(group_name, {}).get(stamp)
            if grid:
                entry[grids][stamp] = grid
    if not entry['title']:
        title, unit_label = known['labels'].get(group_name, (None, None))
        entry['title'] = title
        entry['unit_label'] = unit_label


def _archive_interval(db_manager, last_ts):
    """How far apart the station's readings are, from a reading rather than a setting.

    The configured interval and the one in use are not always the same: a driver that
    reads the interval off the hardware overrides it, and says so in the log. The
    record is the one that was actually written.

    Args:
        db_manager (weewx.manager.Manager): The open database.
        last_ts (int): The newest reading in it.
    """
    try:
        record = db_manager.getRecord(int(last_ts))
        if record and record.get('interval'):
            return int(record['interval']) * 60
    except (weedb.DatabaseError, TypeError, ValueError, KeyError):
        pass
    return 300


def _drop_stale_raw(arch_root, group_name, keep):
    """Delete this group's raw day files that are no longer wanted.

    The raw tier is the only one with a horizon. Every other file is written once and
    kept, because it answers a question that will be asked again. A raw day from last
    year is not: it would be one small file per group per day, forever, for a view
    nobody steps back that far in.

    Args:
        arch_root (str): The archive directory.
        group_name (str): The plot group to sweep.
        keep (set[str]): The day stamps that are still wanted.
    """
    prefix = '%s-raw-' % group_name
    try:
        names = os.listdir(arch_root)
    except OSError:
        return
    for filename in names:
        if not filename.startswith(prefix) or not filename.endswith('.json'):
            continue
        stamp = filename[len(prefix):-len('.json')]
        if stamp in keep:
            continue
        try:
            os.remove(os.path.join(arch_root, filename))
        except OSError as e:
            log.debug("Could not remove stale raw file '%s': %s", filename, e)


def _read_archive_file(path):
    """One archive file as the last run left it, or None if it cannot be used.

    None covers every way this can go wrong: no file, half a file, a file written by a
    version that shaped it differently. All of them mean the same to the caller, which
    is that the span has to be calculated from the database again.

    Args:
        path (str): The file to read.
    """
    try:
        with open(path, encoding='utf-8') as fd:
            payload = json.load(fd)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get('series'), list):
        return None
    return payload


def _resume_from(previous, start, resolution, slots):
    """Where an extended file picks up, or None to work the whole span out again.

    The instant comes out of the file rather than from its slot number, and it has to.
    get_series() puts its aggregation boundaries on constant local time, so where the
    clocks change they are not a whole number of intervals apart. Two runs counting
    from different points would disagree about where a slot begins, and an extended
    file would not match what a rebuild produces.

    Args:
        previous (dict[str, Any] | None): The file already on disk, or None.
        start (int): Where the span being written begins.
        resolution (int): The grid it is written on, in seconds.
        slots (int): How many slots the span holds.

    Returns:
        tuple|None: The instant to ask the database from, and the first slot to
            overwrite. None if the file on disk cannot be carried forward: a changed
            'start' (a moved 'max_days' window), a changed 'interval' (a changed
            'resolution'), a file that reaches past the span now being built (a clock
            that went backwards), or one written before this field existed.
    """
    if not previous:
        return None
    try:
        if int(previous['start']) != start or int(previous['interval']) != resolution:
            return None
        count = int(previous['count'])
        resume_ts = int(previous['resume_ts'])
        resume_slot = int(previous['resume_slot'])
    except (KeyError, TypeError, ValueError):
        return None
    if not 2 <= count <= slots or not previous['series']:
        return None
    if not 0 <= resume_slot < count or not start <= resume_ts:
        return None
    return resume_ts, resume_slot


def _carried_series(previous, position, var_type, count):
    """The series an extended file keeps, whole, or None to rebuild.

    Matched by position, which is the order the skin's plot section gives and only
    changes when the skin does. The observation type has to agree as well: two series
    can swap places without changing how many there are.

    The whole entry rather than its values, because a series can carry more than one
    array: a vector has its components, and a type worth its extremes has those.

    Args:
        previous (dict[str, Any]): The file already on disk.
        position (int): Which of its series to take.
        var_type (str): The observation type it should hold.
        count (int): How many slots the new file has.
    """
    try:
        entry = previous['series'][position]
        values = entry['values']
    except (IndexError, KeyError, TypeError):
        return None
    if entry.get('obs_type') != var_type or not isinstance(values, list) \
            or len(values) != count:
        return None
    return entry


def _daynight(start_ts, stop_ts, lat, lon):
    """Sunrise, sunset, and the civil twilight around them.

    `weeutil.weeutil.getDayNightTransitions()` gives the moments the sun crosses the
    horizon, where the PNGs step from day shading to night. The light does not change
    that abruptly: it fades over the half hour or so of civil twilight, and over much
    longer at high latitude in summer. Those boundaries are returned as well, so the
    page can fade rather than step.

    Args:
        start_ts (int): The beginning of the span.
        stop_ts (int): Its end.
        lat (float): The station latitude, in degrees.
        lon (float): Its longitude, in degrees.

    Returns:
        dict|None: Three keys. 'first' is 'day' or 'night', whichever it was at
            start_ts. 'transitions' is the horizon crossings, as timestamps.
            'twilight' is one entry per dawn and dusk, e.g.
            {'from': 1787725000, 'to': 1787727100, 'dir': 'dawn'}. None where the sun
            neither rises nor sets in this span, as it does inside the polar circles.
    """
    from weeutil import Sun

    start_ts, stop_ts = int(start_ts), int(stop_ts)
    first = None
    transitions = []
    twilight = []

    for t in range(start_ts - 86400, stop_ts + 86401, 86400):
        x_tt = time.gmtime(weeutil.weeutil.startOfDayUTC(t))
        y, m, d = x_tt[:3]
        day_start = calendar.timegm((y, m, d, 0, 0, 0, 0, 0, -1))

        rise_h, set_h = Sun.sunRiseSet(y, m, d, lon, lat)
        dawn_h, dusk_h = Sun.civilTwilight(y, m, d, lon, lat)

        rise = int(day_start + rise_h * 3600.0 + 0.5)
        sets = int(day_start + set_h * 3600.0 + 0.5)
        dawn = int(day_start + dawn_h * 3600.0 + 0.5)
        dusk = int(day_start + dusk_h * 3600.0 + 0.5)

        if start_ts < rise < stop_ts:
            transitions.append(rise)
            if first is None:
                first = 'night'
        if start_ts < sets < stop_ts:
            transitions.append(sets)
            if first is None:
                first = 'day'

        # Dawn runs from the start of civil twilight to sunrise, getting lighter. Dusk
        # runs from sunset to the end of civil twilight, getting darker. Naming which
        # is which saves the page from deducing it from the horizon crossings.
        if dawn < stop_ts and rise > start_ts:
            twilight.append({'from': dawn, 'to': rise, 'dir': 'dawn'})
        if sets < stop_ts and dusk > start_ts:
            twilight.append({'from': sets, 'to': dusk, 'dir': 'dusk'})

    if first is None and not transitions:
        # The sun neither rose nor set in this span. Inside the polar circles that is
        # normal for weeks at a time.
        return None

    transitions.sort()
    twilight.sort(key=lambda b: b['from'])
    return {'first': first or 'day', 'transitions': transitions, 'twilight': twilight}


def _holds_plots(section):
    """Does this section define plots, rather than hold settings?

    A plot definition is three levels deep: [ImageGenerator], then a time span such as
    [[day_images]], then a plot such as [[[daytempdew]]]. So a section holds plots when
    its subsections have subsections of their own. A settings section such as
    [[Archive]] has one level at most, and holding scalars is what tells it apart.

    Args:
        section (dict): The section to test.
    """
    try:
        return any(section[name].sections for name in section.sections)
    except (AttributeError, KeyError, TypeError):
        return False


def _yscale(plot_options, series_out):
    """The y axis for this plot, as [min, max, increment].

    Worked out here rather than in the page, using the function the ImageGenerator
    calls. The plot's own 'yscale' fixes whichever of the three values it names, and
    weeplot.utilities.scale() works out the rest from the data. A chart library left to
    choose its own gets this wrong: wind direction running to 400 degrees, or an axis
    reaching 5 m/s for wind that never passed 2.3.

    Args:
        plot_options (dict[str, Any]): The options of the plot being written.
        series_out (list[dict[str, Any]]): The series already worked out for it.

    Returns:
        list|None: The three values, or None if there is nothing to scale.
    """
    prescale = weeutil.weeutil.convertToFloat(
        weeutil.weeutil.option_as_list(plot_options.get('yscale', ['None', 'None', 'None'])))
    prescale = tuple(prescale) + (None,) * (3 - len(prescale))

    ymin = ymax = None
    for entry in series_out:
        values = [v for v in entry['values'] if v is not None]
        if not values:
            continue
        if entry.get('plot_type') == 'vector':
            # A vector's extent is the magnitude, mirrored about zero, exactly as
            # genplot._calcYScaling() has it.
            line_max = max(abs(v) for v in values)
            line_min = -line_max
        else:
            line_min, line_max = min(values), max(values)
        ymin = line_min if ymin is None else min(ymin, line_min)
        ymax = line_max if ymax is None else max(ymax, line_max)

    if ymin is None:
        return None
    nsteps = to_int(plot_options.get('y_nticks', 10))
    return list(weeplot.utilities.scale(ymin, ymax, prescale, nsteps=nsteps))


def _drop_empty_points(entry, time_length, gap_fraction, gap_factor=3.0):
    """Leave out the points that carry nothing, keeping real gaps visible.

    A sensor reporting every ten minutes has a reading in one archive record out of
    ten and null in the other nine. Sent as they are, the page draws a line broken in
    hundreds of places, in a file many times larger than the readings in it.

    A run of nulls counts as a gap by the sensor's own interval, not the width of the
    plot: ten minutes without a reading is a fault at an eight second interval and
    normal at a ten minute one. So the interval is measured, and only a run several
    times longer is kept as a gap. 'line_gap_fraction' wins where it is set, which is
    the ImageGenerator's fixed threshold.

    Args:
        entry (dict[str, Any]): The series to thin.
        time_length (int): The span it covers, in seconds.
        gap_fraction (float | None): The plot option of the same name.
        gap_factor (float): How many archive intervals count as a gap.
    """
    times, values = entry['time'], entry['values']
    if len(times) != len(values):
        return

    kept = [i for i, v in enumerate(values) if v is not None]
    if not kept:
        return

    threshold = None
    if gap_fraction and time_length:
        # 'time_length' may be a duration such as '27h', the same as everywhere else
        # it is read.
        span = weeutil.weeutil.nominal_spans(time_length)
        if span:
            threshold = float(gap_fraction) * float(span)
    if threshold is None and len(kept) >= 3:
        spacings = sorted(times[b] - times[a] for a, b in zip(kept, kept[1:]))
        usual = spacings[len(spacings) // 2]
        if usual > 0:
            threshold = gap_factor * usual

    keep = []
    for position, i in enumerate(kept):
        if position and threshold is not None:
            previous = kept[position - 1]
            if times[i] - times[previous] >= threshold:
                # Long enough to be a break in the readings rather than the sensor's
                # normal spacing. Keep one null in the middle of the run, which is
                # what breaks the line; the other nulls would draw nothing.
                keep.append(previous + (i - previous) // 2)
        keep.append(i)

    if len(keep) == len(values):
        return
    entry['time'] = [times[i] for i in keep]
    entry['values'] = [values[i] for i in keep]
    for extra in ('directions', 'bar_width', 'vector_x', 'vector_y'):
        seq = entry.get(extra)
        if isinstance(seq, list) and len(seq) == len(values):
            entry[extra] = [seq[i] for i in keep]


def _round_seq(seq, ndigits):
    """Round a sequence, leaving None (gaps in the data) intact.

    Args:
        seq (list[float | None]): The readings.
        ndigits (int | None): Decimal places, or None to leave them alone.
    """
    if ndigits is None:
        return list(seq)
    return [None if v is None else round(v, ndigits) for v in seq]


def _vector_components(seq):
    """Split a complex series into its real and imaginary parts.

    weeplot draws a wind vector by scaling the complex value and offsetting it from the
    zero line, so a page drawing the same arrows needs both parts.

    Args:
        seq (list[complex | None]): Complex readings, as `get_series()` returns them for wind.

    Returns:
        tuple[list, list]|None: The real parts and the imaginary parts, or None if the
            series holds no complex values and is therefore not a vector series.
    """
    seq = list(seq)
    if not any(isinstance(v, complex) for v in seq):
        return None
    real = [None if v is None else (v.real if isinstance(v, complex) else v) for v in seq]
    imag = [None if v is None else (v.imag if isinstance(v, complex) else 0.0) for v in seq]
    return real, imag


def _split_vectors(seq):
    """Split a wind series into speeds and compass bearings.

    WeeWX holds a wind vector either as a complex number or, once converted, as a
    `weewx.units.Polar`. A series of neither is not a wind series and is returned as it
    came.

    Args:
        seq (list[complex | None]): Complex readings, as `get_series()` returns them for wind.

    Returns:
        tuple[list, list|None]: The speeds, and the bearings in degrees. The bearings
            are None for a series that was not a wind series.
    """
    seq = list(seq)
    if not any(isinstance(v, (complex, weewx.units.Polar)) for v in seq):
        return seq, None

    magnitudes = []
    directions = []
    for v in seq:
        if v is None:
            magnitudes.append(None)
            directions.append(None)
        elif isinstance(v, weewx.units.Polar):
            magnitudes.append(v.mag)
            directions.append(v.dir)
        elif isinstance(v, complex):
            magnitudes.append(abs(v))
            # Polar.from_complex() applies WeeWX's convention: the bearing is the one
            # the wind blows from, measured clockwise from north.
            directions.append(weewx.units.Polar.from_complex(v).dir)
        else:
            magnitudes.append(v)
            directions.append(None)
    return magnitudes, directions


def _normalize_color(color):
    """Rewrite a WeeWX colour as one CSS understands.

    WeeWX accepts three forms: '#RRGGBB', '0xBBGGRR' and English names such as 'blue'.
    CSS takes the first and the third as they are. The second has its red and blue bytes
    the other way round and has to be swapped.

    Args:
        color (str | int | None): A colour, in any of the forms the skin may write it.
    """
    if not isinstance(color, str):
        return color
    c = color.strip()
    if c.lower().startswith('0x'):
        try:
            bgr = int(c, 16)
            b, g, r = (bgr >> 16) & 0xff, (bgr >> 8) & 0xff, bgr & 0xff
            return '#%02x%02x%02x' % (r, g, b)
        except ValueError:
            return c
    return c
