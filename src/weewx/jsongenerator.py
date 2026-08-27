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
import json
import logging
import os
import time

import weeplot.utilities
import weeutil.logger
import weeutil.weeutil
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
        # Generic labels, such as "Outside Temperature":
        try:
            self.generic_dict = self.skin_dict['Labels']['Generic']
        except KeyError:
            self.generic_dict = {}
        # Translated text strings:
        self.text_dict = self.skin_dict.get('Texts', {})

        # Which section holds the plot definitions. [JSONGenerator] when the skin
        # has one, [ImageGenerator] otherwise, so that a skin written before this
        # generator existed needs no new configuration. Option 'source' names a
        # third section instead.
        #
        # An empty section, not an empty dict, when the skin has none: search_up()
        # climbs the tree through .parent, which a plain dict does not have.
        if 'JSONGenerator' not in self.skin_dict:
            self.skin_dict['JSONGenerator'] = {}
        self.gen_dict = self.skin_dict['JSONGenerator']
        source = self.gen_dict.get('source')
        if source:
            named = True
        else:
            source, named = 'JSONGenerator', False

        self.plot_dict = self.skin_dict.get(source, {})
        if not _holds_plots(self.plot_dict):
            if named:
                log.error("Section [%s] holds no plot definitions. "
                          "JSON generation skipped.", source)
                self.plot_dict = {}
            else:
                self.plot_dict = self.skin_dict.get('ImageGenerator', {})
                if not _holds_plots(self.plot_dict):
                    log.error("No plot definitions found, in [JSONGenerator] or "
                              "[ImageGenerator]. JSON generation skipped.")
                    self.plot_dict = {}

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

    def gen_json(self, gen_ts):
        """Walk the plot definitions and write one JSON file per plot."""
        t1 = time.time()
        ngen = 0

        if not self.plot_dict:
            return

        log_success = to_bool(search_up(self.gen_dict, 'log_success', True))

        # Where to write. Default to a 'data' subdirectory so JSON does not litter the
        # top level next to the HTML.
        dest_dir = self.gen_dict.get('json_dest_dir', 'data')
        indent = to_int(self.gen_dict.get('json_indent'))

        # One entry per plot written. At the end of this method they go into
        # 'index.json', a list of every plot file that exists, with its title, its
        # units and the observation types in it. The page reads index.json first and
        # lays out its charts from that, rather than requesting each plot to find out
        # whether it is there. A station without a UV sensor has no UV plot, and
        # nothing asks for the file.
        manifest = []
        manifest_root = None
        nskipped = 0
        # How many seconds each time span covers, from 'time_length' in the plot
        # definitions: 86400 for [[day_images]], and so on. It goes into index.json
        # because the page draws the x axis itself, and 'time_length' is the only
        # statement of how wide a "day" plot is meant to be. Leave it out and the
        # option no longer reaches the chart at all.
        span_lengths = {}

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

                # An aggregated plot only changes when its aggregation interval rolls
                # over: a year plot of daily averages says the same thing at 10:05 as
                # it did at 10:00. Rewriting it anyway costs a database read, and on a
                # station publishing over FTP, an upload of every file every cycle.
                # This is the test the ImageGenerator applies to its PNGs.
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
            obs_types = set()
            units_seen = set()
            for entry in manifest:
                obs_types.update(entry.get('obs_types') or [])
                if entry.get('unit'):
                    units_seen.add(entry['unit'])
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
                                                    self.formatter),
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

        gen_json() above writes the four plots the ImageGenerator draws: the last day,
        the last week, the last month and the last year, each ending now. None of the
        four can answer "show me last March", because last March was never one of them.

        This method writes the whole database instead, split by calendar year. Two
        things follow from splitting it that way, and both matter on the small machines
        WeeWX usually runs on:

        - A year that has ended never changes again. Its file is written once and
          skipped from then on, so a station with fourteen years of data rewrites one
          file per report rather than fourteen.
        - The page fetches only the years it is showing.

        Readings inside a file are spaced evenly in time, one every `resolution`
        seconds. A file therefore stores the first timestamp and that spacing, and no
        timestamp per reading, which halves it.

        A file is rewritten when its newest reading moves into the next slot of that
        spacing, not when the file reaches a given age. While the station is running,
        those two are the same thing. They differ after a catch-up import, where the
        file is minutes old and hours behind: an age test would find nothing to do.

        To rebuild everything, delete the archive directory and run the report again
        (`weectl report run <report>`).
        """
        arch_dict = self.gen_dict.get('Archive', {})
        if not to_bool(arch_dict.get('enable', False)):
            return

        t1 = time.time()

        source_group = arch_dict.get('source_group', 'day_images')
        strip_prefix = arch_dict.get('strip_prefix', 'day')
        resolution = to_int(weeutil.weeutil.nominal_spans(arch_dict.get('resolution', 3600)))
        aggregate_type = arch_dict.get('aggregate_type', 'avg')
        max_days = to_int(arch_dict.get('max_days', 0))
        # A second set of files over the recent past, spaced more closely and written
        # per calendar month. One reading an hour is the right trade over years, but it
        # flattens a single day, and stepping back one day at a time is what the page
        # offers. Thirty days at one reading per five minutes costs about what one year
        # at one per hour costs, and the page fetches only the months it is showing.
        fine_days = to_int(arch_dict.get('fine_days', 0))
        fine_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('fine_resolution', 300)))
        if fine_days and fine_resolution >= resolution:
            # An easy mistake: in a duration suffix 'm' means months, not minutes, so
            # '5m' asks for readings five months apart.
            log.warning("Ignoring fine_days: fine_resolution (%d seconds) is not finer "
                        "than resolution (%d seconds)", fine_resolution, resolution)
            fine_days = 0
        dest_dir = arch_dict.get('dest_dir',
                                 os.path.join(self.gen_dict.get('json_dest_dir', 'data'),
                                              'archive'))
        indent = to_int(self.gen_dict.get('json_indent'))
        rounding = to_int(arch_dict.get('round', self.gen_dict.get('round', 2)))

        try:
            group_dict = self.plot_dict[source_group]
        except KeyError:
            log.error("Archive: no section [%s]. Skipped.", source_group)
            return

        ngen = 0
        nskipped = 0
        index = {}
        root = None
        overall_start = overall_stop = None

        # How far the last run got, per group and year, from the index it left behind.
        # One file, read once, the way gen_json() reads its own index.
        previous, previous_fine, previous_first = self._read_archive_index(dest_dir)

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
            if overall_start is None or first_ts < overall_start:
                overall_start = int(first_ts)
            if overall_stop is None or last_ts > overall_stop:
                overall_stop = int(last_ts)

            group_name = plotname[len(strip_prefix):] \
                if strip_prefix and plotname.startswith(strip_prefix) else plotname

            arch_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     plot_options['HTML_ROOT'], dest_dir)

            for year_span in weeutil.weeutil.genYearSpans(first_ts, last_ts):
                year = time.localtime(year_span.start).tm_year
                out_file = os.path.join(arch_root, '%s-%d.json' % (group_name, year))

                # The newest reading this file holds. For a year that has ended it is
                # the last instant of the year, and never moves again. That file is
                # written once, which is what keeps a long record cheap to report. For
                # the year in progress it advances with the database, and the file is
                # rewritten once it reaches the next slot.
                covered = min(int(year_span.stop), int(last_ts))
                was = previous.get(group_name, {}).get(year)
                if os.path.exists(out_file) and was is not None and not reimported \
                        and was // resolution == covered // resolution:
                    nskipped += 1
                    entry = index.setdefault(group_name, {'years': [], 'covered': {}})
                    entry['years'].append(year)
                    entry['covered'][year] = was
                    root = arch_root
                    continue

                payload = self._archive_year(group_dict[plotname], plot_options, year_span,
                                             resolution, aggregate_type, rounding,
                                             group_name, first_ts, last_ts)
                if payload is None:
                    continue

                try:
                    _write_json(out_file, payload, indent)
                    ngen += 1
                    root = arch_root
                    entry = index.setdefault(group_name, {'years': [], 'covered': {}})
                    entry['years'].append(year)
                    entry['covered'][year] = payload['covered']
                    entry['title'] = ', '.join(s['label'] for s in payload['series'])
                    entry['unit_label'] = payload['unit_label']
                except OSError as e:
                    log.error("Unable to save to file '%s': %s", out_file, e)

            if fine_days:
                fine_from = max(int(first_ts), int(last_ts) - fine_days * 86400)
                for month_span in weeutil.weeutil.genMonthSpans(fine_from, last_ts):
                    stamp = time.strftime('%Y-%m', time.localtime(month_span.start))
                    out_file = os.path.join(arch_root, '%s-fine-%s.json'
                                            % (group_name, stamp))
                    covered = min(int(month_span.stop), int(last_ts))
                    was = previous_fine.get(group_name, {}).get(stamp)
                    if os.path.exists(out_file) and was is not None and not reimported \
                            and was // fine_resolution == covered // fine_resolution:
                        nskipped += 1
                        entry = index.setdefault(group_name, {'years': [], 'covered': {}})
                        entry.setdefault('fine', {})[stamp] = was
                        root = arch_root
                        continue

                    payload = self._archive_year(group_dict[plotname], plot_options,
                                                 month_span, fine_resolution,
                                                 aggregate_type, rounding, group_name,
                                                 fine_from, last_ts)
                    if payload is None:
                        continue
                    try:
                        _write_json(out_file, payload, indent)
                        ngen += 1
                        root = arch_root
                        entry = index.setdefault(group_name, {'years': [], 'covered': {}})
                        entry.setdefault('fine', {})[stamp] = payload['covered']
                    except OSError as e:
                        log.error("Unable to save to file '%s': %s", out_file, e)

        # Sunrise and sunset for the whole record. They depend on the location alone,
        # so they go in one file per year instead of being repeated in every group's
        # file. The page shades the night from them, on spans short enough for the
        # bands to be readable.
        if root and to_bool(arch_dict.get('include_daynight',
                                          self.gen_dict.get('include_daynight', True))):
            self._archive_daynight(root, overall_start, overall_stop, indent)

        if root:
            groups = []
            for name in sorted(index):
                entry = index[name]
                groups.append({
                    'name': name,
                    'title': entry.get('title', name),
                    'unit_label': entry.get('unit_label', ''),
                    'years': sorted(set(entry['years'])),
                    # Newest reading per year. JSON has no integer keys, so the year
                    # is written as a string and read back as one.
                    'covered': {str(y): c for y, c in entry.get('covered', {}).items()},
                    # The same, for the months that also have a closely spaced file.
                    'fine': {str(m): c for m, c in entry.get('fine', {}).items()},
                })
            try:
                _write_json(os.path.join(root, 'index.json'),
                            {'interval': resolution,
                             'fine_interval': fine_resolution if fine_days else None,
                             'first': int(overall_start) if overall_start else None,
                             'last': int(overall_stop) if overall_stop else None,
                             'groups': groups},
                            indent)
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        if to_bool(search_up(self.gen_dict, 'log_success', True)):
            log.info("Generated %d archive files (%d already current) for report %s "
                     "in %.2f seconds",
                     ngen, nskipped, self.skin_dict['REPORT_NAME'], time.time() - t1)

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
        # The dots keep 'summaryimage.SummaryImageGenerator' out. That name holds
        # the word too, and it draws one picture of the current readings, not a
        # PNG per plot.
        return any('.imagegenerator.' in str(g).lower()
                   for g in weeutil.weeutil.option_as_list(generators))

    def _read_archive_index(self, dest_dir):
        """How far the previous run got, from the index it left behind.

        Returns:
            tuple: Three values.

                - {group: {year: timestamp}}, the newest reading each year's file
                  holds, e.g. {'tempdew': {2025: 1735689599, 2026: 1787777700}}
                - the same for the closely spaced months, keyed 'YYYY-MM'
                - the oldest reading in the database when the last run read it, or
                  None if there was no index to read
        """
        covered = {}
        fine = {}
        first = None
        try:
            path = os.path.join(self.config_dict['WEEWX_ROOT'],
                                search_up(self.skin_dict, 'HTML_ROOT', 'public_html'),
                                dest_dir, 'index.json')
            with open(path, encoding='utf-8') as fd:
                index = json.load(fd)
            first = to_int(index.get('first'))
            for group in index.get('groups', []):
                years = {}
                for year, ts in (group.get('covered') or {}).items():
                    years[int(year)] = int(ts)
                if years:
                    covered[group['name']] = years
                months = {}
                for stamp, ts in (group.get('fine') or {}).items():
                    months[str(stamp)] = int(ts)
                if months:
                    fine[group['name']] = months
        except (OSError, ValueError, KeyError, TypeError):
            # No index, or one this version cannot read. Report that nothing is
            # current, so everything is rebuilt. That costs a run; the other way
            # round would leave stale files in place.
            return {}, {}, None
        return covered, fine, first

    def _archive_daynight(self, root, first_ts, last_ts, indent):
        """Write sunrise and sunset times, one file per calendar year.

        Sunrise and sunset depend on the station's latitude and longitude and on
        nothing else, so one file serves every plot group. Like the data files, a year
        that has ended is written once and then left alone.
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

    def _archive_year(self, plot_section, plot_options, year_span, resolution,
                      aggregate_type, rounding, group_name, first_ts, last_ts):
        """Build the contents of one archive file: one plot group, one calendar year.

        There are no timestamps in the result. `start` is the first instant, `interval`
        the seconds between readings, and `count` how many there are, so the time of
        `values[i]` is `start + i * interval`. A null in `values` is a reading the
        station did not take.

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
        lo = max(year_span.start, int(first_ts))
        hi = min(year_span.stop, int(last_ts) + resolution)
        start = int(lo // resolution * resolution)
        stop = int(hi // resolution * resolution) + resolution
        domain = TimeSpan(start, stop)
        slots = int((stop - start) / resolution)
        if slots < 2:
            return None

        series_out = []
        unit = unit_label = None

        for line_name in plot_section.sections:
            line_options = accumulateLeaves(plot_section[line_name])
            var_type = line_options.get('data_type', line_name)
            mgr = self.db_binder.get_manager(line_options['data_binding'])

            if _skip_if_empty(mgr, var_type, domain):
                continue

            # Wind vectors are pairs of components, not single numbers, and the evenly
            # spaced form here holds one number per slot. The day, week, month and year
            # files written by gen_json() still carry them.
            if line_options.get('plot_type', 'line').lower() == 'vector':
                continue

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
                # An arithmetic mean of compass bearings says the wrong thing: 350 and
                # 10 degrees average to 180, due south, where the wind never blew from.
                # WeeWX has the 'vecdir' aggregate for this, which averages the vectors
                # and then takes the bearing. It reads the 'wind' daily summary, so the
                # observation type has to change with the aggregate.
                var_type = 'wind'
                agg = 'vecdir'

            option_dict = dict(line_options)
            option_dict.pop('aggregate_type', None)
            option_dict.pop('aggregate_interval', None)

            try:
                _, stop_vec_t, data_vec_t = weewx.xtypes.get_series(
                    var_type, domain, mgr,
                    aggregate_type=agg,
                    aggregate_interval=resolution,
                    **option_dict)
            except (weewx.UnknownType, weewx.UnknownAggregation):
                continue

            if plot_options.get('unit'):
                conv = weewx.units.convert(data_vec_t, plot_options['unit'])
            else:
                conv = self.converter.convert(data_vec_t)

            unit = conv[1]
            unit_label = line_options.get(
                'y_label', self.formatter.get_label_string(conv[1]))

            # Put each value where its timestamp belongs. get_series() returns nothing
            # at all for an interval with no readings, so the position is computed from
            # the timestamp rather than taken from the loop counter.
            grid = [None] * slots
            for ts, val in zip(stop_vec_t[0], conv[0]):
                if ts is None or val is None:
                    continue
                slot = int((ts - resolution - start) // resolution)
                if 0 <= slot < slots:
                    grid[slot] = round(val, rounding) if rounding is not None else val

            label = line_options.get('label')
            label = self.text_dict.get(label, label) if label \
                else self.generic_dict.get(var_type, var_type)

            entry = {
                'obs_type': var_type,
                'label': label,
                'aggregate_type': agg,
                'values': grid,
            }
            color = line_options.get('color')
            if color:
                entry['color'] = _normalize_color(color)
            if line_options.get('plot_type', 'line').lower() == 'bar':
                entry['plot_type'] = 'bar'
            series_out.append(entry)

        if not series_out:
            return None

        # Colours the skin sets for every plot, for series that name none of their own.
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
            'covered': min(int(year_span.stop), int(last_ts)),
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }

    def gen_plot_data(self, plotgen_ts, plot_options, plot_dict, plotname):
        """Assemble the data for a single plot.

        Mirrors ImageGenerator.gen_plot(), minus everything to do with drawing. Unlike
        _archive_year() above, every reading carries its own timestamp here, because
        the readings are as the station took them and not evenly spaced.

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

    weewx.units holds a function per pair of units, which is no use to a page that
    wants to do the same arithmetic. Almost every one of them is linear, so measuring
    it at 0 and at 1 gives the factor and the offset exactly. Checking it again at 10
    catches the ones that are not, and those are left out rather than approximated.

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


def _unit_choices(obs_types, units_seen, formatter):
    """What the page needs in order to show these readings in another unit.

    Everything a plot file carries is already converted, into whatever the skin asked
    for, and a page that wants to offer Fahrenheit next to Celsius cannot get there
    from the numbers alone. This is the missing half: which group each observation
    belongs to, which unit each unit system uses for that group, and the arithmetic
    between any two of them.

    It is written once, into index.json, and is about a kilobyte.

    Returns:
        dict: Four keys. 'groups' maps an observation type to its unit group.
            'systems' maps a system name to the unit it uses for each group.
            'convert' maps a unit to each unit it can be turned into, as
            [factor, offset]. 'labels' and 'formats' give the label and the number
            format for each unit, so that the page writes "18.5 °C" the way the
            server would have.
    """
    systems = [('US', weewx.units.USUnits),
               ('Metric', weewx.units.MetricUnits),
               ('MetricWX', weewx.units.MetricWXUnits)]

    groups = {}
    for obs_type in sorted(obs_types):
        group = weewx.units.getUnitGroup(obs_type)
        if group:
            groups[obs_type] = group

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

    convert = {}
    for from_unit in sorted(units_seen):
        pairs = {}
        for to_unit in sorted(wanted):
            if to_unit == from_unit:
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

    return {'groups': groups, 'systems': by_system, 'convert': convert,
            'labels': labels, 'formats': formats}


def _write_json(path, payload, indent):
    """Write one JSON file, so that a reader never sees half of it.

    The files are written while a browser somewhere may be fetching them, and a
    reader that arrives mid-write gets a truncated document. index.json is the one
    that matters: a browser cannot parse half a list, so it concludes that the station
    publishes no plots at all and draws nothing until the next poll.

    Writing to a temporary file in the same directory and renaming it over the target
    fixes that. Within one filesystem the rename is atomic, so a reader sees either
    the old file or the new one.
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fd:
        json.dump(payload, fd, indent=indent, ensure_ascii=False,
                  separators=(',', ':') if indent is None else None)
    os.replace(tmp, path)


def _daynight(start_ts, stop_ts, lat, lon):
    """Sunrise, sunset, and the civil twilight around them.

    `weeutil.weeutil.getDayNightTransitions()` gives the moments the sun crosses the
    horizon, which is where the PNGs step from day shading to night. The light does not
    change that abruptly: it fades over the half hour or so of civil twilight, and over
    much longer at high latitude in summer. The twilight boundaries are returned as
    well, so the page can fade between the two instead of stepping.

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
    [[Archive]] has one level of subsections at most, and holding scalars is what tells
    it apart.
    """
    try:
        return any(section[name].sections for name in section.sections)
    except (AttributeError, KeyError, TypeError):
        return False


def _yscale(plot_options, series_out):
    """The y axis for this plot, as [min, max, increment].

    Worked out here rather than in the page, using the function the ImageGenerator
    calls. The plot's own 'yscale' fixes whichever of the three values it names, and
    weeplot.utilities.scale() works out the rest from the data.

    A chart library left to choose its own axis gets this wrong in ways that matter:
    wind direction running to 400 degrees, or an axis reaching 5 m/s for wind that
    never passed 2.3. The rule for a readable axis is the same whatever draws it, and
    WeeWX already has it.

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

    A sensor that reports every ten minutes has a reading in one archive record out of
    ten, and null in the other nine. Sent as they are, the page draws a line broken in
    hundreds of places, and the file is many times larger than the readings in it.

    How long a run of nulls counts as a gap depends on how often the sensor reports,
    not on how wide the plot is. Ten minutes without a reading is a fault on a station
    reporting every eight seconds and normal on one reporting every ten minutes. So the
    interval between readings is measured, and only a run several times longer than
    that is kept as a gap. Where 'line_gap_fraction' is set it wins, which is the
    ImageGenerator's fixed threshold.
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
    """Round a sequence, leaving None (gaps in the data) intact."""
    if ndigits is None:
        return list(seq)
    return [None if v is None else round(v, ndigits) for v in seq]


def _vector_components(seq):
    """Split a complex series into its real and imaginary parts.

    weeplot draws a wind vector by scaling the complex value and offsetting it from the
    zero line, so a page drawing the same arrows needs both parts.

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
