#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate JSON time series, for a page that draws its own charts.

The JSON generator is the data-only counterpart to `weewx.imagegenerator`. It reads plot
definitions in the ImageGenerator's syntax and fetches the series through
`weewx.xtypes.get_series()`. It converts units and looks up labels like the
ImageGenerator, but writes JSON instead of a PNG.

Throughout this module, "the page" means whatever reads the JSON files and draws the
charts. In the skins that ship with WeeWX, the page is JavaScript in the browser.

The generator writes into `<HTML_ROOT>/<json_dest_dir>`:

  skin.json    The length of each time span, and the unit table. See gen_skin_json().
  archive/     The readings of each plot group over the whole record, one file per day,
               month or year. See gen_archive().

The Reference Guide documents the options under [JSONGenerator]. The docstring of
_archive_span() shows what an archive file holds.
"""

import bisect
import calendar
import datetime
import json
import logging
import math
import os
import re
import time

import configobj

import weedb
import weeplot.utilities
import weeutil.logger
import weeutil.weeutil
import weewx.accum
import weewx.reportengine
import weewx.units
import weewx.xtypes
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_bool, to_int, TimeSpan
from weewx.imagegenerator import _skip_if_empty

log = logging.getLogger(__name__)

# Three resolution tiers as (kind, grids) tuples. Under 'kind', the index records the newest
# reading of each file, and under 'grids' the grid resolution of each file.
TIERS = (('years', 'year_intervals'), ('months', 'month_intervals'),
         ('days', 'day_intervals'))

# The defaults of the options in [[Archive]]. The Horizon skin.conf sets the same
# values, and a test keeps the two in step. See _archive_settings().
ARCHIVE_DEFAULTS = {
    'years': 2,                    # How many years to keep 'year_resolution'
    'year_resolution': '1h',
    'old_year_resolution': '4h',    # The resolution for files older than the 'years' limit.
    'months': 2,
    'month_resolution': 900,
    'days': 30,
    'day_resolution': 0,
    'budget': 30,
    'extremes': ['windGust', 'windSpeed', 'rainRate', 'UV'],
    'rebuild': 0,
}

# The name of an archive file: the plot group, then the year, the month or the day the
# file covers. See _parse_archive_name().
_ARCHIVE_NAME = re.compile(r'^(.+)-(\d{4})(-\d{2})?(-\d{2})?\.json$')


class JSONGenerator(weewx.reportengine.ReportGenerator):
    """Generate JSON time series from plot definitions."""

    def __init__(self, config_dict,
                 skin_dict,
                 gen_ts,
                 first_run,
                 stn_info,
                 record=None,
                 stop_event=None):
        super().__init__(config_dict, skin_dict, gen_ts, first_run, stn_info, record, stop_event)
        self.converter = None
        self.data_root = None
        self.formatter = None
        self.gen_dict = None
        self.generic_dict = None
        self.plot_dict = None
        self.text_dict = None

    def run(self):
        self.setup()
        if not self.plot_dict:
            # No plot definitions found. Return.
            return
        self.gen_skin_json()
        self.gen_archive(self.gen_ts)

    def setup(self):
        # Generic labels, such as "Outside Temperature":
        try:
            self.generic_dict = self.skin_dict['Labels']['Generic']
        except KeyError:
            self.generic_dict = {}
        # Translated text strings:
        self.text_dict = self.skin_dict.get('Texts', {})

        # gen_dict must be a Section in order for function 'search_up()` to work.
        self.skin_dict.setdefault('JSONGenerator', configobj.ConfigObj())
        self.gen_dict = self.skin_dict['JSONGenerator']
        self.data_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict.get('HTML_ROOT', 'public_html'),
                                      self.gen_dict.get('json_dest_dir', 'data'))

        # Search for plot definitions. Try [JSONGenerator] first, then [ImageGenerator].
        self.plot_dict = configobj.ConfigObj()
        for name in ('JSONGenerator', 'ImageGenerator'):
            section = self.skin_dict.get(name)
            if section is not None and _holds_plots(section):
                self.plot_dict = section
                break
        else:
            log.info("No plot definitions in [JSONGenerator] or [ImageGenerator]. "
                     "No JSON written.")

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

    def gen_skin_json(self):
        """Write skin.json, which holds the length of each time span and the unit table.

        The page reads skin.json before it draws a chart. Nothing in skin.json comes
        from the database, and the configuration changes only with a restart of
        weewxd. So skin.json is written on the first run only, or when it is missing.
        """
        skin_file = os.path.join(self.data_root, 'skin.json')
        if not self.first_run and os.path.exists(skin_file):
            return

        # span_lengths maps each time span to its 'time_length' in seconds, e.g.,
        # 86400 for [[day_images]]. The page sets the x axis width from span_lengths.
        # A section without plots, e.g., [[Archive]], is not a time span.
        span_lengths = {}
        for timespan in self.plot_dict.sections:
            if self.plot_dict[timespan].sections:
                span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                    search_up(self.plot_dict[timespan], 'time_length', 86400)))

        try:
            _write_json(skin_file,
                        {'spans': span_lengths,
                         # Each archive file holds readings in one unit. The unit
                         # table lets the page convert them to any other.
                         'units': _unit_choices(self.formatter, self.converter)})
        except OSError as e:
            log.error("Unable to save to file '%s': %s", skin_file, e)

    def gen_archive(self, gen_ts):
        """Write the whole record, one file per plot group and span.

        The spans are calendar years, and optionally months (the month tier) and days
        (the day tier). A span that has ended never changes, so its file is written
        once and then skipped. The page fetches only the spans it shows. See "The JSON
        generator" in the Customization Guide for the format and the cost.

        Args:
            gen_ts (int | None): The time the report is being run for.
        """
        arch_dict = self.gen_dict.get('Archive', {})

        t1 = time.time()

        opts = _archive_settings(arch_dict)
        rounding = to_int(self.gen_dict.get('round', 2))
        # The page reads the archive from 'archive' below the JSON directory.
        arch_root = os.path.join(self.data_root, 'archive')

        # The plot groups are the plots of [[day_images]], named without the prefix
        # 'day', e.g., 'tempdew' for 'daytempdew'. 'plot_groups' in skin.conf uses the
        # same names.
        try:
            group_dict = self.plot_dict['day_images']
        except KeyError:
            log.error("Archive: no section [[day_images]]. Skipped.")
            return

        # What this run has done so far, for the budget and for the log line at the
        # end.
        counters = {'written': 0, 'skipped': 0, 'extended': 0, 'deferred': 0,
                    'spent': 0.0, 'first': None, 'last': None, 'daynight': False}

        # The archive index the last run wrote, checked against the files on disk. The
        # index this run writes starts from it, and every file written updates it.
        try:
            on_disk = os.listdir(arch_root)
        except OSError:
            on_disk = []
        known = self._read_archive_index(arch_root)
        self._reconcile_index(known, arch_root, on_disk)
        index = _index_of(known)
        previous_first = known['first']
        now_ts = int(gen_ts or time.time())
        rebuilding = _rebuild_due(known['rebuilt'], now_ts, opts['rebuild'])

        def write_index():
            """Write the archive index.json for the files that exist so far.

            Called after each pass. The page finds the archive files through
            index.json, so it cannot see a file that index.json does not name.
            """
            groups = []
            for name in sorted(index):
                entry = index[name]
                if not any(entry[kind] for kind, _ in TIERS):
                    # The group has no file in any tier. Naming it would send the
                    # page after a 404.
                    continue
                # The grid is recorded per file, because files written under
                # different settings differ.
                groups.append({'name': name,
                               'title': entry['title'] or name,
                               'unit_label': entry['unit_label'] or '',
                               **{key: entry[key] for tier in TIERS for key in tier}})
            try:
                _write_json(os.path.join(arch_root, 'index.json'),
                            {'first': counters['first'],
                             'last': counters['last'],
                             # When the files were last rebuilt in full. The next
                             # run passes 'rebuilt' to _rebuild_due().
                             'rebuilt': now_ts if rebuilding else known['rebuilt'],
                             'groups': groups})
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        # Two passes over the groups: first the day tier of every group, then the other
        # tiers. The index is written after each pass. So a station building its
        # history has the day view at once, before the years behind it are done.
        for pass_name in ('days', 'rest'):
            for plotname in group_dict.sections:
                if self.stop_event and self.stop_event.is_set():
                    return

                plot_options = accumulateLeaves(group_dict[plotname])
                db_manager = self.db_binder.get_manager(plot_options['data_binding'])

                first_ts = db_manager.firstGoodStamp()
                last_ts = gen_ts or db_manager.lastGoodStamp()
                if not first_ts or not last_ts:
                    continue

                # If the database reaches further back than last run, history was
                # imported, and every file has to be built again.
                reimported = previous_first is not None and int(first_ts) < previous_first

                # Take 'first' and 'last' from the database, not from the files written this
                # run. A second run in the same minute writes no file.
                if counters['first'] is None or first_ts < counters['first']:
                    counters['first'] = int(first_ts)
                if counters['last'] is None or last_ts > counters['last']:
                    counters['last'] = int(last_ts)

                group_name = plotname[len('day'):] if plotname.startswith('day') else plotname

                this_year = time.localtime(int(last_ts)).tm_year

                def write_tier(spans, kind, stamp_of, grid_of, tier_from, metered=True):
                    """Write the files of one tier for the current plot group.

                    The tiers differ in how they cut the record into files and in the
                    grid. The arguments supply those differences. Skipping, extending and
                    recording work the same for every tier.

                    Args:
                        spans (Iterable[weeutil.weeutil.TimeSpan]): The spans to write,
                            one file each.
                        kind (str): Which tier, as the index names it, e.g., 'days'.
                        stamp_of (Callable[[weeutil.weeutil.TimeSpan], str]): Called as
                            ``stamp_of(span)``. Returns the index stamp for a span, e.g.,
                            '2026-07'.
                        grid_of (Callable[[str, int | None], int]): Called as
                            ``grid_of(stamp, existing)``. Returns the grid, in seconds, for
                            a stamp. ``existing`` is the grid recorded for that stamp in the
                            previous index, or None if there is none.
                        tier_from (int): The oldest instant this tier reaches.
                        metered (bool): Whether the budget applies. The day tier is not
                            metered.
                    """
                    grids = dict(TIERS)[kind]
                    # Newest span first. A run that stops early then leaves the oldest
                    # spans unbuilt, not this year.
                    for span in reversed(list(spans)):
                        # A file deferred by the budget is written by a later report.
                        if metered and opts['budget'] and counters['spent'] >= opts['budget']:
                            counters['deferred'] += 1
                            continue
                        stamp = stamp_of(span)
                        out_file = os.path.join(arch_root, '%s-%s.json' % (group_name, stamp))
                        grid = grid_of(stamp, known[grids].get(group_name, {}).get(stamp))
                        entry = index.setdefault(group_name, _new_entry())

                        # 'newest' is the newest reading the file holds. For a finished
                        # span it is the end of the span, so the file is written once. For
                        # the span in progress, 'newest' advances with the database. The
                        # file is rewritten when 'newest' reaches the next slot. A test on
                        # the file's age would miss a catch-up, where the file is minutes
                        # old but hours behind.
                        newest = min(int(span.stop), int(last_ts))
                        was = known[kind].get(group_name, {}).get(stamp)
                        if os.path.exists(out_file) and was is not None and not reimported \
                                and was // grid == newest // grid:
                            counters['skipped'] += 1
                            continue

                        # Passing the file on disk as 'carry' means only the slots from
                        # its newest reading on are calculated. A rebuild or an import
                        # calculates the whole span instead.
                        carry = None if rebuilding or reimported or was is None \
                            else _read_archive_file(out_file)
                        if carry is not None:
                            counters['extended'] += 1

                        started = time.time()
                        payload = self._archive_span(
                            group_dict[plotname], plot_options, span, grid, rounding,
                            group_name, tier_from, last_ts, carry, opts['extremes'])
                        counters['spent'] += time.time() - started
                        if payload is None:
                            continue
                        try:
                            _write_json(out_file, payload)
                            counters['written'] += 1
                            entry[kind][stamp] = payload['newest']
                            entry[grids][stamp] = grid
                            entry['title'] = ', '.join(s['label'] for s in payload['series'])
                            entry['unit_label'] = payload['unit_label']
                        except OSError as e:
                            log.error("Unable to save to file '%s': %s", out_file, e)

                if opts['days'] and pass_name == 'days':
                    # The day tier is exempt from the budget. It is cheap, and a report
                    # that deferred it would leave the page without today. It is also the
                    # only tier whose old files are deleted. See _drop_old_days().
                    grid = opts['day_resolution'] or _archive_interval(db_manager, last_ts)
                    days_from = max(int(first_ts),
                                    weeutil.weeutil.startOfDay(int(last_ts))
                                    - (opts['days'] - 1) * 86400)
                    day_spans = list(weeutil.weeutil.genDaySpans(days_from, last_ts))
                    day_stamp = lambda span: time.strftime('%Y-%m-%d',
                                                           time.localtime(span.start))
                    write_tier(day_spans, 'days', day_stamp, lambda stamp, existing: grid,
                               days_from, metered=False)
                    _drop_old_days(arch_root, on_disk, group_name,
                                   {day_stamp(span) for span in day_spans},
                                   index.get(group_name))

                if opts['months'] and pass_name == 'rest':
                    months_from = _months_back(int(last_ts), opts['months'], int(first_ts))
                    write_tier(
                        weeutil.weeutil.genMonthSpans(months_from, last_ts), 'months',
                        lambda span: time.strftime('%Y-%m', time.localtime(span.start)),
                        lambda stamp, existing: opts['month_resolution'],
                        months_from)

                if pass_name == 'rest':
                    write_tier(
                        weeutil.weeutil.genYearSpans(first_ts, last_ts), 'years',
                        lambda span: time.strftime('%Y', time.localtime(span.start)),
                        lambda year, existing: _year_grid(int(year), this_year, opts['years'],
                                                          opts['year_resolution'],
                                                          opts['old_year_resolution'],
                                                          existing),
                        first_ts)

            # Write the index after each pass that has anything to show.
            if any(entry[kind] for entry in index.values() for kind, _ in TIERS):
                # Write the day/night files with the first index, so the shading
                # appears with the first charts. Without the day tier, that is the
                # second pass.
                if not counters['daynight'] \
                        and to_bool(self.gen_dict.get('include_daynight', True)):
                    counters['daynight'] = True
                    self._archive_daynight(arch_root, counters['first'], counters['last'])
                write_index()

        if to_bool(search_up(self.gen_dict, 'log_success', True)):
            log.info("Generated %d archive files (%d extended, %d already current) "
                     "for report %s in %.2f seconds",
                     counters['written'], counters['extended'], counters['skipped'],
                     self.skin_dict['REPORT_NAME'], time.time() - t1)

    @staticmethod
    def _read_archive_index(arch_root):
        """Read the archive index.json that the previous run wrote.

        A file the index names need not be calculated again, whatever the current
        settings say.

        Args:
            arch_root (str): The archive directory.

        Returns:
            dict: With keys

                years:           {group: {year: timestamp}}, the newest reading each
                                 year's file holds
                months:          the same for the months, keyed 'YYYY-MM'
                days:            the same for the days, keyed 'YYYY-MM-DD'
                year_intervals:  {group: {year: seconds}}, the grid each year's file
                                 is on. Files can differ, because a file is never
                                 rewritten just to coarsen it.
                month_intervals: the same for the months
                day_intervals:   the same for the days
                labels:          {group: (title, unit_label)}
                first:           the oldest reading in the database when the last
                                 run read it, or None if there was no index
                rebuilt:         when the files were last rebuilt in full, or None
        """
        path = os.path.join(arch_root, 'index.json')
        known = _empty_index()
        try:
            with open(path, encoding='utf-8') as fd:
                index = json.load(fd)
            known['first'] = to_int(index.get('first'))
            known['rebuilt'] = to_int(index.get('rebuilt'))
            for group in index.get('groups', []):
                name = group['name']
                # A run that writes no file of a group still needs the group's title
                # and unit_label for the index, so keep them from the old index.
                known['labels'][name] = (group.get('title'), group.get('unit_label'))
                for key in (key for tier in TIERS for key in tier):
                    stamps = {stamp: int(value)
                              for stamp, value in (group.get(key) or {}).items() if value}
                    if stamps:
                        known[key][name] = stamps
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # No index, or one this version cannot read. Start from an empty record,
            # which _reconcile_index() then fills from the files on disk.
            return _empty_index()
        return known

    @staticmethod
    def _reconcile_index(known, arch_root, on_disk):
        """Correct the archive index, in place, to match the files on disk.

        The page cannot see a file the index does not name. A name without a file
        sends the page after a 404. If index.json is lost, the files restore it, and
        nothing has to be calculated again. Only files missing from the index are
        opened.

        Args:
            known (dict[str, dict[str, Any]]): The index as it was read.
            arch_root (str): The archive directory.
            on_disk (list[str]): The names of the files in it.
        """
        seen = {kind: set() for kind, _ in TIERS}
        for filename in on_disk:
            parsed = _parse_archive_name(filename)
            if parsed is None or parsed[0] == 'daynight':
                continue
            group, kind, key = parsed
            grids = dict(TIERS)[kind]
            seen[kind].add((group, key))
            if key in known[kind].get(group, {}):
                continue
            # The index does not name this file. Read 'newest' and 'interval' from it.
            payload = _read_archive_file(os.path.join(arch_root, filename))
            if not payload:
                continue
            newest = to_int(payload.get('newest'))
            interval = to_int(payload.get('interval'))
            if newest is None or not interval:
                continue
            known[kind].setdefault(group, {})[key] = newest
            known[grids].setdefault(group, {})[key] = interval

        # Drop what the index names but the directory does not hold.
        for kind, grids in TIERS:
            for group in list(known[kind]):
                for key in list(known[kind][group]):
                    if (group, key) not in seen[kind]:
                        known[kind][group].pop(key, None)
                        known[grids].get(group, {}).pop(key, None)

    def _archive_daynight(self, root, first_ts, last_ts):
        """Write sunrise and sunset times, one file per calendar year.

        Sunrise and sunset depend only on the station's location, so one file serves
        every plot group. A year that has ended is written once, like the archive
        files.

        Args:
            root (str): The archive directory.
            first_ts (int): The oldest reading in the database.
            last_ts (int): The newest reading in it.
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
                _write_json(out_file, dn)
            except Exception as e:
                log.warning("Could not write day/night file for %d: %s", year, e)

    def _archive_span(self, plot_section, plot_options, span, resolution, rounding,
                      group_name, first_ts, last_ts, previous=None, extrema=()):
        """Build the contents of one archive file: one plot group, one span.

        Every tier builds its files here. A day, a month and a year differ only in
        length and grid.

        The result holds no timestamps. `values[i]` is at `start + i * interval`, for
        `count` slots. A null is a slot without a reading.

        Args:
            plot_section (configobj.Section): The plot's section, holding one
                subsection per line.
            plot_options (dict[str, Any]): The options that apply to it.
            span (weeutil.weeutil.TimeSpan): The span the file covers.
            resolution (int): The grid it is written on, in seconds.
            rounding (int|None): Decimal places, or None to leave them alone.
            group_name (str): The plot group, which the file is named after.
            first_ts (int): The oldest reading in the database.
            last_ts (int): The newest reading in it.
            previous (dict[str, Any]|None): The file this one replaces, as read back
                from disk. A series the file already holds, on the same grid, is
                calculated only from the slot of the file's newest reading on.
            extrema (set[str]|tuple[str, ...]): The observation types that also
                carry the lowest and highest reading in each slot.

        Returns:
            dict|None: The file's contents, or None if the span holds nothing worth
                writing. For a temperature group over 2025, on an hourly grid::

                    {'name': 'tempdew', 'start': 1735725600, 'interval': 3600,
                     'count': 8760, 'newest': 1767261599,
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
        # Round 'stop' up to a multiple of 'resolution'. Rounding down and adding one
        # step would add a slot whenever 'hi' is on a boundary, i.e., for every
        # finished day. No later run fills that slot, because 'newest' stays the same
        # and the file is skipped. The instant belongs to the next file anyway.
        stop = int(-(-hi // resolution) * resolution)
        slots = int((stop - start) / resolution)
        if slots < 2:
            return None

        # A file on another grid, or cut from another span, cannot be extended.
        if previous is not None and not _extends(previous, start, resolution, slots):
            previous = None
        old_series = {}
        if previous is not None:
            old_series = {(s.get('obs_type'), s.get('aggregate_type')): s
                          for s in previous['series']}

        series_out = []
        unit = unit_label = None
        for line_name in plot_section.sections:
            line = self._line_spec(plot_section[line_name], line_name, resolution)
            old = old_series.get((line['var_type'], line['agg']))
            entry = self._archive_series(line, plot_options, start, stop, slots,
                                         resolution, rounding, extrema, old, previous)
            if entry is None:
                continue
            entry_unit = entry.pop('unit')
            if entry_unit is not None:
                unit = entry_unit
                unit_label = line['options'].get(
                    'y_label', self.formatter.get_label_string(entry_unit))
            series_out.append(entry)

        if not series_out:
            return None
        # A span without new readings reports no unit. The file then keeps its own.
        if unit is None and previous is not None:
            unit, unit_label = previous.get('unit'), previous.get('unit_label')

        # chart_line_colors applies to every series that sets no color of its own.
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
            'newest': min(int(span.stop), int(last_ts)),
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }

    def _archive_series(self, line, plot_options, start, stop, slots, resolution,
                        rounding, extrema, old, previous):
        """Build one series of an archive file.

        The readings of the span are read once, and sorted into the slots in Python.
        A query per slot costs thousands of queries for a year.

        Args:
            line (dict[str, Any]): The line, as _line_spec() returns it.
            plot_options (dict[str, Any]): The options of the plot the line belongs to.
            start (int): The first instant of the file.
            stop (int): The end of the file.
            slots (int): How many slots the file holds.
            resolution (int): The grid of the file, in seconds.
            rounding (int|None): Decimal places, or None to leave them alone.
            extrema (set[str]|tuple[str, ...]): The observation types that also carry
                the lowest and highest reading in each slot.
            old (dict[str, Any]|None): The same series in the file on disk, or None.
            previous (dict[str, Any]|None): The file on disk, if it is being extended.

        Returns:
            dict|None: The series, with its unit under 'unit', which the caller takes
                out again. None if the series holds no reading.
        """
        mgr = self.db_binder.get_manager(line['options']['data_binding'])
        # Many skins plot sensors a station lacks. One query that stops at the first
        # reading saves reading a whole year of nothing, on every report.
        if previous is None and _skip_if_empty(mgr, line['data_type'],
                                               TimeSpan(start, stop)):
            return None
        begins, ends = _intervals(start, stop, line['step'])

        # The interval that holds the newest reading of the file on disk may have filled
        # up since. So it is calculated again, together with every interval after it.
        first = bisect.bisect_left(ends, previous['newest']) if previous is not None else 0
        since = begins[first] if first < len(begins) else stop
        keep = int((since - start) // resolution)

        def new_grid(key):
            carried = old.get(key) if old is not None else None
            if carried is None:
                return [None] * slots
            # Clear the slots from 'keep' on, so a slot without a new reading does not
            # keep its old value.
            return list(carried[:keep]) + [None] * (slots - keep)

        def fill(grid, pairs):
            for begin, val in pairs:
                slot = int((begin - start) // resolution)
                if val is not None and 0 <= slot < slots:
                    grid[slot] = round(val, rounding) if rounding is not None else val
            return grid

        read = self._read_slots(line, plot_options, mgr, TimeSpan(since, stop), begins,
                                ends, first)
        if read is None:
            return None
        unit, pairs, buckets = read
        empty = all(val is None for _, val in pairs)
        if old is None and empty:
            return None
        if previous is not None and (
                old is None or unit is not None and unit != previous.get('unit', unit)):
            # A series the file on disk lacks, e.g., a new sensor, or a unit that has
            # changed since the file was written: calculate the whole span.
            return self._archive_series(line, plot_options, start, stop, slots,
                                        resolution, rounding, extrema, None, None)

        entry = {
            'obs_type': line['var_type'],
            'label': line['label'],
            'aggregate_type': line['agg'],
            'unit': unit,
        }
        if line['step'] != resolution:
            # The readings sit every nth slot. The page needs aggregate_interval to
            # draw each bar n slots wide.
            entry['aggregate_interval'] = line['step']
        if line['color']:
            entry['color'] = _normalize_color(line['color'])
        if line['plot_type'] == 'bar':
            entry['plot_type'] = 'bar'

        values = [val for _, val in pairs]
        components = _vector_components(values) if line['plot_type'] == 'vector' else None
        if components:
            # The speed goes in 'values', so a reader that knows nothing about vectors
            # still draws a line. The legend shows the bearing, and the page draws the
            # arrows from the components.
            speeds, bearings = _split_vectors(values)
            instants = [begin for begin, _ in pairs]
            entry['values'] = fill(new_grid('values'), zip(instants, speeds))
            entry['vector_x'] = fill(new_grid('vector_x'), zip(instants, components[0]))
            entry['vector_y'] = fill(new_grid('vector_y'), zip(instants, components[1]))
            if bearings is not None:
                entry['directions'] = fill(new_grid('directions'),
                                           zip(instants, bearings))
            entry['plot_type'] = 'vector'
            if line['rotate'] is not None:
                entry['vector_rotate'] = -float(line['rotate'])
        else:
            entry['values'] = fill(new_grid('values'), pairs)

        # The lowest and highest reading per slot, for the types named in 'extremes'.
        # They come from the readings already read, so they cost no query.
        if buckets is not None and line['var_type'] in extrema \
                and line['agg'] not in ('min', 'max', 'vecdir') and not components:
            if line['step'] != resolution:
                slot_begins, slot_ends = _intervals(start, stop, resolution)
                buckets = _bucket(slot_begins, slot_ends,
                                  bisect.bisect_left(slot_ends, since), *buckets[1])
            else:
                slot_begins = begins
            for which in ('min', 'max'):
                entry[which] = fill(new_grid(which),
                                    ((slot_begins[i], _reduce(which, vals, weights))
                                     for i, (vals, weights) in buckets[0].items()))
        return entry

    def _line_spec(self, line_section, line_name, resolution):
        """Read the options of one line of a plot.

        Args:
            line_section (configobj.Section): The line's section, e.g., [[[[outTemp]]]].
            line_name (str): The name of the section.
            resolution (int): The grid of the file, in seconds.

        Returns:
            dict: 'var_type', 'agg', 'step', 'plot_type', 'label', 'color', 'rotate',
                all the line's 'options', and the 'data_type' as the skin names it,
                e.g., 'windDir' where 'var_type' is 'wind'.
        """
        options = accumulateLeaves(line_section)
        var_type = options.get('data_type', line_name)
        plot_type = options.get('plot_type', 'line').lower()

        # The line's own aggregate_type wins. 'none' asks for raw samples, which do not
        # fit a fixed grid, so average.
        agg = options.get('aggregate_type')
        if agg in (None, '', 'None', 'none'):
            agg = 'avg'
        # Sum the types whose accumulator extractor is 'sum', e.g., 'rain', 'ET' and
        # 'windrun'. Reading accum_dict instead of a list here also sums the types a
        # station adds under [Accumulator].
        if weewx.accum.accum_dict.get(var_type, {}).get('extractor') == 'sum':
            agg = 'sum'
        elif var_type in ('windDir', 'windGustDir'):
            # The arithmetic mean of 350 and 10 degrees is 180, due south. 'vecdir'
            # averages the vectors and takes their bearing instead.
            var_type, agg = 'wind', 'vecdir'

        # A bar's aggregate_interval is part of its meaning: an hourly rain total
        # differs from sixty one-minute totals. So a bar asking for an interval coarser
        # than the grid gets it, with a reading every nth slot. Lines keep the grid.
        # On a line, aggregate_interval only smooths the drawing, and honouring it
        # would leave most slots of a fine grid empty.
        step = resolution
        asked = to_int(weeutil.weeutil.nominal_spans(options.get('aggregate_interval')))
        if asked and asked > resolution and plot_type == 'bar':
            step = asked

        label = options.get('label')
        label = self.text_dict.get(label, label) if label \
            else self.generic_dict.get(var_type, var_type)

        return {'var_type': var_type, 'agg': agg, 'step': step, 'plot_type': plot_type,
                'label': label, 'color': options.get('color'),
                'rotate': options.get('vector_rotate'), 'options': options,
                'data_type': options.get('data_type', line_name)}

    def _read_slots(self, line, plot_options, mgr, span, begins, ends, first):
        """Read one line over a span, and reduce it to one value per interval.

        Args:
            line (dict[str, Any]): The line, as _line_spec() returns it.
            plot_options (dict[str, Any]): The options of the plot the line belongs to.
            mgr (weewx.manager.Manager): The open database.
            span (weeutil.weeutil.TimeSpan): The span to read.
            begins (list[int]): Where each interval of the file begins.
            ends (list[int]): Where each interval ends.
            first (int): The index of the first interval inside the span.

        Returns:
            tuple|None: A three-way tuple (unit, pairs, buckets). 'pairs' holds
                (begin, value) for each interval with a value. 'buckets' is a two-way
                tuple of the readings per interval and the readings themselves, for
                the extremes, or None where the readings were not read one by one.
                None if the database knows neither the type nor the aggregation.
        """
        options = dict(line['options'])
        options.pop('aggregate_type', None)
        options.pop('aggregate_interval', None)

        if line['agg'] in _RAW_AGGREGATES:
            # 'vecdir' takes the bearing of the vector sum, so it reads the vectors.
            read_type = 'windvec' if line['agg'] == 'vecdir' else line['var_type']
            try:
                start_vec, stop_vec, data_vec = weewx.xtypes.get_series(
                    read_type, span, mgr, **options)
            except (weewx.UnknownType, weewx.UnknownAggregation):
                pass
            else:
                if line['agg'] == 'vecdir':
                    # A bearing does not depend on the unit of the speed.
                    unit = self.converter.getTargetUnit('wind', 'vecdir')[0]
                    values = data_vec[0]
                else:
                    unit, values = self._convert(data_vec, plot_options)
                # 'vecdir' weighs each reading by its archive interval, as the database
                # does.
                weights = [b - a for a, b in zip(start_vec[0], stop_vec[0])]
                readings = (stop_vec[0], values, weights)
                per_interval = _bucket(begins, ends, first, *readings)
                pairs = [(begins[i], _reduce(line['agg'], vals, wts))
                         for i, (vals, wts) in sorted(per_interval.items())]
                return unit, pairs, (per_interval, readings)

        # An aggregation that has no counterpart here, or a type that exists only as an
        # aggregate: one query per interval, as the ImageGenerator does it.
        try:
            start_vec, _, data_vec = weewx.xtypes.get_series(
                line['var_type'], span, mgr, aggregate_type=line['agg'],
                aggregate_interval=line['step'], **options)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            return None
        unit, values = self._convert(data_vec, plot_options)
        return unit, list(zip(start_vec[0], values)), None

    def _convert(self, data_vec, plot_options):
        """Convert a series into the unit of the plot, or else of the report.

        Returns:
            tuple[str|None, list]: A two-way tuple (unit, values).
        """
        if plot_options.get('unit'):
            conv = weewx.units.convert(data_vec, plot_options['unit'])
        else:
            conv = self.converter.convert(data_vec)
        return conv[1], conv[0]


def _linear(convert, from_unit, to_unit):
    """Return the factor and offset that convert from_unit into to_unit.

    weewx.units converts with a function per pair of units, which the page cannot
    call. So the page gets the numbers instead.

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
    # The values at 0 and at 1 give the offset and the factor. The value at 10
    # rejects a conversion that is not linear, instead of approximating it.
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


def _unit_choices(formatter, converter):
    """Build the unit table that lets the page show readings in another unit.

    The archive files hold readings in the skin's units. To offer Fahrenheit next to
    Celsius, the page needs each type's unit group, each system's unit for the group,
    and the conversions between units. The unit table goes into skin.json.

    Args:
        formatter (weewx.units.Formatter): The formatter the report was rendered with.
        converter (weewx.units.Converter): The converter it was rendered with.

    Returns:
        dict: Six keys. 'groups' maps an observation type to its unit group.
            'systems' maps a system name to the unit it uses for each group.
            'report' maps each group to the unit the report renders it in.
            'convert' maps a unit to each unit it converts to, as [factor, offset].
            'labels' and 'formats' give each unit's label and number format, so the
            page writes "18.5 °C" the way the server would.
    """
    # Every unit system WeeWX knows, with the unit it uses for each group.
    by_system = {}
    for unit_system in weewx.units.std_groups:
        name = weewx.units.unit_nicknames[unit_system]
        by_system[name] = dict(weewx.units.std_groups[unit_system])

    # 'report' holds the units the report renders in. The page needs them for the
    # readings it fetches itself, e.g., the forecast, which arrives in Celsius.
    # Without 'report', "Default" on the page would mean metric, not the skin's units.
    report = dict(converter.group_unit_dict)

    # The page can switch to any unit system, so 'wanted' holds every unit of every
    # system, and the units of the report.
    wanted = {unit for table in by_system.values() for unit in table.values()}
    wanted.update(report.values())

    # Iterate over weewx.units.conversionDict, rather than over every pair of units
    # in 'wanted'. Asking weewx.units.convert() for a pair it cannot convert logs a
    # DEBUG line, and most pairs cannot be converted.
    #
    # The Walter and Lieth diagram on the climate page is always drawn in degree_C and
    # mm, because its 2:1 ratio is defined in those units. On a US station the
    # readings arrive in degree_F and inch. So 'convert' must carry the rows from
    # those units to metric, whatever units the rest of the page shows.
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

    return {
        'groups': dict(weewx.units.obs_group_dict),
        'systems': by_system,
        'report': report,
        'convert': convert,
        'labels': labels,
        'formats': formats
    }


def _write_json(path, payload):
    """Write one JSON file atomically and compactly, so a reader never sees half of it.

    A browser may fetch a file while it is being written. Half an index.json does not
    parse, and the page then draws nothing until the next poll.

    Args:
        path (str): Where to write the file.
        payload (dict[str, Any]): What to write.
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    # os.replace() is atomic only within one filesystem, so the temporary file sits
    # beside the target.
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fd:
        json.dump(payload, fd, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def _new_entry():
    """A blank index entry for one plot group."""
    return {'title': None, 'unit_label': None,
            **{key: {} for tier in TIERS for key in tier}}


def _empty_index():
    """An archive index that names no file."""
    return {'first': None, 'rebuilt': None, 'labels': {},
            **{key: {} for tier in TIERS for key in tier}}


def _archive_settings(arch_dict):
    """Read the options of [[Archive]], taking ARCHIVE_DEFAULTS for those not set.

    Args:
        arch_dict (dict): The section [[Archive]], or {} if there is none.

    Returns:
        dict: The keys of ARCHIVE_DEFAULTS. Durations are in seconds, counts are int,
            and 'extremes' is a set.
    """

    def get(name):
        return arch_dict.get(name, ARCHIVE_DEFAULTS[name])

    def seconds(name):
        return to_int(weeutil.weeutil.nominal_spans(get(name)))

    opts = {
        # The year tier, the coarsest: one file per calendar year. People read the
        # last 'years' years closely, so those get 'year_resolution'. Older years get
        # 'old_year_resolution', because an hourly grid gives each one 8760 points.
        'years': to_int(get('years')),
        'year_resolution': seconds('year_resolution'),
        'old_year_resolution': seconds('old_year_resolution'),
        # The month tier: one file per calendar month, on a finer grid. The range bar
        # steps back one day at a time, and an hourly grid flattens a day.
        'months': to_int(get('months')),
        'month_resolution': seconds('month_resolution'),
        # The day tier, the finest: one file per day, which the day view is drawn
        # from. A 'day_resolution' of 0 means the archive interval the station
        # actually uses. See _archive_interval().
        'days': to_int(get('days')),
        'day_resolution': seconds('day_resolution'),
        # 'budget' is how many seconds the year and month tiers may take per report.
        # Building years of history at once would delay the next report by minutes.
        # The next report carries on where this one stopped. 0 means no limit.
        'budget': seconds('budget'),
        # The types named in 'extremes' also carry their lowest and highest reading
        # per slot. An average over four hours turns a storm's gusts into a breeze.
        # Each named type costs extra queries per slot.
        'extremes': set(weeutil.weeutil.option_as_list(get('extremes')) or []),
        # How often a file is rebuilt from the database instead of extended from the
        # file on disk. See _rebuild_due().
        'rebuild': seconds('rebuild'),
    }

    if opts['months'] and opts['month_resolution'] >= opts['year_resolution']:
        # Usually month_resolution = 5m. In a duration, 'm' means months, not minutes.
        log.warning("Ignoring months: month_resolution (%d seconds) is not "
                    "finer than year_resolution (%d seconds)",
                    opts['month_resolution'], opts['year_resolution'])
        opts['months'] = 0
    if opts['old_year_resolution'] < opts['year_resolution']:
        # A skin that sets only year_resolution, to more than the default of
        # old_year_resolution, gets year_resolution for all years without a warning.
        if 'old_year_resolution' in arch_dict:
            log.warning("old_year_resolution (%d seconds) is finer than "
                        "year_resolution (%d seconds). Using year_resolution for both.",
                        opts['old_year_resolution'], opts['year_resolution'])
        opts['old_year_resolution'] = opts['year_resolution']
    return opts


def _year_grid(year, this_year, years, year_resolution, old_year_resolution, existing):
    """Return the grid, in seconds, for one calendar year's file.

    The last 'years' years get 'year_resolution', older years 'old_year_resolution'.
    A file already on a finer grid keeps it. Coarsening a year would cost a year of
    queries to end up with less.

    Args:
        year (int): The calendar year the file covers.
        this_year (int): The year the report is being run in.
        years (int): How many years, counting back, use the finer grid.
        year_resolution (int): The grid for the recent years, in seconds.
        old_year_resolution (int): The grid the older years use, in seconds.
        existing (int | None): The grid the file on disk was written at, if there is one.
    """
    if years and year <= this_year - years:
        grid = old_year_resolution
    else:
        grid = year_resolution
    if existing and existing < grid:
        return existing
    return grid


def _months_back(last_ts, months, floor_ts):
    """Return the start of the month 'months - 1' months before the one of last_ts.

    The month files are cut by calendar month. So 'months = 2' means the month in
    progress and the whole month before it.

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
    """Return True if this run must rebuild every file from the database.

    An extended file keeps what earlier runs put in it. So a change to the past
    persists, e.g., a reading corrected by an import, or a changed unit. A rebuild at a
    fixed cadence limits how long such stale data survives.

    For a day or more, the test counts calendar days, not elapsed seconds. So every
    station rebuilds on its first report after midnight, whatever its interval. A
    station that was off over midnight rebuilds when it comes back.

    Args:
        rebuilt (int | None): When the last rebuild ran, or None for never.
        now_ts (int): The time this report is being run for.
        after (int): How many seconds between rebuilds. Zero never rebuilds.
    """
    if not after:
        return False
    if rebuilt is None:
        return True
    # Under a day, calendar days do not apply, so compare elapsed seconds.
    if after < 86400:
        return now_ts - rebuilt >= after
    then = datetime.date.fromtimestamp(rebuilt)
    now = datetime.date.fromtimestamp(now_ts)
    return (now - then).days >= int(after // 86400)


def _index_of(known):
    """Return the index entries, by plot group, of the files already on disk.

    A run skips the files that are current, and a budget defers more. The index still
    has to name them, or the page cannot see them. _reconcile_index() has checked
    'known' against the directory, so every file in 'known' exists.

    Args:
        known (dict[str, dict[str, Any]]): The archive index as read and reconciled.

    Returns:
        dict[str, dict[str, Any]]: One entry per plot group, as _new_entry() makes it.
    """
    index = {}
    for key in (key for tier in TIERS for key in tier):
        for group, stamps in known[key].items():
            index.setdefault(group, _new_entry())[key].update(stamps)
    for group, entry in index.items():
        entry['title'], entry['unit_label'] = known['labels'].get(group, (None, None))
    return index


def _archive_interval(db_manager, last_ts):
    """Return the archive interval in seconds, as stored in the newest record.

    A driver that reads the interval from the hardware can override the configured
    one. The record holds the interval actually used. Falls back to 300 seconds.

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


def _drop_old_days(arch_root, on_disk, group_name, keep, entry):
    """Delete the day files of group_name whose stamps are not in keep.

    The day tier is the only tier whose old files are deleted. Kept forever, it would
    add one small file per group per day, and nobody steps back a year day by day.

    Args:
        arch_root (str): The archive directory.
        on_disk (list[str]): The names of the files in it.
        group_name (str): The plot group to sweep.
        keep (set[str]): The day stamps that are still wanted.
        entry (dict[str, Any]|None): The group's entry in the index being written.
            The days deleted leave it too.
    """
    for filename in on_disk:
        parsed = _parse_archive_name(filename)
        if parsed is None or parsed[:2] != (group_name, 'days') or parsed[2] in keep:
            continue
        try:
            os.remove(os.path.join(arch_root, filename))
        except OSError as e:
            log.debug("Could not remove old day file '%s': %s", filename, e)
            continue
        if entry is not None:
            entry['days'].pop(parsed[2], None)
            entry['day_intervals'].pop(parsed[2], None)


def _parse_archive_name(filename):
    """Split the name of an archive file into its plot group, tier and stamp.

    A year file is named '<group>-2025.json', a month file '<group>-2025-07.json', and
    a day file '<group>-2025-07-13.json'.

    Args:
        filename (str): The file name, without a directory.

    Returns:
        tuple[str, str, str]|None: A three-way tuple (group, kind, stamp), with kind
            as TIERS names it, e.g., ('tempdew', 'months', '2025-07'). None if the
            name is not that of an archive file.
    """
    match = _ARCHIVE_NAME.match(filename)
    if match is None:
        return None
    group, year, month, day = match.groups()
    if day:
        return group, 'days', year + month + day
    if month:
        return group, 'months', year + month
    return group, 'years', year


def _read_archive_file(path):
    """Read one archive file, or return None if it cannot be used.

    None covers a missing file, a truncated one, and one in an unknown shape. In every
    case the caller calculates the span from the database again.

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


def _extends(previous, start, resolution, slots):
    """Return True if the file on disk is on the grid of the file being built.

    Args:
        previous (dict[str, Any]): The file on disk.
        start (int): Where the file being built begins.
        resolution (int): Its grid, in seconds.
        slots (int): How many slots it holds.
    """
    try:
        return int(previous['start']) == start and int(previous['interval']) == resolution \
            and int(previous['count']) <= slots and int(previous['newest']) >= start \
            and isinstance(previous['series'], list)
    except (KeyError, TypeError, ValueError):
        return False


def _intervals(start, stop, step):
    """Return where the intervals of a series begin and end, as two lists.

    The intervals are the ones get_series() aggregates over: intervalgen() keeps their
    boundaries on constant local time, so an interval across a change of DST is an
    hour longer or shorter.

    Args:
        start (int): The beginning of the first interval.
        stop (int): The end of the last interval.
        step (int): The length of an interval, in seconds.
    """
    begins, ends = [], []
    for span in weeutil.weeutil.intervalgen(start, stop, step):
        begins.append(int(span.start))
        ends.append(int(span.stop))
    return begins, ends


def _bucket(begins, ends, first, stamps, values, weights):
    """Sort readings into the intervals they belong to.

    A reading stamped t belongs to the interval with begin < t <= end, as in the
    queries of the database.

    Args:
        begins (list[int]): Where each interval begins.
        ends (list[int]): Where each interval ends.
        first (int): The index of the first interval to fill.
        stamps (list[int]): When each reading was taken.
        values (list): The readings. A None is left out.
        weights (list[int]): The archive interval of each reading, in seconds.

    Returns:
        dict: {index: (values, weights)} for each interval that holds a reading.
    """
    out = {}
    for stamp, value, weight in zip(stamps, values, weights):
        if value is None:
            continue
        i = bisect.bisect_left(ends, stamp, first)
        if i < len(ends) and begins[i] < stamp:
            vals, wts = out.setdefault(i, ([], []))
            vals.append(value)
            wts.append(weight)
    return out


# The aggregations _reduce() does itself. Any other goes to the database, one query per
# interval.
_RAW_AGGREGATES = ('avg', 'sum', 'min', 'max', 'first', 'last', 'vecdir')


def _reduce(agg, values, weights):
    """Combine the readings of one interval, as the database would.

    Args:
        agg (str): One of _RAW_AGGREGATES.
        values (list[float|complex]): The readings, in the order they were taken.
        weights (list[int]): The archive interval of each reading, in seconds.

    Returns:
        float|complex|None: The aggregate. A wind vector with no length has no
            bearing, so 'vecdir' then returns None.
    """
    if agg == 'avg':
        return sum(values) / len(values)
    if agg == 'sum':
        return sum(values)
    if agg in ('min', 'max'):
        pick = min if agg == 'min' else max
        # A wind vector compares by its length, as in the database. Python 3.7 does
        # not take key=None, so the two cases stay apart.
        return pick(values, key=abs) if isinstance(values[0], complex) else pick(values)
    if agg == 'first':
        return values[0]
    if agg == 'last':
        return values[-1]
    # 'vecdir': the bearing of the sum of the vectors, each weighed by its interval.
    total = sum(value * weight for value, weight in zip(values, weights))
    if not total:
        return None
    deg = 90.0 - math.degrees(math.atan2(total.imag, total.real))
    return deg if deg >= 0 else deg + 360.0


def _daynight(start_ts, stop_ts, lat, lon):
    """Compute sunrise, sunset and civil twilight over a span.

    The PNGs switch from day to night shading where the sun crosses the horizon.
    Daylight fades over civil twilight, i.e., about half an hour, and much longer at
    high latitude in summer. The twilight bounds let the page fade the shading.

    Args:
        start_ts (int): The beginning of the span.
        stop_ts (int): The end of the span.
        lat (float): The station latitude, in degrees.
        lon (float): The station longitude, in degrees.

    Returns:
        dict|None: Three keys. 'first' is 'day' or 'night', whichever it was at
            start_ts. 'transitions' is the horizon crossings, as timestamps.
            'twilight' is one entry per dawn and dusk, e.g.
            {'from': 1787725000, 'to': 1787727100, 'dir': 'dawn'}. None if the sun
            neither rises nor sets in the span, e.g., inside the polar circles.
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
    """Return True if the section defines plots rather than settings.

    A plot definition is three levels deep: [ImageGenerator], then a time span such as
    [[day_images]], then a plot such as [[[daytempdew]]]. So a section holds plots if
    one of its subsections has subsections. A settings subsection such as [[Archive]]
    has none.

    Args:
        section (configobj.Section): The section to test.
    """
    try:
        return any(section[name].sections for name in section.sections)
    except (AttributeError, KeyError, TypeError):
        return False


def _yscale(plot_options, series_out):
    """Return the y axis of the plot as [min, max, increment].

    The axis comes from weeplot.utilities.scale(), as in the ImageGenerator. The plot's
    'yscale' fixes the values it names, and scale() fills in the rest from the data. A
    chart library picks worse axes, e.g., wind direction up to 400 degrees.

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
