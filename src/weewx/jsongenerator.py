#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate JSON time series for client-side plotting.

This generator is the data-only counterpart to `weewx.imagegenerator`. It reads the same
plot definitions, fetches the same series through `weewx.xtypes.get_series()`, applies the
same unit conversion and label lookup, then writes the result as JSON instead of rendering
it into a PNG.

Because it understands the existing `[ImageGenerator]` syntax, any plot a user has already
defined -- including plots added by hand over the years -- is available as JSON without
touching the configuration.

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

Series are written as two parallel arrays rather than a list of pairs: it is roughly 30%
smaller on the wire and is the shape charting libraries want.
"""

import calendar
import json
import logging
import os
import time

import weeplot.utilities
import weeutil.logger
import weeutil.weeutil
import weewx.imagegenerator
import weewx.reportengine
import weewx.units
import weewx.xtypes
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_bool, to_int, TimeSpan
from weewx.units import ValueTuple

log = logging.getLogger(__name__)

# Reuse the ImageGenerator's helpers rather than duplicating them. Keeping these in one
# place means a fix to the "is this plot empty?" logic benefits both generators.
_get_check_domain = weewx.imagegenerator._get_check_domain
_skip_if_empty = weewx.imagegenerator._skip_if_empty
_skip_this_plot = weewx.imagegenerator._skip_this_plot


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

        # Which section holds the plot definitions?
        #
        # Its own, when it has any. [ImageGenerator] otherwise, so that a skin
        # written before this generator existed works untouched, and so that
        # anyone who wants one definition to serve both the chart and the image
        # gets that by doing nothing.
        #
        # The order matters more than it looks. Defaulting to [ImageGenerator]
        # would mean a skin with no images at all still keeps a section named
        # after them, and that the JSON generator is defined in terms of the one
        # it was meant to stand beside. This way round it stands on its own, and
        # the fall-back is what serves the existing skins rather than the rule.
        self.gen_dict = self.skin_dict.get('JSONGenerator', {})
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
        indent = self.gen_dict.get('json_indent')
        indent = to_int(indent) if indent not in (None, '', 'None', 'none') else None

        # Collected for the manifest, so a client knows what exists without having to
        # probe for it (and without generating a 404 for every sensor this station
        # happens not to have).
        manifest = []
        manifest_root = None
        nskipped = 0
        # How long each time span covers, straight from the plot definitions. A client
        # that lays out its own periods needs this, or 'time_length' would only ever
        # affect the PNGs and the two would drift apart.
        span_lengths = {}

        # A plot that is skipped as unchanged still belongs in the manifest. Read the
        # previous one once, rather than opening every skipped file to rebuild its
        # entry.
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
                # over: a year plot on daily averages says the same thing at 10:05 as
                # it did at 10:00. Rewriting it anyway costs a database read here and
                # -- for anyone publishing over FTP -- an upload of every file, every
                # cycle. This is the same test the ImageGenerator applies to its PNGs.
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
                    os.makedirs(os.path.dirname(json_file), exist_ok=True)
                    with open(json_file, 'w', encoding='utf-8') as fd:
                        json.dump(payload, fd, indent=indent, ensure_ascii=False,
                                  separators=(',', ':') if indent is None else None)
                    ngen += 1
                    manifest_root = json_root
                    manifest.append({
                        'name': plotname,
                        'group': timespan,
                        'title': ', '.join(s['label'] for s in payload['series']),
                        'unit_label': payload['unit_label'],
                        'obs_types': [s['obs_type'] for s in payload['series']],
                    })
                    span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                        plot_options.get('time_length', 86400)))
                except OSError as e:
                    log.error("Unable to save to file '%s': %s", json_file, e)

        # An index of what was written. Lets a client build its layout up front and
        # fetch each series only when it actually needs it.
        if manifest_root:
            index_file = os.path.join(manifest_root, 'index.json')
            try:
                with open(index_file, 'w', encoding='utf-8') as fd:
                    json.dump({'generated': int(gen_ts or time.time()),
                               'spans': span_lengths,
                               # Whether the PNGs of these plots are being written
                               # at all. A client offering a link to one wants to
                               # know before it points at a file nobody generates.
                               'images': self._images_are_generated(),
                               'plots': manifest},
                              fd, indent=indent, ensure_ascii=False,
                              separators=(',', ':') if indent is None else None)
            except OSError as e:
                log.error("Unable to save to file '%s': %s", index_file, e)

        t2 = time.time()
        if log_success:
            log.info("Generated %d JSON files (%d unchanged) for report %s in %.2f seconds",
                     ngen, nskipped, self.skin_dict['REPORT_NAME'], t2 - t1)

    def gen_archive(self, gen_ts):
        """Write the history per plot group and calendar year, on a fixed grid.

        The per-period files above are snapshots of four fixed windows -- the same four
        the ImageGenerator draws. They cannot answer "show me last March", because that
        window was never rendered.

        The archive covers the whole record instead, split by calendar year. Two things
        follow from that split, and both matter on the small machines WeeWX usually runs
        on:

        - A finished year never changes, so it is written once and then skipped forever.
          A station with fourteen years of data rewrites one file, not fourteen.
        - A client fetches only the years it is actually showing.

        Within a file the grid is regular, so timestamps are implied by `start` and
        `interval` rather than stored, which roughly halves the size.

        A file is rewritten when the data it covers have moved on to another grid slot,
        not when the file reaches a certain age. The two are the same thing while the
        station is running. They part company after a catchup: the file is minutes old
        and hours behind, and an age test says there is nothing to do.

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
        # A second, finer grid over the recent past, written per calendar month. An
        # hourly grid is the right trade over years, but it flattens a single day, and
        # stepping back through days is exactly what the client offers. Thirty days at
        # five minutes costs about what one year at one hour costs, and the client only
        # ever fetches the months it is showing.
        fine_days = to_int(arch_dict.get('fine_days', 0))
        fine_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('fine_resolution', 300)))
        if fine_days and fine_resolution >= resolution:
            # Easily done: in a duration suffix 'm' means months, so '5m' asks for a
            # grid coarser than the one it was meant to refine.
            log.warning("Ignoring fine_days: fine_resolution (%d seconds) is not finer "
                        "than resolution (%d seconds)", fine_resolution, resolution)
            fine_days = 0
        dest_dir = arch_dict.get('dest_dir',
                                 os.path.join(self.gen_dict.get('json_dest_dir', 'data'),
                                              'archive'))
        indent = self.gen_dict.get('json_indent')
        indent = to_int(indent) if indent not in (None, '', 'None', 'none') else None
        rounding = arch_dict.get('round', self.gen_dict.get('round', 2))
        rounding = to_int(rounding) if rounding not in (None, '', 'None', 'none') else None

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

        # What the last run covered, so this one can tell what has actually changed.
        # One file, read once, the same way gen_json() reads its manifest.
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

            # Data that reach further back than the last run saw mean an import, and
            # every year has to be built again. 'first_ts' cannot be used for this:
            # under 'max_days' it moves forward on its own as the record grows.
            reimported = previous_first is not None and int(db_first) < previous_first

            # Track the covered span from the data itself, not from what happened to be
            # rewritten this run -- on a second run nothing is rewritten at all.
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

                # How far into this year the data now reach. For a year that has run
                # out this is the end of the year, so it never moves again and the
                # file is written once -- which is what keeps a long-running station
                # cheap. For the current year it advances with the record, and the
                # file is rewritten when it advances into the next grid slot.
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
                    os.makedirs(arch_root, exist_ok=True)
                    with open(out_file, 'w', encoding='utf-8') as fd:
                        json.dump(payload, fd, indent=indent, ensure_ascii=False,
                                  separators=(',', ':') if indent is None else None)
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
                    if os.path.exists(out_file) and was is not None and not reimported                             and was // fine_resolution == covered // fine_resolution:
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
                        os.makedirs(arch_root, exist_ok=True)
                        with open(out_file, 'w', encoding='utf-8') as fd:
                            json.dump(payload, fd, indent=indent, ensure_ascii=False,
                                      separators=(',', ':') if indent is None else None)
                        ngen += 1
                        root = arch_root
                        entry = index.setdefault(group_name, {'years': [], 'covered': {}})
                        entry.setdefault('fine', {})[stamp] = payload['covered']
                    except OSError as e:
                        log.error("Unable to save to file '%s': %s", out_file, e)

        # Sunrise/sunset for the whole record, written once rather than repeated in
        # every group's file. The client shades the night from this when it is showing
        # a window short enough for the bands to mean anything.
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
                    # Keyed by year, so it survives the trip through JSON as strings.
                    'covered': {str(y): c for y, c in entry.get('covered', {}).items()},
                    # Months that also exist on the finer grid.
                    'fine': {str(m): c for m, c in entry.get('fine', {}).items()},
                })
            try:
                with open(os.path.join(root, 'index.json'), 'w', encoding='utf-8') as fd:
                    json.dump({'interval': resolution,
                               'fine_interval': fine_resolution if fine_days else None,
                               'first': int(overall_start) if overall_start else None,
                               'last': int(overall_stop) if overall_stop else None,
                               'groups': groups},
                              fd, indent=indent, ensure_ascii=False,
                              separators=(',', ':') if indent is None else None)
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        if to_bool(search_up(self.gen_dict, 'log_success', True)):
            log.info("Generated %d archive files (%d already current) for report %s "
                     "in %.2f seconds",
                     ngen, nskipped, self.skin_dict['REPORT_NAME'], time.time() - t1)

    def _images_are_generated(self):
        """Is the ImageGenerator in this report's generator list?

        The skin says once, in [Generators], whether it draws images. Anything
        that needs to know reads it from here rather than being told a second
        time in a second place, where the two can disagree.
        """
        try:
            generators = self.skin_dict['Generators']['generator_list']
        except (KeyError, TypeError):
            return False
        # The dots matter: 'summaryimage.SummaryImageGenerator' contains the
        # word too, and draws one picture of the current readings rather than a
        # plot per chart.
        return any('.imagegenerator.' in str(g).lower()
                   for g in weeutil.weeutil.option_as_list(generators))

    def _read_archive_index(self, dest_dir):
        """What the previous run wrote, from the index it left behind.

        Returns:
            tuple: A dict of {group: {year: covered}}, the same for the finer months as
                {group: {'YYYY-MM': covered}}, and the earliest reading the last run
                knew about (None if there was no usable index).
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
            # No index, or one this version cannot read. Everything gets rebuilt,
            # which is the safe direction to fail in.
            return {}, {}, None
        return covered, fine, first

    def _archive_daynight(self, root, first_ts, last_ts, indent):
        """Write sunrise/sunset transitions, one file per calendar year.

        These depend only on the location, so they are the same for every plot group and
        are written once instead of being repeated in each. Like the data files, a
        finished year is written once and then left alone.
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
                with open(out_file, 'w', encoding='utf-8') as fd:
                    json.dump(dn, fd, indent=indent, ensure_ascii=False,
                              separators=(',', ':') if indent is None else None)
            except Exception as e:
                log.warning("Could not write day/night file for %d: %s", year, e)

    def _archive_year(self, plot_section, plot_options, year_span, resolution,
                      aggregate_type, rounding, group_name, first_ts, last_ts):
        """Build the payload for one plot group over one calendar year.

        Returns:
            dict|None: The payload, or None if this year holds nothing worth writing.
        """
        # Clip to the data we actually have, then snap to the grid, so that every series
        # of every year lands on the same instants and the client can stitch years
        # together without resampling.
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

            # A vector series has no meaning on a shared grid of scalars. The
            # per-period files still carry it.
            if line_options.get('plot_type', 'line').lower() == 'vector':
                continue

            # The plot's own aggregate_type wins, but 'none' is how a skin asks for raw
            # samples -- not an option on a fixed grid, so fall back to the default.
            agg = line_options.get('aggregate_type')
            if agg in (None, '', 'None', 'none'):
                agg = aggregate_type
            if var_type in ('rain', 'ET', 'lightning_strike_count', 'hail', 'snow'):
                agg = 'sum'
            elif var_type in ('windDir', 'windGustDir'):
                # Averaging compass bearings is meaningless: 350 deg and 10 deg average
                # to 180, due south, when the wind never blew from there. WeeWX has
                # 'vecdir' for this, which resolves the vectors first -- but it works
                # off the 'wind' daily summary, not 'windDir'.
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

            # Place the values on the grid. get_series() skips empty intervals, so the
            # slot has to be computed rather than assumed.
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

        # Fall back to the skin's palette, exactly as the per-period files do.
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
            # The reading this file was built from. What decides whether it has to be
            # written again, rather than how old the file happens to be.
            'covered': min(int(year_span.stop), int(last_ts)),
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }

    def gen_plot_data(self, plotgen_ts, plot_options, plot_dict, plotname):
        """Assemble the data for a single plot.

        Mirrors ImageGenerator.gen_plot(), minus everything to do with drawing.

        Returns:
            dict|None: The payload, or None if the plot has no non-null data and
                skip_if_empty asked us to drop it.
        """
        time_length = weeutil.weeutil.nominal_spans(plot_options.get('time_length', 86400))
        # Snap to the same boundaries the ImageGenerator uses. Taking the window raw
        # would put the JSON and the PNG of the same plot on different axes, and the
        # two would disagree about where a day begins.
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

        rounding = plot_options.get('round', 3)
        rounding = to_int(rounding) if rounding not in (None, '', 'None', 'none') else None

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

            # When aggregating, the ImageGenerator shifts the point into the middle of
            # its interval. Do the same, so both renderings line up.
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

            # Wind vectors arrive as complex numbers (x + yj). Split them into magnitude
            # and compass direction: that is what the vector plot actually draws, and it
            # is far more useful to a client than a raw pair of components.
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
                # Bar width, in seconds, so the client can size the bars correctly.
                entry['bar_width'] = [b - a for a, b in zip(start_vec_t[0], stop_vec_t[0])]
            if plot_type == 'vector':
                # A vector plot draws each reading as an arrow from the zero line, so
                # the client needs the components, not just the magnitude. Handing them
                # over avoids rebuilding them from magnitude and bearing at the far end.
                if components:
                    entry['vector_x'] = _round_seq(components[0], rounding)
                    entry['vector_y'] = _round_seq(components[1], rounding)
                vr = line_options.get('vector_rotate')
                if vr is not None:
                    # Negated, exactly as the ImageGenerator does it. Without the minus
                    # the arrows come out mirrored against the PNG of the same data.
                    entry['vector_rotate'] = -float(vr)
                # The compass rose the PNGs draw in the corner: without it, nothing on
                # the plot says which way the arrows are measured from.
                entry['rose_label'] = self.text_dict.get(
                    'rose_label', plot_options.get('rose_label', 'N'))

            # Last, so that every parallel sequence is filtered along with the values.
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

        # The PNGs shade night-time. Hand the client what it needs to do the same.
        if to_bool(plot_options.get('show_daynight', False)) \
                and to_bool(self.gen_dict.get('include_daynight', True)):
            try:
                dn = _daynight(x_domain.start, x_domain.stop,
                               self.stn_info.latitude_f, self.stn_info.longitude_f)
                if dn:
                    payload['daynight'] = dn
            except Exception as e:
                # Shading is decorative and must never break a report -- but a silent
                # failure here once hid a real bug, so say something.
                log.warning("Could not compute day/night for '%s': %s", plotname, e)

        return payload


def _daynight(start_ts, stop_ts, lat, lon):
    """Sunrise, sunset, and the civil twilight around them.

    `weeutil.weeutil.getDayNightTransitions()` gives the moments the sun crosses the
    horizon, which is what the PNGs shade against. But dusk is not an edge: the light
    fades over the half hour or so of civil twilight, and much longer at high latitude
    in summer. Returning those boundaries as well lets a client draw the real thing
    instead of a step.

    Returns:
        dict|None: 'first' ('day' or 'night' at start_ts), 'transitions' (horizon
            crossings, as before), and 'twilight' (pairs of timestamps bounding each
            dawn and dusk).
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

        # Dawn runs from the start of civil twilight to sunrise, getting lighter;
        # dusk from sunset to the end of civil twilight, getting darker. Saying which
        # is which saves the client from working it out from the crossings.
        if dawn < stop_ts and rise > start_ts:
            twilight.append({'from': dawn, 'to': rise, 'dir': 'dawn'})
        if sets < stop_ts and dusk > start_ts:
            twilight.append({'from': sets, 'to': dusk, 'dir': 'dusk'})

    if first is None and not transitions:
        # Polar day or night: nothing crosses the horizon in this window.
        return None

    transitions.sort()
    twilight.sort(key=lambda b: b['from'])
    return {'first': first or 'day', 'transitions': transitions, 'twilight': twilight}


def _holds_plots(section):
    """Does this section define plots, rather than merely hold settings?

    A time span such as [[day_images]] is a subsection whose own entries are
    subsections: one per plot. Settings like [[Archive]] carry scalars only, so
    counting subsections alone would mistake them for plot definitions.
    """
    try:
        return any(section[name].sections for name in section.sections)
    except (AttributeError, KeyError, TypeError):
        return False


def _yscale(plot_options, series_out):
    """The y axis for this plot, as [min, max, increment].

    The same axis the ImageGenerator would draw: the plot's own 'yscale' fixes
    whichever of the three it names, and weeplot.utilities.scale() fills in the rest
    from the data. Leaving that to the client means a chart disagreeing with the PNG
    of the same plot -- wind direction running to 400 degrees where the image stops
    at 360, or an axis to 5 m/s for wind that never passed 2.3.

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

    A source reporting every ten minutes fills one archive record in ten, and the rest
    hold null for it. Sent as they are, a client draws a line broken in hundreds of
    places, and the file is far larger than the data in it.

    What counts as a gap has to come from the source's own rhythm, not from the width
    of the plot: ten minutes between readings is a break for a station reporting every
    eight seconds and business as usual for one reporting every ten minutes. So the
    usual spacing is measured, and only a run several times longer than that is drawn
    as a gap. `line_gap_fraction` still wins where it is set, for anyone who wants the
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
                # Long enough to be a break in the readings rather than their rhythm.
                # One null says so; the rest of the run would only be noise.
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

    weeplot draws a vector by scaling the complex value and offsetting from the zero
    line; a client doing the same needs the components. Returns None for a series that
    is not complex.

    Returns:
        tuple[list, list]|None: The real and imaginary parts.
    """
    seq = list(seq)
    if not any(isinstance(v, complex) for v in seq):
        return None
    real = [None if v is None else (v.real if isinstance(v, complex) else v) for v in seq]
    imag = [None if v is None else (v.imag if isinstance(v, complex) else 0.0) for v in seq]
    return real, imag


def _split_vectors(seq):
    """Split a possibly-complex sequence into magnitudes and directions.

    WeeWX carries wind vectors as complex numbers, and `Polar` for the already-converted
    form. Anything else is returned unchanged with no directions.

    Returns:
        tuple[list, list|None]: Magnitudes, and compass directions in degrees (or None if
            the series was not a vector series).
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
            # WeeWX's convention: the vector points in the direction the wind is coming
            # from, measured clockwise from north. That is what Polar.from_complex does.
            directions.append(weewx.units.Polar.from_complex(v).dir)
        else:
            magnitudes.append(v)
            directions.append(None)
    return magnitudes, directions


def _normalize_color(color):
    """Normalize a WeeWX color spec to something CSS understands.

    WeeWX accepts '#RRGGBB', '0xBBGGRR' and English names. The first and last are already
    valid CSS; the middle one is byte-swapped and has to be turned around.
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
