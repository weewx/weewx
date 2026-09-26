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
# Import _skip_if_empty() rather than copy it, so that a fix to it reaches both
# generators.
from weewx.imagegenerator import _skip_if_empty

log = logging.getLogger(__name__)


class JSONGenerator(weewx.reportengine.ReportGenerator):
    """Generate JSON time series from plot definitions."""

    def run(self):
        self.setup()
        # setup() found no plot definitions and has logged the error.
        if not self.plot_dict:
            return
        self.gen_skin_json()
        self.gen_archive(self.gen_ts)

    def setup(self):
        # ReportGenerator gained stop_event in v5.5.0. Earlier versions do not set
        # stop_event, and the JSON generator runs under them as an extension.
        if not hasattr(self, 'stop_event'):
            self.stop_event = None

        # Generic labels, such as "Outside Temperature":
        try:
            self.generic_dict = self.skin_dict['Labels']['Generic']
        except KeyError:
            self.generic_dict = {}
        # Translated text strings:
        self.text_dict = self.skin_dict.get('Texts', {})

        # ConfigObj turns the {} into a Section. search_up() needs a Section, because
        # it climbs the tree through .parent.
        if 'JSONGenerator' not in self.skin_dict:
            self.skin_dict['JSONGenerator'] = {}
        self.gen_dict = self.skin_dict['JSONGenerator']
        self.data_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict.get('HTML_ROOT', 'public_html'),
                                      self.gen_dict.get('json_dest_dir', 'data'))

        # Take the plot definitions from [JSONGenerator] if it holds any. A skin that
        # draws only charts in the page keeps them there. Otherwise take them from
        # [ImageGenerator]. Then a skin that draws both defines each plot once, and
        # an older skin needs no new configuration.
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

    def gen_skin_json(self):
        """Write skin.json, which holds the length of each time span and the unit table.

        The page reads skin.json before it draws a chart. Nothing in skin.json comes
        from the database.
        """
        indent = to_int(self.gen_dict.get('json_indent'))

        # span_lengths maps each time span to its 'time_length' in seconds, e.g.,
        # 86400 for [[day_images]]. The page sets the x axis width from span_lengths.
        span_lengths = {}
        # Every observation type in the plot definitions. _unit_choices() builds the
        # unit table from obs_types.
        obs_types = set()
        for timespan in self.plot_dict.sections:
            span_dict = self.plot_dict[timespan]
            # A section without plots, e.g., [[Archive]], is not a time span.
            if not span_dict.sections:
                continue
            span_lengths[timespan] = to_int(weeutil.weeutil.nominal_spans(
                search_up(span_dict, 'time_length', 86400)))
            for plotname in span_dict.sections:
                for line_name in span_dict[plotname].sections:
                    obs_types.add(search_up(span_dict[plotname][line_name],
                                            'data_type', line_name))

        # No reading is fetched here, so the converter supplies the unit of each type.
        units_seen = set()
        for obs in obs_types:
            try:
                unit = self.converter.getTargetUnit(obs)[0]
            except (KeyError, TypeError, weewx.UnknownType):
                continue
            if unit:
                units_seen.add(unit)

        skin_file = os.path.join(self.data_root, 'skin.json')
        try:
            _write_json(skin_file,
                        {'spans': span_lengths,
                         # Each archive file holds readings in one unit. The unit
                         # table lets the page convert them to any other.
                         'units': _unit_choices(obs_types, units_seen,
                                                self.formatter, self.converter)},
                        indent)
        except OSError as e:
            log.error("Unable to save to file '%s': %s", skin_file, e)

    def gen_archive(self, gen_ts):
        """Write the whole record, one file per plot group and span.

        The spans are calendar years, and optionally months (the fine tier) and days
        (the raw tier). A span that has ended never changes, so its file is written
        once and then skipped. The page fetches only the spans it shows. See "The JSON
        generator" in the Customization Guide for the format and the cost.

        Args:
            gen_ts (int | None): The time the report is being run for.
        """
        arch_dict = self.gen_dict.get('Archive', {})

        t1 = time.time()

        source_group = arch_dict.get('source_group', 'day_images')
        strip_prefix = arch_dict.get('strip_prefix', 'day')
        aggregate_type = arch_dict.get('aggregate_type', 'avg')
        max_days = to_int(arch_dict.get('max_days', 0))

        # The year tier, the coarsest: one file per calendar year. People read the
        # last 'recent_years' years closely, so those get 'resolution'. Older years
        # get 'coarse_resolution', because an hourly grid gives each one 8760 points.
        resolution = to_int(weeutil.weeutil.nominal_spans(arch_dict.get('resolution', 3600)))
        coarse_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('coarse_resolution', resolution)))
        recent_years = to_int(arch_dict.get('recent_years', 0))

        # The fine tier: one file per calendar month, on a finer grid. The range bar
        # steps back one day at a time, and an hourly grid flattens a day.
        fine_months = to_int(arch_dict.get('fine_months', 0))
        fine_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('fine_resolution', 900)))
        if fine_months and fine_resolution >= resolution:
            # Usually fine_resolution = 5m. In a duration, 'm' means months, not minutes.
            log.warning("Ignoring fine_months: fine_resolution (%d seconds) is not "
                        "finer than resolution (%d seconds)",
                        fine_resolution, resolution)
            fine_months = 0
        if coarse_resolution < resolution:
            log.warning("coarse_resolution (%d seconds) is finer than resolution "
                        "(%d seconds). Using resolution for both.",
                        coarse_resolution, resolution)
            coarse_resolution = resolution

        # The raw tier, the finest: one file per day, which the day view is drawn
        # from. A 'raw_resolution' of 0 means the archive interval the station
        # actually uses. See _archive_interval().
        raw_days = to_int(arch_dict.get('raw_days', 0))
        raw_resolution = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('raw_resolution', 0)))

        # 'budget' is how many seconds the year and fine tiers may take per report.
        # Building years of history at once would delay the next report by minutes.
        # The next report carries on where this one stopped. 0 means no limit.
        budget = to_int(weeutil.weeutil.nominal_spans(arch_dict.get('budget', 0)))

        # The types named in 'extremes' also carry their lowest and highest reading
        # per slot. An average over four hours turns a storm's gusts into a breeze.
        # Each named type costs extra queries per slot, so the skin must ask for it.
        extrema = set(weeutil.weeutil.option_as_list(
            arch_dict.get('extremes', [])) or [])
        dest_dir = arch_dict.get('dest_dir',
                                 os.path.join(self.gen_dict.get('json_dest_dir', 'data'),
                                              'archive'))
        indent = to_int(self.gen_dict.get('json_indent'))
        rounding = to_int(arch_dict.get('round', self.gen_dict.get('round', 2)))
        # How often a file is rebuilt from the database instead of extended from the
        # file on disk. See _rebuild_due().
        rebuild_after = to_int(weeutil.weeutil.nominal_spans(
            arch_dict.get('rebuild', '1d')))

        try:
            group_dict = self.plot_dict[source_group]
        except KeyError:
            log.error("Archive: no section [%s]. Skipped.", source_group)
            return

        # write_tier() updates these counters. In a dict they need no 'nonlocal'.
        counters = {'written': 0, 'skipped': 0, 'extended': 0, 'deferred': 0,
                    'spent': 0.0, 'slots': 0, 'root': None,
                    'first': None, 'last': None, 'daynight': False}
        index = {}

        # The archive index the last run wrote.
        known = self._read_archive_index(dest_dir)
        self._reconcile_index(known, os.path.join(
            self.config_dict['WEEWX_ROOT'],
            search_up(self.skin_dict, 'HTML_ROOT', 'public_html'), dest_dir))
        previous_first = known['first']
        now_ts = int(gen_ts or time.time())
        rebuilding = _rebuild_due(known['rebuilt'], now_ts, rebuild_after)

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
                group = {
                    'name': name,
                    'title': entry['title'] or name,
                    'unit_label': entry['unit_label'] or '',
                    'years': sorted(entry['covered']),
                }
                for kind, grids in TIERS:
                    # JSON keys are strings, so a year is written as one, and
                    # _read_archive_index() converts it back. The grid is recorded per
                    # file, because files written under different settings differ.
                    group[kind] = {str(s): c for s, c in entry[kind].items()}
                    group[grids] = {str(s): g for s, g in entry[grids].items()}
                groups.append(group)
            try:
                _write_json(os.path.join(counters['root'], 'index.json'),
                            # 'interval' and 'fine_interval' are the grids for files
                            # written now. A reader that ignores the per-file grids
                            # falls back on them.
                            {'interval': resolution,
                             'fine_interval': fine_resolution if fine_months else None,
                             'first': counters['first'],
                             'last': counters['last'],
                             # When the files were last rebuilt in full. The next
                             # run passes 'rebuilt' to _rebuild_due().
                             'rebuilt': now_ts if rebuilding else known['rebuilt'],
                             'groups': groups},
                            indent)
            except OSError as e:
                log.error("Unable to write archive index: %s", e)

        # Two passes over the groups: first the raw tier of every group, then the other
        # tiers. The index is written after each pass. So a station building its
        # history has the day view at once, before the years behind it are done.
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

            # If the database reaches further back than last run, history was
            # imported, and every file has to be built again. The test uses 'db_first',
            # because under 'max_days' 'first_ts' moves forward every day.
            reimported = previous_first is not None and int(db_first) < previous_first

            # Take 'first' and 'last' from the database, not from the files written this
            # run. A second run in the same minute writes no file.
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
                """Write the files of one tier for the current plot group.

                The tiers differ in how they cut the record into files, in the grid,
                and in their index keys. The arguments supply those differences.
                Skipping, extending and recording work the same for every tier.

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
                # Newest span first. A run that stops early then leaves the oldest
                # spans unbuilt, not this year.
                for span in reversed(list(spans)):
                    afford = _affordable(budget, counters) if metered else None
                    if afford == 0:
                        counters['deferred'] += 1
                        continue
                    stamp = stamp_of(span)
                    out_file = os.path.join(arch_root, name_of(stamp))
                    grid = grid_of(stamp, known[grids].get(group_name, {}).get(stamp))
                    entry = index.setdefault(group_name, _new_entry())

                    # 'covered' is the newest reading the file holds. For a finished
                    # span it is the end of the span, so the file is written once. For
                    # the span in progress, 'covered' advances with the database. The
                    # file is rewritten when 'covered' reaches the next slot. A test on
                    # the file's age would miss a catch-up, where the file is minutes
                    # old but hours behind.
                    covered = min(int(span.stop), int(last_ts))
                    was = known[kind].get(group_name, {}).get(stamp)
                    if os.path.exists(out_file) and was is not None and not reimported \
                            and was // grid == covered // grid:
                        counters['skipped'] += 1
                        entry[kind][stamp] = was
                        entry[grids][stamp] = grid
                        counters['root'] = arch_root
                        continue

                    # The file on disk holds every slot but its last. Passing it as
                    # 'carry' means only the slots from there on are calculated. A
                    # rebuild or an import calculates the whole span instead.
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
                    # Count the slots calculated, so that _affordable() can size the
                    # next file to the budget that is left.
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

            if raw_days and pass_name == 'raw':
                # The raw tier is exempt from the budget. It is cheap, and a report
                # that deferred it would leave the page without today. It is also the
                # only tier whose old files are deleted. See _drop_stale_raw().
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
                lambda year, existing: _year_grid(year, this_year, recent_years,
                                                  resolution, coarse_resolution,
                                                  existing),
                first_ts)

            _carry_over_index(index, known, group_name)
            if index.get(group_name) \
                    and any(index[group_name][kind] for kind, _ in TIERS):
                counters['root'] = arch_root

          # Write the index after each pass that has anything to show.
          if counters['root']:
              # Write the day/night files with the first index, so the shading
              # appears with the first charts. Without the raw tier, that is the
              # second pass.
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

    def _read_archive_index(self, dest_dir):
        """Read the archive index.json that the previous run wrote.

        A file the index names need not be calculated again, whatever the current
        settings say.

        Args:
            dest_dir (str): The archive directory.

        Returns:
            dict: With keys

                covered:        {group: {year: timestamp}}, the newest reading each
                                year's file holds
                fine:           the same for the months, keyed 'YYYY-MM'
                raw:            the same for the days, keyed 'YYYY-MM-DD'
                intervals:      {group: {year: seconds}}, the grid each year's file is
                                on. Files can differ, because a file is never
                                rewritten just to coarsen it.
                fine_intervals: the same for the months
                raw_intervals:  the same for the days
                labels:         {group: (title, unit_label)}
                first:          the oldest reading in the database when the last run
                                read it, or None if there was no index
                rebuilt:        when the files were last rebuilt in full, or None
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
            # An older index gives one grid at the top instead of one per file. Use
            # that grid for every file the older index names.
            defaults = {'intervals': to_int(index.get('interval')),
                        'fine_intervals': to_int(index.get('fine_interval')),
                        'raw_intervals': None}
            # JSON keys are strings. Year stamps are converted back to int, while month
            # and day stamps stay str.
            as_key = {'covered': int, 'fine': str, 'raw': str}
            for group in index.get('groups', []):
                name = group['name']
                # A run that writes no file of a group still needs the group's title
                # and unit_label for the index, so keep them from the old index.
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
            # No index, or one this version cannot read. Start from an empty record,
            # which _reconcile_index() then fills from the files on disk.
            return empty
        found['first'] = first
        found['rebuilt'] = rebuilt
        return found

    def _span_extreme(self, var_type, tail, mgr, which, resolution, option_dict,
                      plot_options, unit):
        """Get the lowest or highest reading of each slot in a span.

        Args:
            var_type (str): The observation type.
            tail (weeutil.weeutil.TimeSpan): The span to look in.
            mgr (weewx.manager.Manager): The open database.
            which (str): Which end is wanted, `min` or `max`.
            resolution (int): The grid, in seconds.
            option_dict (dict[str, Any]): The options of the line being written.
            plot_options (dict[str, Any]): The options of the plot it belongs to.
            unit (str): The unit the readings are wanted in.

        Returns:
            list|None: The values, in the order get_series() returns them. None if the
                database cannot answer for this type, or answers in another unit.
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
        # Extremes in another unit than the aggregate would put two scales on one
        # chart. So drop the extremes.
        if unit is not None and conv[1] is not None and conv[1] != unit:
            return None
        return conv[0]

    @staticmethod
    def _reconcile_index(known, arch_root):
        """Correct the archive index, in place, to match the files on disk.

        The page cannot see a file the index does not name. A name without a file
        sends the page after a 404. If index.json is lost, the files restore it, and
        nothing has to be calculated again.

        Only files missing from the index are opened, so an intact index costs one
        listdir.

        Args:
            known (dict[str, dict[str, Any]]): The index as it was read.
            arch_root (str): The archive directory.
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
            # The index does not name this file. Read 'covered' and 'interval' from it.
            payload = _read_archive_file(os.path.join(arch_root, filename))
            if not payload:
                continue
            covered = to_int(payload.get('covered'))
            interval = to_int(payload.get('interval'))
            if covered is None or not interval:
                continue
            known[kind].setdefault(group, {})[key] = covered
            known[grids].setdefault(group, {})[key] = interval

        # Drop what the index names but the directory does not hold.
        for kind, grids in TIERS:
            for group in list(known[kind]):
                for key in list(known[kind][group]):
                    if (group, key) not in seen[kind]:
                        known[kind][group].pop(key, None)
                        known[grids].get(group, {}).pop(key, None)

    def _archive_daynight(self, root, first_ts, last_ts, indent):
        """Write sunrise and sunset times, one file per calendar year.

        Sunrise and sunset depend only on the station's location, so one file serves
        every plot group. A year that has ended is written once, like the archive
        files.

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

        Every tier builds its files here. A day, a month and a year differ only in
        length and grid.

        The result holds no timestamps. `values[i]` is at `start + i * interval`, for
        `count` slots. A null is a slot without a reading.

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
            previous (dict[str, Any] | None): The file this one replaces, as read back
                from disk. If it can be extended, only the slots after its newest are
                calculated. Otherwise, e.g., after a change of series or unit, the whole
                span is.
            max_slots (int | None): The most slots to calculate. If they do not reach
                the end of the span, the file is written short, and the next run
                continues it. None calculates the whole span.
            extrema (set[str] | tuple[str, ...]): The observation types that also
                carry the lowest and highest reading in each slot.

        Returns:
            dict|None: The file's contents, or None if the span holds nothing worth
                writing. For a temperature group over 2025, on an hourly grid::

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
        # Round 'stop' up to a multiple of 'resolution'. Rounding down and adding one
        # step would add a slot whenever 'hi' is on a boundary, i.e., for every
        # finished day. No later run fills that slot, because 'covered' stays the same
        # and the file is skipped. The instant belongs to the next file anyway.
        stop = int(-(-hi // resolution) * resolution)
        slots = int((stop - start) / resolution)
        if slots < 2:
            return None

        # 'resume' is (resume_ts, resume_slot) from the file on disk, or None to
        # calculate every slot.
        resume = _resume_from(previous, start, resolution, slots)

        # Stop short if the budget allows only 'max_slots' more slots. The file then
        # covers less than its span, like a file still filling up. 'covered' says how
        # far it got, and the next run carries on from there.
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
        # resume_ts is where the last slot of this file starts, and resume_slot is its
        # index. Both go into the file, so that the next run carries on from there.
        resume_ts = resume_slot = None
        # 'stale' is set when the file on disk does not match the series being built.
        # Only the loop can detect that. The loop then breaks, and the whole span is
        # calculated.
        stale = False

        for line_name in plot_section.sections:
            line_options = accumulateLeaves(plot_section[line_name])
            var_type = line_options.get('data_type', line_name)
            mgr = self.db_binder.get_manager(line_options['data_binding'])

            if _skip_if_empty(mgr, var_type, domain):
                continue

            is_vector = line_options.get('plot_type', 'line').lower() == 'vector'

            # The line's own aggregate_type wins. 'none' asks for raw samples, which do
            # not fit a fixed grid, so use the default.
            agg = line_options.get('aggregate_type')
            if agg in (None, '', 'None', 'none'):
                agg = aggregate_type
            # Sum the types whose accumulator extractor is 'sum', e.g., 'rain', 'ET'
            # and 'windrun'. Reading accum_dict instead of a list here also sums the
            # types a station adds under [Accumulator].
            if weewx.accum.accum_dict.get(var_type, {}).get('extractor') == 'sum':
                agg = 'sum'
            elif var_type in ('windDir', 'windGustDir'):
                # The arithmetic mean of 350 and 10 degrees is 180, due south.
                # 'vecdir' averages the vectors and takes their bearing instead.
                # 'vecdir' reads the 'wind' daily summary, so var_type becomes 'wind'.
                var_type = 'wind'
                agg = 'vecdir'

            # Take the matching series from the file on disk, or rebuild if there is
            # none. See _carried_series().
            carried = None
            if resume is not None:
                carried = _carried_series(previous, len(series_out), var_type,
                                          previous['count'])
                if carried is None:
                    stale = True
                    break

            # A bar's aggregate_interval is part of its meaning: an hourly rain total
            # differs from sixty one-minute totals. So a bar asking for an interval
            # coarser than the grid gets it, with a reading every nth slot.
            #
            # Lines keep the grid. On a line, aggregate_interval only smooths the
            # drawing, and honouring it would leave most slots of a fine grid empty.
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

            # A span without readings reports no unit. Overwriting an earlier series'
            # unit with None would write a null into the file. An extending run would
            # then see a changed unit and rebuild the span on every report.
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

            # get_series() returns a wind vector as complex numbers.
            values, components, bearings = conv[0], None, None
            if is_vector:
                components = _vector_components(conv[0])
                if components:
                    # The speed goes in 'values', so a reader that knows nothing
                    # about vectors still draws a line. The legend shows the bearing,
                    # and the page draws the arrows from the components.
                    values, bearings = _split_vectors(conv[0])

            # Place each value by its timestamp. get_series() skips intervals without
            # readings, so the loop counter is not the slot.
            def new_grid(carried_values):
                if carried_values is None:
                    return [None] * slots
                # Keep the carried values before slot resume[1]. Clear the rest, so a
                # slot without a new reading does not keep its old value.
                return list(carried_values[:resume[1]]) + [None] * (slots - resume[1])

            def fill(grid, seq):
                for begin, val in zip(start_vec_t[0], seq):
                    if begin is None or val is None:
                        continue
                    # Place by the interval's start. intervalgen() clips the last
                    # interval to the end of the span, so counting back from its end
                    # would put it a slot early.
                    slot = int((begin - start) // resolution)
                    if 0 <= slot < slots:
                        grid[slot] = round(val, rounding) if rounding is not None else val
                return grid

            grid = fill(new_grid(carried['values'] if carried else None), values)

            # The last interval of the series may still have been filling up, so the
            # next run resumes at its start. Take the earliest across all series, so
            # that no series skips a slot.
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
                # The readings sit every nth slot. The page needs aggregate_interval
                # to draw each bar n slots wide.
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

            # Add the lowest and highest reading per slot for the types named in
            # 'extremes'. See gen_archive().
            if var_type in extrema and agg not in ('min', 'max'):
                for which in ('min', 'max'):
                    seq = self._span_extreme(var_type, tail, mgr, which, resolution,
                                             option_dict, plot_options, conv[1])
                    if seq is None:
                        continue
                    entry[which] = fill(
                        new_grid(carried and carried.get(which)), seq)

            series_out.append(entry)

        # A series added since the file was written makes series_out longer than
        # previous['series']. The loop can only detect that after it ends.
        if resume is not None and len(series_out) != len(previous['series']):
            stale = True

        if stale:
            # The file on disk holds other series, or another unit, than the skin asks
            # for now. Calculate the whole span without the file.
            log.debug("Archive file for '%s' does not match the plot it is for. "
                      "Rebuilding it.", group_name)
            return self._archive_span(plot_section, plot_options, span, resolution,
                                      aggregate_type, rounding, group_name, first_ts,
                                      last_ts, extrema=extrema)

        if not series_out:
            return None

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
            'covered': min(int(span.stop), int(last_ts)),
            # resume_ts and resume_slot tell the next run where to carry on. See
            # _resume_from().
            'resume_ts': resume_ts,
            'resume_slot': resume_slot,
            'unit': unit,
            'unit_label': (unit_label or '').strip(),
            'series': series_out,
        }


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


def _unit_choices(obs_types, units_seen, formatter, converter):
    """Build the unit table that lets the page show readings in another unit.

    The archive files hold readings in the skin's units. To offer Fahrenheit next to
    Celsius, the page needs each type's unit group, each system's unit for the group,
    and the conversions between units. The unit table goes into skin.json.

    Args:
        obs_types (set[str]): The observation types the page shows.
        units_seen (set[str]): The units those readings were written in.
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
    # Take the unit systems from weewx.units, so that a new system needs no change
    # here. The page shows the reader the name used in weewx.conf.
    systems = [(name, weewx.units.std_groups[constant])
               for name, constant in sorted(weewx.units.unit_constants.items(),
                                            key=lambda pair: pair[1])]

    # Include every type WeeWX knows a group for, not only the plotted ones. The
    # Horizon skin shows readings that no chart draws, e.g., rain rate and UV.
    # Without their groups, a unit switch would convert only some readings on a page.
    groups = {}
    for obs_type, group in weewx.units.obs_group_dict.items():
        if group:
            groups[str(obs_type)] = str(group)
    for obs_type in sorted(obs_types):
        group = weewx.units.getUnitGroup(obs_type)
        if group:
            groups[obs_type] = group

    # 'wanted' holds more units than the archive files use. A viewer can switch the
    # page to any unit system, so 'wanted' needs every system's unit for each group.
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

    # 'report' holds the units the report renders in. The page needs them for the
    # readings it fetches itself, e.g., the forecast, which arrives in Celsius.
    # Without 'report', "Default" on the page would mean metric, not the skin's units.
    report = {}
    for group in sorted(set(groups.values())):
        unit = converter.group_unit_dict.get(group)
        if unit:
            report[group] = unit

    return {'groups': groups, 'systems': by_system, 'report': report,
            'convert': convert, 'labels': labels, 'formats': formats}


def _write_json(path, payload, indent):
    """Write one JSON file atomically, so that a reader never sees half of it.

    A browser may fetch a file while it is being written. Half an index.json does not
    parse, and the page then draws nothing until the next poll.

    Args:
        path (str): Where to write the file.
        payload (dict[str, Any]): What to write.
        indent (int | None): Indentation, or None for the compact form.
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    # os.replace() is atomic only within one filesystem, so the temporary file sits
    # beside the target.
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fd:
        json.dump(payload, fd, indent=indent, ensure_ascii=False,
                  separators=(',', ':') if indent is None else None)
    os.replace(tmp, path)


# The index keys of the three tiers, as (kind, grids) pairs. Under 'kind' the index
# records what each file covers, and under 'grids' the grid of each file. The finest
# tier comes last.
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
    """Return the grid, in seconds, for one calendar year's file.

    The last 'recent_years' years get 'resolution', older years 'coarse_resolution'.
    A file already on a finer grid keeps it. Coarsening a year would cost a year of
    queries to end up with less.

    Args:
        year (int): The calendar year the file covers.
        this_year (int): The year the report is being run in.
        recent_years (int): How many years, counting back, use the finer grid.
        resolution (int): The grid for the recent years, in seconds.
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
    """Return the start of the month 'months - 1' months before the one of last_ts.

    The fine files are cut by calendar month. So 'fine_months = 2' means the month in
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


def _affordable(budget, counters):
    """Return how many slots fit in the rest of this run's budget.

    Args:
        budget (int): How many seconds this report may spend. Zero removes the limit.
        counters (dict[str, Any]): What the run has spent so far, and on how many
            slots.

    Returns:
        int|None: The slots that fit in what is left, at least one while any time is
            left. 0 once the budget is spent, and None if there is no budget.
    """
    if not budget:
        return None
    left = budget - counters['spent']
    if left <= 0:
        return 0
    # A slot costs one database query, whose time depends on the machine. So measure
    # it over the slots this run has done. Before the first, assume a pessimistic 5 ms.
    per_slot = counters['spent'] / counters['slots'] if counters['slots'] else 0.005
    return max(1, int(left / per_slot))


def _carry_over_index(index, known, group_name):
    """Add the files this run did not touch to the index entry of group_name.

    A run skips the files that are current, and a budget defers more. Those files are
    on disk, but the page cannot see a file the index does not name. _reconcile_index()
    has checked 'known' against the directory, so every file in 'known' exists.

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


def _drop_stale_raw(arch_root, group_name, keep):
    """Delete the raw day files of group_name whose stamps are not in keep.

    The raw tier is the only tier whose old files are deleted. Kept forever, it would
    add one small file per group per day, and nobody steps back a year day by day.

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


def _resume_from(previous, start, resolution, slots):
    """Return where to extend the file on disk, or None to calculate the whole span.

    The instant is read from the file, not computed from the slot number. get_series()
    aligns its intervals on local time, so across a DST change the boundaries are not a
    whole number of intervals apart. A computed instant would make an extended file
    differ from a rebuild.

    Args:
        previous (dict[str, Any] | None): The file already on disk, or None.
        start (int): Where the span being written begins.
        resolution (int): The grid it is written on, in seconds.
        slots (int): How many slots the span holds.

    Returns:
        tuple|None: A two-way tuple (resume_ts, resume_slot): the instant to query the
            database from, and the first slot to overwrite. None if the file cannot be
            extended, e.g., after a change of 'start' or 'interval', if the file
            reaches past the span, or if it lacks 'resume_ts' or 'resume_slot'.
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
    """Return the series at position in the file on disk, or None to rebuild.

    Series are matched by position, i.e., their order in the skin's plot section. The
    observation type must match too, because two series can swap places. The series
    must also hold exactly count values.

    The whole entry is returned, because a series can carry more arrays than 'values',
    e.g., vector components or extremes.

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
        section (dict): The section to test.
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
