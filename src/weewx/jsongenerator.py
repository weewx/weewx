#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate JSON time series, for JavaScript that draws its own charts.

The JSON generator is the data-only counterpart to `weewx.imagegenerator`. It reads plot
definitions in the ImageGenerator's syntax and fetches the series through
`weewx.xtypes.get_series()`. It converts units and looks up labels like the
ImageGenerator, but writes JSON instead of a PNG.

The generator writes into `<HTML_ROOT>/<json_dest_dir>`:

  skin.json    The time_length of each time period, and the unit table. See
               gen_skin_json().
  archive/     The series of each plot over the whole database, one archive file per
               calendar year, month or day. See gen_archive().

The terms below are the generator's own. Everything else is named as elsewhere in
WeeWX, e.g., archive record, archive interval, aggregation type, aggregation interval,
time period, plot, line and timespan.

  JavaScript     The code of a skin that reads the JSON files and draws the charts. In
                 the Horizon skin, horizon.js.
  run            One call of run(). The report engine makes one per report cycle.
  plot group     The name of a plot without its time period, e.g., 'tempdew' for
                 [[[daytempdew]]], as in option plot_groups of [DisplayOptions].
  archive file   A JSON file that holds the series of one plot group over one calendar
                 year, month or day. See _archive_file() for an example.
  date           The year, month or day an archive file covers, as its name gives it,
                 e.g., '2025', '2025-07' or '2025-07-13'.
  tier           The archive files of one length: the year tier, the month tier and
                 the day tier.
  newest         The time up to which an archive file is complete.
  archive index  The file archive/index.json. It names every archive file, with its
                 newest and its aggregation interval.
  extend         Write an archive file again, starting from the one on disk. Only the
                 aggregation intervals from its newest on are calculated.
  rebuild        Calculate every archive file from the database again.

The Reference Guide documents the options under [JSONGenerator].
"""

import bisect
import calendar
import copy
import datetime
import json
import logging
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

# The three tiers, as two-way tuples (tier, intervals_key). For each plot group, the
# archive index keeps the newest of each archive file under the tier, e.g., 'years', and
# its aggregation interval under intervals_key, e.g., 'year_intervals'.
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

# The name of an archive file: the plot group, then the date. See _parse_archive_name().
_ARCHIVE_NAME = re.compile(r'^(.+)-(\d{4})(-\d{2})?(-\d{2})?\.json$')


class JSONGenerator(weewx.reportengine.ReportGenerator):
    """Generate JSON time series from plot definitions."""
    EMPTY_INDEX = {
        'first': None,
        'rebuilt': None,
        'titles': {},
        **{key: {} for pair in TIERS for key in pair}
    }

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
        self.plot_dict = configobj.ConfigObj()
        self.text_dict = None

    def run(self):
        self.setup()
        if not self.plot_dict:
            # No plot definitions found. Return.
            log.info("No plot definitions in [JSONGenerator] or [ImageGenerator]. "
                     "No JSON written.")
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
        for name in ('JSONGenerator', 'ImageGenerator'):
            section = self.skin_dict.get(name)
            if section is not None and _holds_plots(section):
                self.plot_dict = section
                break

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

    def gen_skin_json(self):
        """Write skin.json: the time_length of each time period, and the unit table.

        The JavaScript reads skin.json before it draws a chart. The contents are static,
        so it is written on the first run only, or when it is missing.
        """
        skin_file = os.path.join(self.data_root, 'skin.json')
        if not self.first_run and os.path.exists(skin_file):
            return

        # time_lengths maps each time period to its 'time_length' in seconds, e.g.,
        # 86400 for [[day_images]]. The JavaScript sets the width of the x axis from it.
        # A section without plots, e.g., [[Archive]], is not a time period.
        time_lengths = {}
        for period in self.plot_dict.sections:
            if self.plot_dict[period].sections:
                time_lengths[period] = to_int(weeutil.weeutil.nominal_spans(
                    search_up(self.plot_dict[period], 'time_length', 86400)))

        try:
            _write_json(skin_file,
                        {'time_lengths': time_lengths,
                         # Each archive file holds values in one unit. The unit
                         # table lets the JavaScript convert them to any other.
                         'units': _unit_choices(self.formatter, self.converter)})
        except OSError as e:
            log.error("Unable to save to file '%s': %s", skin_file, e)

    def gen_archive(self, gen_ts):
        """Write the archive files of every plot group, and the archive index.

        Each tier cuts the database into calendar years, months or days, one archive
        file each. An archive file whose timespan has ended does not change, so it is
        written once and then skipped. The JavaScript fetches only the archive files it
        shows. See "The JSON generator" in the Customization Guide for the format and
        the cost.

        Args:
            gen_ts (int|None): The time the report is being run for.
        """
        arch_dict = self.gen_dict.get('Archive', {})

        t1 = time.time()

        opts = _archive_settings(arch_dict)
        rounding = to_int(self.gen_dict.get('round', 2))
        # The JavaScript reads the archive files from 'archive' below the JSON directory.
        arch_root = os.path.join(self.data_root, 'archive')

        # The archive files hold the plots of [[day_images]].
        try:
            day_plots = self.plot_dict['day_images']
        except KeyError:
            log.error("Archive: no section [[day_images]]. Skipped.")
            return

        # What this run has done so far, for the budget and for the log line at the
        # end.
        counters = {'written': 0, 'skipped': 0, 'extended': 0, 'deferred': 0,
                    'spent': 0.0, 'first': None, 'last': None, 'daynight': False}

        # 'old_index' is the archive index the previous run wrote, corrected to match
        # the archive files on disk. The archive index this run writes, 'index', starts
        # from it, and every archive file written updates it.
        try:
            on_disk = os.listdir(arch_root)
        except OSError:
            on_disk = []
        old_index = self._read_archive_index(arch_root)
        self._reconcile_index(old_index, arch_root, on_disk)
        index = _index_of(old_index)
        previous_first = old_index['first']
        now_ts = int(gen_ts or time.time())
        rebuilding = _rebuild_due(old_index['rebuilt'], now_ts, opts['rebuild'])

        def write_index():
            """Write the archive index, for the archive files that exist so far.

            Called after each pass. The JavaScript finds the archive files through the
            archive index, so it cannot see an archive file the index does not name.
            """
            groups = []
            for name in sorted(index):
                entry = index[name]
                if not any(entry[tier] for tier, _ in TIERS):
                    # The plot group has no archive file in any tier. Naming it would
                    # send the JavaScript after a 404.
                    continue
                # The aggregation interval is recorded per archive file, because files
                # written under different settings differ.
                groups.append({'name': name,
                               'title': entry['title'] or name,
                               **{key: entry[key] for pair in TIERS for key in pair}})
            try:
                _write_json(os.path.join(arch_root, 'index.json'),
                            {'first': counters['first'],
                             'last': counters['last'],
                             # When the archive files were last rebuilt. The next run
                             # passes 'rebuilt' to _rebuild_due().
                             'rebuilt': now_ts if rebuilding else old_index['rebuilt'],
                             'groups': groups})
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        # Two passes over the plot groups: first the day tier of every plot group, then
        # the other tiers. The archive index is written after each pass. So a station
        # building its history has the day view at once, before the years behind it are
        # done.
        for pass_name in ('days', 'rest'):
            for plotname in day_plots.sections:
                if self.stop_event and self.stop_event.is_set():
                    return

                plot_options = accumulateLeaves(day_plots[plotname])
                db_manager = self.db_binder.get_manager(plot_options['data_binding'])

                first_ts = db_manager.firstGoodStamp()
                last_ts = gen_ts or db_manager.lastGoodStamp()
                if not first_ts or not last_ts:
                    continue

                # If the database reaches further back than in the previous run, history
                # was imported, and every archive file has to be built again.
                reimported = previous_first is not None and int(first_ts) < previous_first

                # Take 'first' and 'last' from the database, not from the archive files
                # written this run. A second run in the same minute writes no file.
                if counters['first'] is None or first_ts < counters['first']:
                    counters['first'] = int(first_ts)
                if counters['last'] is None or last_ts > counters['last']:
                    counters['last'] = int(last_ts)

                group_name = plotname[len('day'):] if plotname.startswith('day') else plotname

                this_year = time.localtime(int(last_ts)).tm_year

                def write_tier(timespans, tier, date_of, interval_of, tier_from,
                               metered=True, raw=False):
                    """Write the archive files of one tier for the current plot group.

                    The tiers differ in how they cut the database into archive files,
                    and in the aggregation interval. The arguments supply those
                    differences. Skipping, extending and recording in the archive index
                    work the same for every tier.

                    Args:
                        timespans (Iterable[weeutil.weeutil.TimeSpan]): The timespans to
                            write, one archive file each.
                        tier (str): Which tier, as the archive index names it, e.g.,
                            'days'.
                        date_of (Callable[[weeutil.weeutil.TimeSpan], str]): Called as
                            ``date_of(timespan)``. Returns the date of the archive file
                            for a timespan, e.g., '2026-07'.
                        interval_of (Callable[[str, int|None], int]): Called as
                            ``interval_of(date, old_interval)``. Returns the aggregation
                            interval, in seconds, of the archive file for a date.
                            ``old_interval`` is the one the previous archive index
                            records for that date, or None if there is none.
                        tier_from (int): The oldest time this tier reaches.
                        metered (bool): Whether the budget applies. The day tier is not
                            metered.
                        raw (bool): Whether the aggregation interval is the archive
                            interval. See _archive_series().
                    """
                    intervals_key = dict(TIERS)[tier]
                    # Start with the newest timespan. A run that stops early then leaves
                    # the oldest archive files unbuilt, not this year.
                    for timespan in reversed(list(timespans)):
                        # An archive file deferred by the budget is written by a later
                        # run.
                        if metered and opts['budget'] and counters['spent'] >= opts['budget']:
                            counters['deferred'] += 1
                            continue
                        date = date_of(timespan)
                        out_file = os.path.join(arch_root, '%s-%s.json' % (group_name, date))
                        old_interval = old_index[intervals_key].get(group_name, {}).get(date)
                        interval = interval_of(date, old_interval)
                        entry = index.setdefault(group_name, _new_entry())

                        # 'newest' is the time up to which the archive file is complete.
                        # For a timespan that has ended, it is the end of the timespan,
                        # so the file is written once. For the timespan in progress,
                        # 'newest' advances with the database. The file is written again
                        # when 'newest' reaches the next aggregation interval. A test on
                        # the file's age would miss a catch-up, where the file is minutes
                        # old but hours behind.
                        newest = min(int(timespan.stop), int(last_ts))
                        old_newest = old_index[tier].get(group_name, {}).get(date)
                        if os.path.exists(out_file) and old_newest is not None \
                                and not reimported \
                                and old_newest // interval == newest // interval:
                            counters['skipped'] += 1
                            continue

                        # Passing the archive file on disk as 'old_file' extends it. A
                        # rebuild or an import calculates the whole timespan instead.
                        old_file = None if rebuilding or reimported or old_newest is None \
                            else _read_archive_file(out_file)
                        if old_file is not None:
                            counters['extended'] += 1

                        started = time.time()
                        payload = self._archive_file(
                            plot_dict=day_plots[plotname], plot_options=plot_options,
                            timespan=timespan, interval=interval, rounding=rounding,
                            group_name=group_name, first_ts=tier_from, last_ts=last_ts,
                            old_file=old_file, extremes=opts['extremes'], raw=raw)
                        counters['spent'] += time.time() - started
                        if payload is None:
                            continue
                        try:
                            _write_json(out_file, payload)
                            counters['written'] += 1
                            entry[tier][date] = payload['newest']
                            entry[intervals_key][date] = interval
                            entry['title'] = ', '.join(s['label'] for s in payload['series'])
                        except OSError as e:
                            log.error("Unable to save to file '%s': %s", out_file, e)

                if opts['days'] and pass_name == 'days':
                    # The day tier is exempt from the budget. It is cheap, and a run that
                    # deferred it would leave the JavaScript without today. It is also
                    # the only tier whose old archive files are deleted. See
                    # _drop_old_days().
                    days_from = max(int(first_ts),
                                    weeutil.weeutil.startOfDay(int(last_ts))
                                    - (opts['days'] - 1) * 86400)
                    day_timespans = list(weeutil.weeutil.genDaySpans(days_from, last_ts))
                    date_of_day = lambda timespan: time.strftime(
                        '%Y-%m-%d', time.localtime(timespan.start))
                    timespan_of = {date_of_day(timespan): timespan
                                   for timespan in day_timespans}
                    # A 'day_resolution' of 0 takes the archive interval of the day's
                    # archive records. An archive file already written keeps its own, so
                    # the database is asked once per day.
                    day_interval = lambda date, old_interval: (
                        opts['day_resolution'] or old_interval
                        or _archive_interval_of_day(db_manager, timespan_of[date]))
                    write_tier(timespans=day_timespans, tier='days', date_of=date_of_day,
                               interval_of=day_interval, tier_from=days_from,
                               metered=False, raw=not opts['day_resolution'])
                    _drop_old_days(arch_root, on_disk, group_name,
                                   {date_of_day(timespan) for timespan in day_timespans},
                                   index.get(group_name))

                if opts['months'] and pass_name == 'rest':
                    months_from = _months_back(int(last_ts), opts['months'], int(first_ts))
                    write_tier(
                        timespans=weeutil.weeutil.genMonthSpans(months_from, last_ts),
                        tier='months',
                        date_of=lambda timespan: time.strftime(
                            '%Y-%m', time.localtime(timespan.start)),
                        interval_of=lambda date, old_interval: opts['month_resolution'],
                        tier_from=months_from)

                if pass_name == 'rest':
                    write_tier(
                        timespans=weeutil.weeutil.genYearSpans(first_ts, last_ts),
                        tier='years',
                        date_of=lambda timespan: time.strftime(
                            '%Y', time.localtime(timespan.start)),
                        interval_of=lambda year, old_interval: _year_interval(
                            year=int(year), this_year=this_year, years=opts['years'],
                            year_resolution=opts['year_resolution'],
                            old_year_resolution=opts['old_year_resolution'],
                            old_interval=old_interval),
                        tier_from=first_ts)

            # Write the archive index after each pass that leaves any archive file.
            if any(entry[tier] for entry in index.values() for tier, _ in TIERS):
                # Write the day/night files with the first archive index, so the
                # shading appears with the first charts. Without the day tier, that is
                # the second pass.
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
        """Read the archive index that the previous run wrote.

        An archive file the archive index names need not be calculated again, whatever
        the current settings say.

        Args:
            arch_root (str): The archive directory.

        Returns:
            dict: With keys

                years:           {plot group: {date: newest}}, for each year's archive
                                 file
                months:          the same for the months
                days:            the same for the days
                year_intervals:  {plot group: {date: seconds}}, the aggregation interval
                                 of each year's archive file. The archive files can
                                 differ, because a file is never rewritten just to
                                 coarsen it.
                month_intervals: the same for the months
                day_intervals:   the same for the days
                titles:          {plot group: title}
                first:           the oldest archive record in the database when the
                                 previous run read it, or None if there was no archive
                                 index
                rebuilt:         when the archive files were last rebuilt, or None
        """
        path = os.path.join(arch_root, 'index.json')
        # A copy, because the rest of this run fills 'old_index' in place.
        old_index = copy.deepcopy(JSONGenerator.EMPTY_INDEX)
        try:
            with open(path, encoding='utf-8') as fd:
                index = json.load(fd)
            old_index['first'] = to_int(index.get('first'))
            old_index['rebuilt'] = to_int(index.get('rebuilt'))
            for group in index.get('groups', []):
                name = group['name']
                # A run that writes no archive file of a plot group still needs the
                # plot group's title for the archive index, so keep it from the old one.
                old_index['titles'][name] = group.get('title')
                for key in (key for pair in TIERS for key in pair):
                    by_date = {date: int(value)
                               for date, value in (group.get(key) or {}).items() if value}
                    if by_date:
                        old_index[key][name] = by_date
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # No archive index, or one this version cannot read. Start from an empty
            # one, which _reconcile_index() then fills from the archive files on disk.
            return copy.deepcopy(JSONGenerator.EMPTY_INDEX)
        return old_index

    @staticmethod
    def _reconcile_index(old_index, arch_root, on_disk):
        """Correct the archive index, in place, to match the archive files on disk.

        The JavaScript cannot see an archive file the archive index does not name. A
        name without a file sends the JavaScript after a 404. If index.json is lost, the
        archive files restore it, and nothing has to be calculated again. Only archive
        files missing from the archive index are opened.

        Args:
            old_index (dict): The archive index as _read_archive_index() returns it.
            arch_root (str): The archive directory.
            on_disk (list[str]): The names of the files in it.
        """
        seen = {tier: set() for tier, _ in TIERS}
        for filename in on_disk:
            parsed = _parse_archive_name(filename)
            if parsed is None or parsed[0] == 'daynight':
                continue
            group_name, tier, date = parsed
            intervals_key = dict(TIERS)[tier]
            seen[tier].add((group_name, date))
            if date in old_index[tier].get(group_name, {}):
                continue
            # The archive index does not name this archive file. Read 'newest' and
            # 'interval' from the file.
            payload = _read_archive_file(os.path.join(arch_root, filename))
            if not payload:
                continue
            newest = to_int(payload.get('newest'))
            interval = to_int(payload.get('interval'))
            if newest is None or not interval:
                continue
            old_index[tier].setdefault(group_name, {})[date] = newest
            old_index[intervals_key].setdefault(group_name, {})[date] = interval

        # Drop what the archive index names but the directory does not hold.
        for tier, intervals_key in TIERS:
            for group_name in list(old_index[tier]):
                for date in list(old_index[tier][group_name]):
                    if (group_name, date) not in seen[tier]:
                        old_index[tier][group_name].pop(date, None)
                        old_index[intervals_key].get(group_name, {}).pop(date, None)

    def _archive_daynight(self, root, first_ts, last_ts):
        """Write sunrise and sunset times, one file per calendar year.

        Sunrise and sunset depend only on the station's location, so one file serves
        every plot group. A year that has ended is written once, like the archive
        files.

        Args:
            root (str): The archive directory.
            first_ts (int): The oldest archive record in the database.
            last_ts (int): The newest archive record in it.
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

    def _archive_file(self, plot_dict, plot_options, timespan, interval, rounding,
                      group_name, first_ts, last_ts, old_file=None, extremes=(), raw=False):
        """Build the contents of one archive file: one plot group over one timespan.

        Every tier builds its archive files here. A day, a month and a year differ only
        in length and aggregation interval.

        The result holds no timestamps. 'values[i]' is the aggregate over the
        aggregation interval that begins at 'start + i * interval', for 'count'
        aggregation intervals. A None is an aggregation interval without a value.

        Args:
            plot_dict (configobj.Section): The plot, holding one subsection per line.
            plot_options (dict): The options that apply to the plot.
            timespan (weeutil.weeutil.TimeSpan): The timespan the archive file covers.
            interval (int): The aggregation interval of the archive file, in seconds.
            rounding (int|None): Decimal places, or None to leave them alone.
            group_name (str): The plot group, which the archive file is named after,
                e.g., 'tempdew'.
            first_ts (int): The oldest archive record in the database.
            last_ts (int): The newest archive record in it.
            old_file (dict|None): The archive file on disk, as read back, if it is to be
                extended. None otherwise.
            extremes (set[str]|tuple[str, ...]): The observation types that also carry
                the lowest and highest value in each aggregation interval.
            raw (bool): Whether 'interval' is the archive interval. See
                _archive_series().

        Returns:
            dict|None: The contents of the archive file, or None if the timespan holds
                nothing worth writing. For example, the archive file of plot group
                'tempdew' for 2025, at an aggregation interval of one hour, on a station
                in UTC+1::

                    {'name': 'tempdew', 'start': 1735686000, 'interval': 3600,
                     'count': 8760, 'newest': 1767222000,
                     'unit': 'degree_C',
                     'yscale': [-10.0, 35.0, 5.0],
                     'series': [{'obs_type': 'outTemp', 'label': 'Outside Temperature',
                                 'aggregate_type': 'avg', 'color': '#4282b4',
                                 'values': [3.1, 2.8, None, 2.4, ...]}]}
        """
        # Clip to the archive records that exist, then move both ends onto a multiple of
        # 'interval'. Every series of every year then falls on the same times, and the
        # JavaScript can put two years end to end without resampling either.
        lo = max(timespan.start, int(first_ts))
        hi = min(timespan.stop, int(last_ts) + interval)
        start = int(lo // interval * interval)
        # Round 'stop' up to a multiple of 'interval'. Rounding down and adding
        # 'interval' would add an aggregation interval whenever 'hi' is on a boundary,
        # i.e., for every timespan that has ended. No later run fills that aggregation
        # interval, because 'newest' stays the same and the file is skipped. The time
        # belongs to the next archive file anyway.
        stop = int(-(-hi // interval) * interval)
        count = int((stop - start) / interval)
        if count < 2:
            return None

        # An archive file at another aggregation interval, or cut from another
        # timespan, cannot be extended.
        if old_file is not None and not _extends(old_file, start, interval, count):
            old_file = None
        old_by_key = {}
        if old_file is not None:
            old_by_key = {(s.get('obs_type'), s.get('aggregate_type')): s
                          for s in old_file['series']}

        series_out = []
        unit = None
        for line_name in plot_dict.sections:
            line = self._line_spec(plot_dict[line_name], line_name, interval)
            entry = self._archive_series(
                line=line, plot_options=plot_options, start=start, stop=stop,
                count=count, interval=interval, rounding=rounding, extremes=extremes,
                old_series=old_by_key.get((line['var_type'], line['aggregate_type'])),
                old_file=old_file, raw=raw)
            if entry is None:
                continue
            entry_unit = entry.pop('unit')
            if entry_unit is not None:
                unit = entry_unit
            series_out.append(entry)

        if not series_out:
            return None
        # A timespan without new archive records reports no unit. The archive file then
        # keeps its own.
        if unit is None and old_file is not None:
            unit = old_file.get('unit')

        # chart_line_colors applies to every series that sets no color of its own.
        default_colors = weeutil.weeutil.option_as_list(
            plot_options.get('chart_line_colors', [])) or []
        for i, s in enumerate(series_out):
            if 'color' not in s and default_colors:
                s['color'] = _normalize_color(default_colors[i % len(default_colors)])

        return {
            'name': group_name,
            'start': start,
            'interval': interval,
            'yscale': _yscale(plot_options, series_out),
            'count': count,
            # The time up to which this archive file is complete. The next run compares
            # it with the database to decide whether the file has to be written again.
            'newest': min(int(timespan.stop), int(last_ts)),
            # The unit of every value in the file. Its label is in skin.json.
            'unit': unit,
            'series': series_out,
        }

    def _archive_series(self, line, plot_options, start, stop, count, interval, rounding,
                        extremes, old_series, old_file, raw=False):
        """Build one series of an archive file.

        Args:
            line (dict): The line, as _line_spec() returns it.
            plot_options (dict): The options of the plot the line belongs to.
            start (int): Where the archive file begins.
            stop (int): Where it ends.
            count (int): How many aggregation intervals it holds.
            interval (int): Its aggregation interval, in seconds.
            rounding (int|None): Decimal places, or None to leave them alone.
            extremes (set[str]|tuple[str, ...]): The observation types that also carry
                the lowest and highest value in each aggregation interval.
            old_series (dict|None): The same series in the archive file on disk, or None.
            old_file (dict|None): The archive file on disk, if it is being extended.
            raw (bool): Whether 'interval' is the archive interval. Each aggregation
                interval then holds one archive record, and a line at that interval
                takes the values of the archive records as they are.

        Returns:
            dict|None: The series, with its unit under 'unit', which the caller takes
                out again. None if the series holds no value.
        """
        mgr = self.db_binder.get_manager(line['options']['data_binding'])
        # Many skins plot sensors a station lacks. One query that stops at the first
        # archive record saves reading a whole year of nothing, on every run.
        if old_file is None and _skip_if_empty(mgr, line['data_type'],
                                               TimeSpan(start, stop)):
            return None

        def resume(aggregate_interval):
            """Return where to start calculating, and how many old values to keep.

            When extending, the aggregation interval that holds the newest of the
            archive file on disk may have filled up since. So it is calculated again,
            together with every aggregation interval after it.

            Returns:
                tuple[int, int]: A two-way tuple (since, keep). 'since' is where that
                    aggregation interval begins, and 'keep' the number of values to
                    take from the file on disk.
            """
            if old_file is None:
                return start, 0
            begins, ends = _intervals(start, stop, aggregate_interval)
            i = bisect.bisect_left(ends, old_file['newest'])
            since = begins[i] if i < len(begins) else stop
            return since, int((since - start) // interval)

        def new_values(key, keep):
            """Return a list of 'count' values, with the first 'keep' from old_series."""
            carried = old_series.get(key) if old_series is not None else None
            if carried is None:
                return [None] * count
            # Clear the values from 'keep' on, so an aggregation interval without a new
            # value does not keep its old one.
            return list(carried[:keep]) + [None] * (count - keep)

        def fill(out, pairs):
            """Put each (begin, value) of pairs into 'out', at the position of 'begin'."""
            for begin, val in pairs:
                i = int((begin - start) // interval)
                if val is not None and 0 <= i < count:
                    out[i] = round(val, rounding) if rounding is not None else val
            return out

        # The aggregation intervals of the line. Only a bar has other ones than the
        # archive file. See _line_spec().
        since, keep = resume(line['aggregate_interval'])
        # A value that is alone in its aggregation interval needs no aggregation. One
        # query then reads all of them, instead of one query per aggregation interval.
        unaggregated = raw and line['aggregate_interval'] == interval
        aggregated = self._aggregate_line(line=line, plot_options=plot_options, mgr=mgr,
                                          timespan=TimeSpan(since, stop), raw=unaggregated)
        if aggregated is None:
            return None
        unit, pairs = aggregated
        empty = all(val is None for _, val in pairs)
        if old_series is None and empty:
            return None
        if old_file is not None and (
                old_series is None or unit is not None and unit != old_file.get('unit', unit)):
            # A series the archive file on disk lacks, e.g., a new sensor, or a unit that
            # has changed since the file was written: calculate the whole timespan.
            return self._archive_series(
                line=line, plot_options=plot_options, start=start, stop=stop,
                count=count, interval=interval, rounding=rounding, extremes=extremes,
                old_series=None, old_file=None, raw=raw)

        entry = {
            'obs_type': line['var_type'],
            'label': line['label'],
            'aggregate_type': line['aggregate_type'],
            'unit': unit,
        }
        if line['aggregate_interval'] != interval:
            # The aggregates of a bar sit at every nth position. The JavaScript needs
            # aggregate_interval to draw each bar n aggregation intervals wide.
            entry['aggregate_interval'] = line['aggregate_interval']
        if line['color']:
            entry['color'] = _normalize_color(line['color'])
        if line['plot_type'] == 'bar':
            entry['plot_type'] = 'bar'

        values = [val for _, val in pairs]
        components = _vector_components(values) if line['plot_type'] == 'vector' else None
        if components:
            # The speed goes in 'values', so a reader that knows nothing about vectors
            # still draws a line. The legend shows the bearing, and the JavaScript draws
            # the arrows from the components.
            speeds, bearings = _split_vectors(values)
            instants = [begin for begin, _ in pairs]
            entry['values'] = fill(new_values('values', keep), zip(instants, speeds))
            entry['vector_x'] = fill(new_values('vector_x', keep),
                                     zip(instants, components[0]))
            entry['vector_y'] = fill(new_values('vector_y', keep),
                                     zip(instants, components[1]))
            if bearings is not None:
                entry['directions'] = fill(new_values('directions', keep),
                                           zip(instants, bearings))
            entry['plot_type'] = 'vector'
            if line['rotate'] is not None:
                entry['vector_rotate'] = -float(line['rotate'])
        else:
            entry['values'] = fill(new_values('values', keep), pairs)

        # The lowest and highest value per aggregation interval of the archive file, for
        # the observation types named in 'extremes'. For a bar, these are finer than
        # its own aggregation intervals. A value alone in its aggregation interval is
        # its own lowest and highest.
        if line['var_type'] in extremes and not unaggregated \
                and line['aggregate_type'] not in ('min', 'max', 'vecdir') and not components:
            since, keep = resume(interval)
            for which in ('min', 'max'):
                extreme = self._aggregate_line(
                    line=line, plot_options=plot_options, mgr=mgr,
                    timespan=TimeSpan(since, stop), aggregate_type=which,
                    aggregate_interval=interval)
                if extreme is not None:
                    entry[which] = fill(new_values(which, keep), extreme[1])
        return entry

    def _line_spec(self, line_dict, line_name, interval):
        """Read the options of one line of a plot.

        Args:
            line_dict (configobj.Section): The line, e.g., [[[[outTemp]]]].
            line_name (str): The name of the section.
            interval (int): The aggregation interval of the archive file, in seconds.

        Returns:
            dict: 'var_type', 'aggregate_type', 'aggregate_interval', 'plot_type',
                'label', 'color', 'rotate', all the line's 'options', and the
                'data_type' as the skin names it, e.g., 'windDir' where 'var_type' is
                'wind'.
        """
        options = accumulateLeaves(line_dict)
        var_type = options.get('data_type', line_name)
        plot_type = options.get('plot_type', 'line').lower()

        # The line's own aggregate_type wins. 'none' asks for the values of the archive
        # records, which do not fit the aggregation interval of the file, so average.
        aggregate_type = options.get('aggregate_type')
        if aggregate_type in (None, '', 'None', 'none'):
            aggregate_type = 'avg'
        # Sum the observation types whose accumulator extractor is 'sum', e.g., 'rain',
        # 'ET' and 'windrun'. Reading accum_dict instead of a list here also sums the
        # types a station adds under [Accumulator].
        if weewx.accum.accum_dict.get(var_type, {}).get('extractor') == 'sum':
            aggregate_type = 'sum'
        elif var_type in ('windDir', 'windGustDir'):
            # The arithmetic mean of 350 and 10 degrees is 180, due south. 'vecdir'
            # averages the vectors and takes their bearing instead.
            var_type, aggregate_type = 'wind', 'vecdir'

        # A line with 'plot_type = bar' keeps its aggregate_interval where that is
        # coarser than the aggregation interval of the archive file: an hourly rain
        # total differs from sixty one-minute totals. Its aggregates then sit at every
        # nth position of the series. Other lines take the aggregation interval of the
        # file. For them, aggregate_interval only smooths the drawing, and honouring it
        # would leave most positions of a fine archive file empty.
        aggregate_interval = interval
        asked = to_int(weeutil.weeutil.nominal_spans(options.get('aggregate_interval')))
        if asked and asked > interval and plot_type == 'bar':
            aggregate_interval = asked

        label = options.get('label')
        label = self.text_dict.get(label, label) if label \
            else self.generic_dict.get(var_type, var_type)

        return {'var_type': var_type, 'aggregate_type': aggregate_type,
                'aggregate_interval': aggregate_interval, 'plot_type': plot_type,
                'label': label, 'color': options.get('color'),
                'rotate': options.get('vector_rotate'), 'options': options,
                'data_type': options.get('data_type', line_name)}

    def _aggregate_line(self, line, plot_options, mgr, timespan, aggregate_type=None,
                        aggregate_interval=None, raw=False):
        """Return the aggregates of one line over a timespan, as the ImageGenerator does.

        Args:
            line (dict): The line, as _line_spec() returns it.
            plot_options (dict): The options of the plot the line belongs to.
            mgr (weewx.manager.Manager): The database manager.
            timespan (weeutil.weeutil.TimeSpan): The timespan to aggregate.
            aggregate_type (str|None): The aggregation type, or None for the line's own.
            aggregate_interval (int|None): The aggregation interval in seconds, or None
                for the line's own.
            raw (bool): True to return the values of the archive records instead, each
                paired with the beginning of its archive interval.

        Returns:
            tuple|None: A two-way tuple (unit, pairs). 'pairs' holds (begin, aggregate)
                for each aggregation interval. None if the database knows neither the
                observation type nor the aggregation type.
        """
        options = dict(line['options'])
        options.pop('aggregate_type', None)
        options.pop('aggregate_interval', None)
        try:
            if raw:
                # The type as the skin names it: 'windDir', not 'wind' with 'vecdir'.
                start_vec, _, data_vec = weewx.xtypes.get_series(
                    line['data_type'], timespan, mgr, **options)
            else:
                start_vec, _, data_vec = weewx.xtypes.get_series(
                    line['var_type'], timespan, mgr,
                    aggregate_type=aggregate_type or line['aggregate_type'],
                    aggregate_interval=aggregate_interval or line['aggregate_interval'],
                    **options)
        except (weewx.UnknownType, weewx.UnknownAggregation):
            return None
        unit, values = self._convert(data_vec, plot_options)
        return unit, list(zip(start_vec[0], values))

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

    weewx.units converts with a function per pair of units, which the JavaScript cannot
    call. So the JavaScript gets the numbers instead.

    Args:
        convert (Callable[[weewx.units.ValueTuple, str], weewx.units.ValueTuple]):
            Called as ``convert(val_t, to_unit)``, normally `weewx.units.convert`.
            Returns the ValueTuple converted to ``to_unit``.
        from_unit (str): The unit the value is in.
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
    """Build the unit table that lets the JavaScript show values in another unit.

    The archive files hold values in the skin's units. To offer Fahrenheit next to
    Celsius, the JavaScript needs each observation type's unit group, each unit system's
    unit for the unit group, and the conversions between units. The unit table goes into
    skin.json.

    Args:
        formatter (weewx.units.Formatter): The formatter the report was rendered with.
        converter (weewx.units.Converter): The converter it was rendered with.

    Returns:
        dict: Six keys. 'groups' maps an observation type to its unit group.
            'systems' maps a unit system name to the unit it uses for each unit group.
            'report' maps each unit group to the unit the report renders it in.
            'convert' maps a unit to each unit it converts to, as [factor, offset].
            'labels' and 'formats' give each unit's label and number format, so the
            JavaScript writes "18.5 °C" the way the server would.
    """
    # Every unit system WeeWX knows, with the unit it uses for each unit group.
    by_system = {}
    for unit_system in weewx.units.std_groups:
        name = weewx.units.unit_nicknames[unit_system]
        by_system[name] = dict(weewx.units.std_groups[unit_system])

    # 'report' holds the units the report renders in. The JavaScript needs them for the
    # values it fetches itself, e.g., the forecast, which arrives in Celsius. Without
    # 'report', "Default" in the unit picker would mean metric, not the skin's units.
    report = dict(converter.group_unit_dict)

    # The JavaScript can switch to any unit system, so 'wanted' holds every unit of
    # every unit system, and the units of the report.
    wanted = {unit for table in by_system.values() for unit in table.values()}
    wanted.update(report.values())

    # Iterate over weewx.units.conversionDict, rather than over every pair of units
    # in 'wanted'. Asking weewx.units.convert() for a pair it cannot convert logs a
    # DEBUG line, and most pairs cannot be converted.
    #
    # The Walter and Lieth diagram on the climate page is always drawn in degree_C and
    # mm, because its 2:1 ratio is defined in those units. On a US station the
    # values arrive in degree_F and inch. So 'convert' must carry the rows from
    # those units to metric, whatever units the other charts show.
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
    """Write one JSON file atomically and compactly.

    An atomic write is needed to avoid parsing errors caused by a partial write.

    Args:
        path (str): Where to write the file.
        payload (dict): What to write.
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
    """A blank archive index entry for one plot group."""
    return {'title': None,
            **{key: {} for pair in TIERS for key in pair}}


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
        # The year tier: one archive file per calendar year. People read the last
        # 'years' years closely, so those get 'year_resolution'. Older years get
        # 'old_year_resolution', because an aggregation interval of one hour gives each
        # one 8760 aggregates.
        'years': to_int(get('years')),
        'year_resolution': seconds('year_resolution'),
        'old_year_resolution': seconds('old_year_resolution'),
        # The month tier: one archive file per calendar month, at a shorter aggregation
        # interval. The range bar steps back one day at a time, and an aggregation
        # interval of one hour flattens a day.
        'months': to_int(get('months')),
        'month_resolution': seconds('month_resolution'),
        # The day tier: one archive file per day, which the day view is drawn from. A
        # 'day_resolution' of 0 means the archive interval of the day's archive
        # records. See _archive_interval_of_day().
        'days': to_int(get('days')),
        'day_resolution': seconds('day_resolution'),
        # 'budget' is how many seconds the year and month tiers may take per run.
        # Building years of history at once would delay the next report by minutes.
        # The next run carries on where this one stopped. 0 means no limit.
        'budget': seconds('budget'),
        # The observation types named in 'extremes' also carry their lowest and highest
        # value per aggregation interval. An average over four hours turns a storm's
        # gusts into a breeze.
        'extremes': set(weeutil.weeutil.option_as_list(get('extremes')) or []),
        # How often every archive file is rebuilt, rather than extended. See
        # _rebuild_due().
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


def _year_interval(year, this_year, years, year_resolution, old_year_resolution,
                   old_interval):
    """Return the aggregation interval, in seconds, of one calendar year's archive file.

    The last 'years' years get 'year_resolution', older years 'old_year_resolution'.
    An archive file already written at a shorter aggregation interval keeps it.
    Coarsening a year would cost a year of queries to end up with less.

    Args:
        year (int): The calendar year the archive file covers.
        this_year (int): The year the report is being run in.
        years (int): How many years, counting back, get 'year_resolution'.
        year_resolution (int): The aggregation interval of the recent years, in seconds.
        old_year_resolution (int): The one of the older years, in seconds.
        old_interval (int|None): The aggregation interval of the archive file on disk,
            if there is one.
    """
    if years and year <= this_year - years:
        interval = old_year_resolution
    else:
        interval = year_resolution
    if old_interval and old_interval < interval:
        return old_interval
    return interval


def _months_back(last_ts, months, floor_ts):
    """Return where the month tier begins.

    The month tier holds 'months' calendar months, counting the one in progress. For
    example, with 'last_ts' on 13 July 2026 and 'months' = 2, the month tier begins on
    1 June 2026 at midnight, local time, and holds June and July.

    Args:
        last_ts (int): The newest archive record in the database.
        months (int): How many calendar months the month tier holds.
        floor_ts (int): The oldest archive record, which the result never precedes.

    Returns:
        int: The timestamp where the month tier begins.
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
    """Return True if this run must rebuild every archive file.

    A run extends an archive file: it keeps the aggregates the file already holds, and
    calculates only the aggregation intervals from its newest on. A change to an older
    archive record never reaches the file, e.g., records filled in by 'weectl database
    calc-missing', or by an import that fills a gap. Option 'rebuild' sets how often
    every archive file is calculated from the database again, which brings such changes
    in.

    For a 'rebuild' of a day or more, count calendar days rather than seconds. The
    rebuild then happens on the first run after midnight, whenever the previous one
    happened. A station that was off over midnight rebuilds when it comes back.

    Args:
        rebuilt (int|None): When the last rebuild happened, or None for never.
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


def _index_of(old_index):
    """Return the entries of the archive index this run starts from, by plot group.

    A run does not write every archive file: it skips the ones that are current, and the
    budget can defer others to a later run. The archive index this run writes must
    still name every archive file on disk, or the JavaScript cannot find it. So it
    starts from the previous archive index, which _reconcile_index() has corrected to
    match the archive files on disk.

    Args:
        old_index (dict): The archive index as read and reconciled.

    Returns:
        dict: One entry per plot group, as _new_entry() makes it.
    """
    index = {}
    for key in (key for pair in TIERS for key in pair):
        for group_name, by_date in old_index[key].items():
            index.setdefault(group_name, _new_entry())[key].update(by_date)
    for group_name, entry in index.items():
        entry['title'] = old_index['titles'].get(group_name)
    return index


def _archive_interval_of_day(db_manager, timespan):
    """Return the archive interval that most archive records of a day have, in seconds.

    A station can change its archive interval, and a driver can take it from the
    hardware rather than from weewx.conf. So each archive file of the day tier takes the
    archive interval of the archive records of its own day.

    Args:
        db_manager (weewx.manager.Manager): The database manager.
        timespan (weeutil.weeutil.TimeSpan): The day.

    Returns:
        int: The archive interval, or 300 if the day holds no archive record.
    """
    try:
        row = db_manager.getSql("SELECT interval FROM %s "
                                "WHERE dateTime > ? AND dateTime <= ? "
                                "GROUP BY interval ORDER BY COUNT(*) DESC LIMIT 1"
                                % db_manager.table_name, timespan)
    except weedb.DatabaseError:
        row = None
    return int(row[0]) * 60 if row and row[0] else 300


def _drop_old_days(arch_root, on_disk, group_name, keep, entry):
    """Delete the day files of group_name whose dates are not in keep.

    The day tier is the only tier whose old archive files are deleted. Kept forever, it
    would add one small file per plot group per day, and nobody steps back a year day by
    day.

    Args:
        arch_root (str): The archive directory.
        on_disk (list[str]): The names of the files in it.
        group_name (str): The plot group to sweep.
        keep (set[str]): The dates of the day files that are still wanted.
        entry (dict|None): The plot group's entry in the archive index being written.
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
    """Split the name of an archive file into its plot group, tier and date.

    A year file is named '<plot group>-2025.json', a month file
    '<plot group>-2025-07.json', and a day file '<plot group>-2025-07-13.json'.

    Args:
        filename (str): The file name, without a directory.

    Returns:
        tuple[str, str, str]|None: A three-way tuple (group_name, tier, date), with
            tier as TIERS names it, e.g., ('tempdew', 'months', '2025-07'). None if the
            name is not that of an archive file.
    """
    match = _ARCHIVE_NAME.match(filename)
    if match is None:
        return None
    group_name, year, month, day = match.groups()
    if day:
        return group_name, 'days', year + month + day
    if month:
        return group_name, 'months', year + month
    return group_name, 'years', year


def _read_archive_file(path):
    """Read one archive file, or return None if it cannot be used.

    None covers a missing file, a truncated one, and one in an unknown shape. In every
    case the caller calculates the timespan from the database again.

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


def _extends(old_file, start, interval, count):
    """Return True if the archive file on disk can be extended into the one being built.

    Both must begin at the same time and have the same aggregation interval, and the
    file on disk must not hold more aggregation intervals than the new one.

    Args:
        old_file (dict): The archive file on disk.
        start (int): Where the archive file being built begins.
        interval (int): Its aggregation interval, in seconds.
        count (int): How many aggregation intervals it holds.
    """
    try:
        return int(old_file['start']) == start and int(old_file['interval']) == interval \
            and int(old_file['count']) <= count and int(old_file['newest']) >= start \
            and isinstance(old_file['series'], list)
    except (KeyError, TypeError, ValueError):
        return False


def _intervals(start, stop, aggregate_interval):
    """Return where the aggregation intervals of a series begin and end, as two lists.

    The aggregation intervals are the ones get_series() aggregates over: intervalgen()
    keeps their boundaries on constant local time, so an aggregation interval across a
    change of DST is an hour longer or shorter.

    Args:
        start (int): The beginning of the first aggregation interval.
        stop (int): The end of the last one.
        aggregate_interval (int): The length of an aggregation interval, in seconds.

    Returns:
        tuple[list[int], list[int]]: A two-way tuple (begins, ends).
    """
    begins, ends = [], []
    for timespan in weeutil.weeutil.intervalgen(start, stop, aggregate_interval):
        begins.append(int(timespan.start))
        ends.append(int(timespan.stop))
    return begins, ends


def _daynight(start_ts, stop_ts, lat, lon):
    """Compute sunrise, sunset and civil twilight over a timespan.

    The PNGs switch from day to night shading where the sun crosses the horizon.
    Daylight fades over civil twilight, i.e., about half an hour, and much longer at
    high latitude in summer. The twilight bounds let the JavaScript fade the shading.

    Args:
        start_ts (int): The beginning of the timespan.
        stop_ts (int): The end of the timespan.
        lat (float): The station latitude, in degrees.
        lon (float): The station longitude, in degrees.

    Returns:
        dict|None: Three keys. 'first' is 'day' or 'night', whichever it was at
            start_ts. 'transitions' is the horizon crossings, as timestamps.
            'twilight' is one entry per dawn and dusk, e.g.
            {'from': 1787725000, 'to': 1787727100, 'dir': 'dawn'}. None if the sun
            neither rises nor sets in the timespan, e.g., inside the polar circles.
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
        # is which saves the JavaScript from deducing it from the horizon crossings.
        if dawn < stop_ts and rise > start_ts:
            twilight.append({'from': dawn, 'to': rise, 'dir': 'dawn'})
        if sets < stop_ts and dusk > start_ts:
            twilight.append({'from': sets, 'to': dusk, 'dir': 'dusk'})

    if first is None and not transitions:
        # The sun neither rose nor set in this timespan. Inside the polar circles that
        # is normal for weeks at a time.
        return None

    transitions.sort()
    twilight.sort(key=lambda b: b['from'])
    return {'first': first or 'day', 'transitions': transitions, 'twilight': twilight}


def _holds_plots(section):
    """Return True if the section defines plots rather than settings.

    A plot definition is three levels deep: [ImageGenerator], then a time period such as
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
        plot_options (dict): The options of the plot being written.
        series_out (list[dict]): The series already worked out for it.

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
    zero line, so JavaScript drawing the same arrows needs both parts.

    Args:
        seq (list[complex|None]): Complex values, as `get_series()` returns them for wind.

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
        seq (list[complex|None]): Complex values, as `get_series()` returns them for wind.

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
        color (str|int|None): A colour, in any of the forms the skin may write it.
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
