#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the JSON generator.

Use pytest to run the tests.
"""

import itertools
import json
import logging
import os
import time
import types

import configobj
import pytest

import parameters
import weewx
import weewx.defaults
import weewx.imagegenerator
import weewx.jsongenerator
import weewx.manager
import weewx.reportengine
import weewx.station
import weewx.units
import weewx.xtypes
import weeutil.weeutil
from weeutil.config import accumulateLeaves

# The aggregation interval of the year files in the archive tests. No test depends on
# the value.
ARCHIVE_RESOLUTION = 14400

# Plot definitions in the [ImageGenerator] syntax: a two-line plot, a bar plot with
# aggregation, a wind vector, and a plot of a type the test database lacks. The
# generator must skip that last plot.
PLOT_CONF = """
REPORT_NAME = TestReport
SKIN_ROOT = skins
skin = Test
unit_system = metricwx
data_binding = wx_binding

[ImageGenerator]
    chart_line_colors = "#4282b4", "#b44242"
    chart_fill_colors = "#72b2c4", "#c47272"
    plot_type = line
    aggregate_type = none
    skip_if_empty = year
    show_daynight = true

    [[day_images]]
        time_length = 27h

        [[[daytempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]

        [[[dayrain]]]
            plot_type = bar
            aggregate_type = sum
            aggregate_interval = 3600
            [[[[rain]]]]

        [[[daywindvec]]]
            vector_rotate = 90
            [[[[windvec]]]]
                plot_type = vector

        [[[daynothing]]]
            [[[[soilMoist4]]]]

    [[week_images]]
        time_length = 7d
        aggregate_type = avg
        aggregate_interval = 1h

        [[[weektempdew]]]
            [[[[outTemp]]]]
            [[[[dewpoint]]]]
"""


def build_skin_dict(html_root, archive_options=None):
    """Build a skin dictionary complete enough to run the generator."""
    # The delta-time formats contain e.g. %(minute_label)s, which ConfigObj would try to
    # interpolate. The report engine turns interpolation off for the same reason.
    weewx.defaults.defaults.interpolation = False

    mine = configobj.ConfigObj(PLOT_CONF.splitlines(), interpolation=False)

    # The tests turn the day and month tiers, the budget and the extremes on where
    # they are about them, and pin a rebuild once a day.
    json_conf = {'json_dest_dir': 'data', 'round': '3',
                 'Archive': {'year_resolution': str(ARCHIVE_RESOLUTION),
                             'years': '0', 'months': '0', 'days': '0',
                             'budget': '0', 'extremes': [], 'rebuild': '1d'}}
    json_conf['Archive'].update(archive_options or {})

    # Build a plain dict and hand it to ConfigObj in one piece. accumulateLeaves()
    # walks the parent chain up to the root. Sections merged into an existing
    # ConfigObj keep their old parents, and the chain breaks.
    combined = weewx.defaults.defaults.dict()
    combined.update(mine.dict())
    combined['HTML_ROOT'] = html_root
    combined['JSONGenerator'] = json_conf

    skin_dict = configobj.ConfigObj(combined, interpolation=False)
    # 'unit_system' is only a shorthand; the report engine expands it into the unit
    # groups before any generator sees it. Do the same, or the converter keeps the
    # database's own units.
    weewx.reportengine.merge_unit_system(skin_dict['unit_system'], skin_dict)
    return skin_dict


def run_generator(config_dict, tmp_path, gen_ts=None, archive_options=None,
                  first_run=True):
    """Run the generator against the test database and return its output directory."""
    html_root = str(tmp_path)
    skin_dict = build_skin_dict(html_root, archive_options=archive_options)

    # WEEWX_ROOT is left as the test configuration set it, so the database is still
    # found. HTML_ROOT is absolute, so os.path.join() ignores WEEWX_ROOT for it.
    config_dict = configobj.ConfigObj(config_dict.dict(), interpolation=False)

    stn_info = weewx.station.StationInfo(**config_dict['Station'])
    if gen_ts is None:
        gen_ts = parameters.synthetic_dict['stop_ts']

    generator = weewx.jsongenerator.JSONGenerator(
        config_dict, skin_dict, gen_ts, first_run=first_run, stn_info=stn_info)
    try:
        generator.start()
    finally:
        generator.finalize()

    return os.path.join(html_root, 'data')


def tier_files(archive_dir, tier, group_name=None):
    """Return the sorted names of the archive files of one tier, e.g., 'days'."""
    names = []
    for name in os.listdir(archive_dir):
        parsed = weewx.jsongenerator._parse_archive_name(name)
        if parsed and parsed[0] != 'daynight' and parsed[1] == tier \
                and group_name in (None, parsed[0]):
            names.append(name)
    return sorted(names)


def date_of(name):
    """Return the date in the name of an archive file, e.g., '2010-08'."""
    return weewx.jsongenerator._parse_archive_name(name)[2]


class TestPlotDefinitions:

    @staticmethod
    def run(config_dict, skin_dict):
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'], first_run=True,
            stn_info=weewx.station.StationInfo(**cd['Station']))
        try:
            generator.start()
        finally:
            generator.finalize()
        return os.path.join(skin_dict['HTML_ROOT'], 'data')

    @staticmethod
    def archived(data_dir):
        """Return the plot groups that have an archive file for 2010."""
        return sorted(f[:-len('-2010.json')]
                      for f in os.listdir(os.path.join(data_dir, 'archive'))
                      if f.endswith('-2010.json') and not f.startswith('daynight'))

    def test_its_own_section_comes_first(self, config_dict, tmp_path):
        """Plots under [JSONGenerator] win over [ImageGenerator]."""
        skin_dict = build_skin_dict(str(tmp_path))
        skin_dict['JSONGenerator']['day_images'] = {
            'dayown': {'time_length': '6h', 'outTemp': {'label': 'Own'}},
        }
        assert self.archived(self.run(config_dict, skin_dict)) == ['own']

    def test_settings_are_not_mistaken_for_plots(self, config_dict, tmp_path):
        """[[Archive]] is a subsection of [JSONGenerator], but defines no plots.

        Counted as a time period, [[Archive]] would leave the generator nothing to
        draw, and no error in the log.
        """
        data_dir = self.run(config_dict, build_skin_dict(str(tmp_path)))
        assert 'tempdew' in self.archived(data_dir)

    def test_plots_can_live_in_this_generators_own_section(self, config_dict, tmp_path):
        """A skin without an ImageGenerator keeps its plots in [JSONGenerator]."""
        skin_dict = build_skin_dict(str(tmp_path))
        skin_dict['JSONGenerator'].update({
            'chart_line_colors': '#118844',
            'day_images': {
                'time_length': '6h',
                'daymything': {'outTemp': {'label': 'Mine'}},
            },
        })
        del skin_dict['ImageGenerator']
        data_dir = self.run(config_dict, skin_dict)

        assert self.archived(data_dir) == ['mything']
        with open(os.path.join(data_dir, 'archive', 'mything-2010.json'),
                  encoding='utf-8') as fd:
            series = json.load(fd)['series'][0]
        assert series['label'] == 'Mine'
        assert series['color'] == '#118844'
        with open(os.path.join(data_dir, 'skin.json'), encoding='utf-8') as fd:
            assert json.load(fd)['time_lengths'] == {'day_images': 6 * 3600}

    def test_the_image_generator_section_still_serves(self, config_dict, tmp_path):
        """A skin written before the JSON generator needs no new configuration."""
        data_dir = self.run(config_dict, build_skin_dict(str(tmp_path)))
        assert self.archived(data_dir) == ['rain', 'tempdew', 'windvec']

    def test_no_plot_definitions_anywhere_is_reported(self, config_dict, tmp_path,
                                                      caplog):
        """A skin without plots writes nothing, and says so as information.

        A skin may well draw no charts, so this is not an error.
        """
        skin_dict = build_skin_dict(str(tmp_path))
        del skin_dict['ImageGenerator']
        with caplog.at_level(logging.INFO, logger='weewx.jsongenerator'):
            self.run(config_dict, skin_dict)
        assert not os.path.isdir(os.path.join(str(tmp_path), 'data'))
        levels = [r.levelname for r in caplog.records
                  if 'No plot definitions' in r.getMessage()]
        assert levels == ['INFO']

    def test_a_skin_without_a_json_section_runs(self, config_dict, tmp_path):
        """[ImageGenerator] alone is enough.

        search_up() climbs the section tree through .parent. A plain dict in place
        of [JSONGenerator] has no .parent, and every search_up() on it raises.
        """
        skin_dict = build_skin_dict(str(tmp_path))
        del skin_dict['JSONGenerator']
        data_dir = self.run(config_dict, skin_dict)
        assert os.path.exists(os.path.join(data_dir, 'skin.json'))
        assert self.archived(data_dir)


class TestSkinJson:

    @staticmethod
    def skin_json(data_dir):
        with open(os.path.join(data_dir, 'skin.json'), encoding='utf-8') as fd:
            return json.load(fd)

    def test_skin_json_is_written_on_the_first_run_only(self, config_dict, tmp_path):
        path = os.path.join(run_generator(config_dict, tmp_path), 'skin.json')
        with open(path, 'w', encoding='utf-8') as fd:
            fd.write('{}')
        run_generator(config_dict, tmp_path, first_run=False)
        with open(path, encoding='utf-8') as fd:
            assert fd.read() == '{}'

        # A lost skin.json is written again.
        os.remove(path)
        run_generator(config_dict, tmp_path, first_run=False)
        assert self.skin_json(os.path.dirname(path))['time_lengths']

    def test_skin_json_holds_the_time_lengths_and_the_units(self, config_dict, tmp_path):
        skin_json = self.skin_json(run_generator(config_dict, tmp_path))
        assert sorted(skin_json) == ['time_lengths', 'units']
        assert skin_json['time_lengths'] == {'day_images': 27 * 3600,
                                             'week_images': 7 * 86400}

    def test_the_time_period_sets_the_time_length(self, config_dict, tmp_path):
        """A plot's own time_length does not change the one of its time period."""
        skin_dict = build_skin_dict(str(tmp_path))
        day_images = skin_dict['ImageGenerator']['day_images']
        for plotname in day_images.sections:
            day_images[plotname]['time_length'] = '6h'
        skin_json = self.skin_json(TestPlotDefinitions.run(config_dict, skin_dict))
        assert skin_json['time_lengths']['day_images'] == 27 * 3600

    def test_the_index_says_which_units_the_report_used(self, config_dict, tmp_path):
        """units['report'] gives the unit the report renders each unit group in.

        The JavaScript converts, e.g., the forecast, which arrives in Celsius, into that
        unit. Without units['report'], the JavaScript converts the forecast only after
        the viewer picks a unit system by hand.
        """
        data_dir = run_generator(config_dict, tmp_path)
        units = self.skin_json(data_dir)['units']

        # Compared with the unit of an archive file, not with a fixed unit. A fixed
        # unit would only restate the test skin's configuration.
        with open(os.path.join(data_dir, 'archive', 'tempdew-2010.json'),
                  encoding='utf-8') as fd:
            written = json.load(fd)['unit']
        assert units['report'][units['groups']['outTemp']] == written

        # Every unit group that appears has a unit in units['report'].
        assert set(units['report']) >= set(units['groups'].values()) - {None}


class TestDayNight:

    @staticmethod
    def daynight(data_dir):
        with open(os.path.join(data_dir, 'archive', 'daynight-2010.json'),
                  encoding='utf-8') as fd:
            return json.load(fd)

    def test_sunrise_and_sunset_are_written(self, config_dict, tmp_path):
        dn = self.daynight(run_generator(config_dict, tmp_path))

        assert dn['first'] in ('day', 'night')
        assert dn['transitions']
        assert dn['transitions'] == sorted(dn['transitions'])
        assert dn['start'] <= dn['transitions'][0]

    def test_twilight_bands_are_written(self, config_dict, tmp_path):
        dn = self.daynight(run_generator(config_dict, tmp_path))

        bands = dn['twilight']
        assert bands, "no civil twilight written"
        for band in bands:
            assert band['dir'] in ('dawn', 'dusk')
            assert band['from'] < band['to']
            # Civil twilight at 45 degrees latitude lasts about 25 to 40 minutes.
            minutes = (band['to'] - band['from']) / 60.0
            assert 15 < minutes < 90, "implausible twilight of %.0f minutes" % minutes

        # Dawn ends at sunrise, and dusk starts at sunset.
        crossings = set(dn['transitions'])
        last = dn['transitions'][-1]
        for band in bands:
            edge = band['to'] if band['dir'] == 'dawn' else band['from']
            if dn['start'] < edge < last:
                assert edge in crossings


class TestArchive:

    @pytest.fixture(scope='class')
    def archive_dir(self, config_dict, tmp_path_factory):
        """Run the generator once for the tests that only read the archive files.

        Tests that need a run of their own still make it.
        """
        data_dir = run_generator(config_dict, tmp_path_factory.mktemp('archive'))
        return os.path.join(data_dir, 'archive')

    def test_writes_one_file_per_plot_group_and_year(self, archive_dir):
        written = sorted(f for f in os.listdir(archive_dir) if f.endswith('.json'))

        # The test data sit in 2010, and the plot group is 'daytempdew' without 'day'.
        assert 'tempdew-2010.json' in written
        assert 'index.json' in written

    def test_the_values_are_evenly_spaced_and_carry_no_timestamps(self, archive_dir):
        with open(os.path.join(archive_dir, 'tempdew-2010.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == ARCHIVE_RESOLUTION
        assert payload['start'] % ARCHIVE_RESOLUTION == 0
        # The fixed aggregation interval makes a 'time' array unnecessary.
        for series in payload['series']:
            assert 'time' not in series
            assert len(series['values']) == payload['count']

    def test_a_database_without_gaps_gives_a_series_without_gaps(self, archive_dir):
        with open(os.path.join(archive_dir, 'tempdew-2010.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        series = payload['series'][0]
        filled = [i for i, v in enumerate(series['values']) if v is not None]
        assert filled, "archive holds no data at all"
        # The synthetic database has no gaps, so nearly every aggregation interval
        # between the first and the last value holds one.
        assert len(filled) > 0.9 * (filled[-1] - filled[0] + 1)

    def test_the_unit_label_is_only_in_skin_json(self, archive_dir):
        """An archive file names its unit, and skin.json gives the label of each unit.

        A label written anywhere else would be a second copy of the one in skin.json.
        """
        with open(os.path.join(os.path.dirname(archive_dir), 'skin.json'),
                  encoding='utf-8') as fd:
            labels = json.load(fd)['units']['labels']
        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        for group in index['groups']:
            assert 'unit_label' not in group and 'unit' not in group, group['name']

        names = [n for n in os.listdir(archive_dir)
                 if n.endswith('.json') and n != 'index.json'
                 and not n.startswith('daynight')]
        assert names
        for name in names:
            with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
                payload = json.load(fd)
            assert 'unit_label' not in payload, name
            assert payload['unit'] in labels, name

    def test_fresh_files_are_not_rewritten(self, config_dict, tmp_path):
        """A second run right after the first rewrites no file.

        Reports run every archive interval, so every run after the first must cost
        almost nothing.
        """
        data_dir = run_generator(config_dict, tmp_path)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path)

        assert os.path.getmtime(path) == before

    def test_a_new_aggregation_interval_rewrites_the_file(self, config_dict, tmp_path):
        """The year in progress is rewritten when the database moves on.

        That is once the database reaches the next aggregation interval.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path,
                                 gen_ts=stop_ts - ARCHIVE_RESOLUTION)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path, gen_ts=stop_ts)

        assert os.path.getmtime(path) != before

    def test_catchup_data_reach_the_archive(self, config_dict, tmp_path):
        """Archive records caught up after a restart reach the archive files.

        After a restart, the logger hands over what it recorded meanwhile. The file on
        disk is then minutes old but days behind. Reported by tkeffer in #1111.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path,
                                 gen_ts=stop_ts - 2 * 86400)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        with open(path, encoding='utf-8') as fd:
            before = json.load(fd)

        # The file is seconds old at this point. Only the data have moved.
        run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        with open(path, encoding='utf-8') as fd:
            after = json.load(fd)

        assert after['newest'] > before['newest']
        filled = lambda p: sum(1 for v in p['series'][0]['values'] if v is not None)
        # Two days of catch-up, so nearly two days of aggregation intervals have to fill
        # in.
        count = 2 * 86400 // ARCHIVE_RESOLUTION
        assert filled(after) - filled(before) > 0.8 * count

    def test_an_import_rebuilds_finished_years(self, config_dict, tmp_path):
        """An import of older data rebuilds the finished years.

        A finished year is otherwise written once and skipped forever, so imported
        history would never show up.
        """
        data_dir = run_generator(config_dict, tmp_path)
        index_path = os.path.join(data_dir, 'archive', 'index.json')
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        # Claim the last run only saw data from a week in. Anything earlier than that
        # is new, exactly as it would be after 'weectl import'.
        with open(index_path, encoding='utf-8') as fd:
            index = json.load(fd)
        index['first'] += 7 * 86400
        with open(index_path, 'w', encoding='utf-8') as fd:
            json.dump(index, fd)

        run_generator(config_dict, tmp_path)

        assert os.path.getmtime(path) != before

    def test_archive_index_lists_years(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert 'tempdew' in groups
        assert '2010' in groups['tempdew']['years']
        assert groups['tempdew']['year_intervals']['2010'] == ARCHIVE_RESOLUTION

    def test_recent_months_get_a_shorter_aggregation_interval(self, config_dict,
                                                              tmp_path):
        """Recent months get a shorter aggregation interval than the year files.

        An aggregation interval of one hour flattens a day.
        """
        data_dir = run_generator(config_dict, tmp_path,
                                 archive_options={'months': '2',
                                                  'month_resolution': '300'})
        archive_dir = os.path.join(data_dir, 'archive')
        fine = tier_files(archive_dir, 'months')
        assert fine, "no month files written"

        with open(os.path.join(archive_dir, fine[0]), encoding='utf-8') as fd:
            payload = json.load(fd)
        assert payload['interval'] == 300

        # The year file of the same plot group is still there, at the longer
        # aggregation interval.
        group_name = weewx.jsongenerator._parse_archive_name(fine[0])[0]
        with open(os.path.join(archive_dir, '%s-2010.json' % group_name),
                  encoding='utf-8') as fd:
            assert json.load(fd)['interval'] == ARCHIVE_RESOLUTION

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        groups = {g['name']: g for g in index['groups']}
        # The archive index names the month, so the JavaScript knows to ask for it.
        assert date_of(fine[0]) in groups[group_name]['months']
        assert groups[group_name]['month_intervals'][date_of(fine[0])] == 300

    def test_a_month_resolution_that_is_not_finer_is_refused(self, config_dict,
                                                             tmp_path):
        """A month_resolution that is not finer than year_resolution writes no month files.

        The usual cause is '5m', which means five months.
        """
        data_dir = run_generator(config_dict, tmp_path,
                                 archive_options={'months': '2',
                                                  'month_resolution': '28800'})
        archive_dir = os.path.join(data_dir, 'archive')
        assert not tier_files(archive_dir, 'months')


class TestArchiveExtension:
    """Extending an archive file on disk instead of calculating the whole timespan.

    Only the aggregation intervals from the newest of the file on disk on are
    calculated. The tests check that the result equals a full rebuild.
    """

    # 'newest' records when a file was written, not what it holds. A run whose
    # aggregation interval has not moved skips the file. So after a chain of runs,
    # 'newest' can come from an earlier run than in a single rebuild. The JavaScript
    # does not draw it.
    BOOKKEEPING = ('newest',)

    @classmethod
    def payloads(cls, archive_dir, only=None):
        """Return the drawable contents of every archive file, keyed by file name."""
        out = {}
        for name in sorted(os.listdir(archive_dir)):
            if not name.endswith('.json') or name == 'index.json':
                continue
            if only and only not in name:
                continue
            with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
                payload = json.load(fd)
            out[name] = {k: v for k, v in payload.items() if k not in cls.BOOKKEEPING}
        return out

    def walk_forward(self, config_dict, root, first_ts, last_ts, step,
                     archive_options=None):
        """Run once per step from first_ts to last_ts, extending each time."""
        options = {'rebuild': '0'}
        options.update(archive_options or {})
        gen_ts = first_ts
        data_dir = None
        while True:
            data_dir = run_generator(config_dict, root, gen_ts=gen_ts,
                                     archive_options=options)
            if gen_ts >= last_ts:
                break
            # The last run lands on 'last_ts', whatever the step. A DST day is 23 or
            # 25 hours long, so a fixed step may not divide the timespan. Without the min(),
            # the walk would stop short of the rebuild it is compared with.
            gen_ts = min(gen_ts + step, last_ts)
        return os.path.join(data_dir, 'archive')

    def test_extending_matches_a_full_rebuild(self, config_dict, tmp_path_factory):
        """Six runs, each extending the last, against one that does the lot."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        first_ts = stop_ts - 6 * ARCHIVE_RESOLUTION

        grown = self.walk_forward(config_dict, tmp_path_factory.mktemp('grown'),
                                  first_ts, stop_ts, ARCHIVE_RESOLUTION)
        built = os.path.join(
            run_generator(config_dict, tmp_path_factory.mktemp('built'),
                          gen_ts=stop_ts),
            'archive')

        assert self.payloads(grown) == self.payloads(built)

    def test_extending_matches_a_full_rebuild_over_a_dst_boundary(
            self, config_dict, tmp_path_factory):
        """Extending matches a full rebuild across a DST change.

        intervalgen() aligns aggregation intervals on local time, so one can be three
        hours long. An extending run starts later than the run that first wrote the
        file. Across a DST change, the two runs could disagree about where an
        aggregation interval begins.
        """
        # 2010-03-14 02:00 PST is 03:00 PDT. Straddle it.
        first_ts = int(time.mktime((2010, 3, 13, 12, 0, 0, 0, 0, -1)))
        last_ts = int(time.mktime((2010, 3, 15, 0, 0, 0, 0, 0, -1)))
        # Both sides must end on the same boundary. A file is rewritten only when its
        # newest reaches the next aggregation interval. A walk ending inside one would
        # leave an older file than the rebuild writes.
        last_ts -= last_ts % ARCHIVE_RESOLUTION

        grown = self.walk_forward(config_dict, tmp_path_factory.mktemp('dst_grown'),
                                  first_ts, last_ts, ARCHIVE_RESOLUTION)
        built = os.path.join(
            run_generator(config_dict, tmp_path_factory.mktemp('dst_built'),
                          gen_ts=last_ts), 'archive')

        assert self.payloads(grown) == self.payloads(built)

    def test_extending_matches_a_full_rebuild_in_the_month_tier(
            self, config_dict, tmp_path_factory):
        """Extending matches a full rebuild in the month tier.

        Only the month in progress is compared. A finished month is written once and
        kept, so its start depends on the run that wrote it.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'months': '2', 'month_resolution': '3600'}
        first_ts = stop_ts - 4 * 3600
        current_month = '-%s.json' % time.strftime('%Y-%m', time.localtime(stop_ts))

        grown = self.walk_forward(config_dict, tmp_path_factory.mktemp('fine_grown'),
                                  first_ts, stop_ts, 3600, options)
        built = os.path.join(
            run_generator(config_dict, tmp_path_factory.mktemp('fine_built'),
                          gen_ts=stop_ts, archive_options=options),
            'archive')

        grown_files = self.payloads(grown, only=current_month)
        assert grown_files, "no month file for the month in progress"
        assert grown_files == self.payloads(built, only=current_month)

    def test_extending_reads_only_the_new_aggregation_intervals(self, config_dict,
                                                                tmp_path, monkeypatch):
        """Extending a year file reads from its newest on, not the whole year."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path,
                      gen_ts=stop_ts - ARCHIVE_RESOLUTION,
                      archive_options={'rebuild': '0'})

        calls = []
        original = weewx.xtypes.get_series
        monkeypatch.setattr(weewx.xtypes, 'get_series',
                            lambda *args, **kwargs: calls.append(args[1])
                            or original(*args, **kwargs))

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options={'rebuild': '0'})

        assert calls, "the second run asked for nothing at all"
        # A query over more than a day means the year was calculated again.
        assert max(timespan.stop - timespan.start for timespan in calls) <= 86400

    def test_a_rebuild_happens_once_a_calendar_day(self, config_dict, tmp_path):
        """A full rebuild runs once per calendar day.

        Only a rebuild picks up changes older than the last run.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        index_path = lambda d: os.path.join(d, 'archive', 'index.json')
        rebuilt_at = lambda d: json.load(open(index_path(d), encoding='utf-8'))['rebuilt']

        data_dir = run_generator(config_dict, tmp_path,
                                 gen_ts=stop_ts - 86400)
        first = rebuilt_at(data_dir)
        assert first is not None

        # Later the same day: extended, so 'rebuilt' does not move.
        run_generator(config_dict, tmp_path,
                      gen_ts=stop_ts - 86400 + ARCHIVE_RESOLUTION)
        assert rebuilt_at(data_dir) == first

        # The next day: rebuilt, so it does.
        run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        assert rebuilt_at(data_dir) != first

    def test_rebuilding_can_be_turned_off(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 86400,
                      archive_options={'rebuild': '0'})
        path = os.path.join(str(tmp_path), 'data', 'archive', 'index.json')
        with open(path, encoding='utf-8') as fd:
            assert json.load(fd)['rebuilt'] is None

    def test_a_file_that_does_not_match_is_rebuilt(self, config_dict, tmp_path):
        """A file whose series differ from the plot's is rebuilt, not extended.

        A changed skin leaves a file with the same name and aggregation interval but
        other series. Extending it would put one observation type's values under
        another one's label.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path,
                      gen_ts=stop_ts - ARCHIVE_RESOLUTION,
                      archive_options={'rebuild': '0'})
        path = os.path.join(str(tmp_path), 'data', 'archive', 'tempdew-2010.json')

        with open(path, encoding='utf-8') as fd:
            payload = json.load(fd)
        payload['series'][0]['obs_type'] = 'somethingElse'
        payload['series'][0]['values'] = [-99.0] * payload['count']
        with open(path, 'w', encoding='utf-8') as fd:
            json.dump(payload, fd)

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options={'rebuild': '0'})

        with open(path, encoding='utf-8') as fd:
            after = json.load(fd)
        assert after['series'][0]['obs_type'] == 'outTemp'
        assert -99.0 not in after['series'][0]['values']


class TestExtends:
    """Whether an archive file on disk can be extended into the one being built."""

    @staticmethod
    def file(**overrides):
        payload = {'start': 1000, 'interval': 100, 'count': 10, 'newest': 1900,
                   'series': [{'obs_type': 'outTemp', 'values': [1.0] * 10}]}
        payload.update(overrides)
        return payload

    def test_a_file_at_the_same_aggregation_interval_extends(self):
        assert weewx.jsongenerator._extends(self.file(), 1000, 100, 20)

    @pytest.mark.parametrize('overrides, reason', [
        ({'start': 2000}, 'the start moved'),
        ({'interval': 50}, 'the aggregation interval changed'),
        ({'count': 30}, 'more aggregation intervals than wanted, e.g., after a clock '
                        'went backwards'),
        ({'count': 'nonsense'}, 'not a number'),
        ({'newest': None}, 'no newest'),
        ({'newest': 500}, 'a newest before the file starts'),
        ({'series': None}, 'no series'),
    ])
    def test_a_file_that_cannot_be_extended(self, overrides, reason):
        assert not weewx.jsongenerator._extends(self.file(**overrides), 1000, 100, 20), \
            reason


class TestAggregation:
    """The aggregates in an archive file are the ones the database gives."""

    def test_vecdir_matches_the_database(self, config_dict, tmp_path):
        """Each bearing in the file is the one the database gives."""
        skin_dict = build_skin_dict(str(tmp_path))
        skin_dict['ImageGenerator']['day_images']['daywinddir'] = {
            'windDir': {}}
        data_dir = TestPlotDefinitions.run(config_dict, skin_dict)
        with open(os.path.join(data_dir, 'archive', 'winddir-2010.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)
        series = payload['series'][0]
        assert series['aggregate_type'] == 'vecdir'

        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        binder = weewx.manager.DBBinder(cd)
        try:
            mgr = binder.get_manager('wx_binding')
            start, interval = payload['start'], payload['interval']
            begins, ends = weewx.jsongenerator._intervals(
                start, start + payload['count'] * interval, interval)
            # Before and after the change to DST, which moves the aggregation intervals.
            for i in (10, 500, 1000):
                timespan = weeutil.weeutil.TimeSpan(begins[i], ends[i])
                expected = weewx.xtypes.get_aggregate('wind', timespan, 'vecdir', mgr)[0]
                position = (begins[i] - start) // interval
                assert series['values'][position] == pytest.approx(expected, abs=0.002), i
        finally:
            binder.close()


class TestTiers:
    """Which aggregation interval a calendar year's archive file has."""

    @staticmethod
    def interval(year, this_year=2026, years=2, year_resolution=3600,
                 old_year_resolution=14400, old_interval=None):
        return weewx.jsongenerator._year_interval(year, this_year, years, year_resolution,
                                                  old_year_resolution, old_interval)

    def test_the_recent_years_get_the_shorter_aggregation_interval(self):
        assert self.interval(2026) == 3600
        assert self.interval(2025) == 3600

    def test_older_years_get_the_longer_one(self):
        assert self.interval(2024) == 14400
        assert self.interval(2016) == 14400

    def test_without_a_recent_window_every_year_is_the_same(self):
        assert self.interval(2016, years=0) == 3600

    def test_a_file_already_shorter_keeps_what_it_has(self):
        """Coarsening a year would cost a year of queries to end up with less."""
        assert self.interval(2016, old_interval=3600) == 3600

    def test_a_file_longer_than_wanted_is_refined(self):
        assert self.interval(2026, old_interval=14400) == 3600


class TestMonthsBack:

    @staticmethod
    def at(year, month, day, months, floor=0):
        last = int(time.mktime((year, month, day, 12, 0, 0, 0, 0, -1)))
        start = weewx.jsongenerator._months_back(last, months, floor)
        return time.strftime('%Y-%m-%d', time.localtime(start))

    def test_one_month_is_the_month_in_progress(self):
        assert self.at(2026, 8, 28, 1) == '2026-08-01'

    def test_two_months_reaches_the_first_of_last_month(self):
        assert self.at(2026, 8, 28, 2) == '2026-07-01'

    def test_it_crosses_the_new_year(self):
        assert self.at(2026, 2, 3, 4) == '2025-11-01'

    def test_it_does_not_go_before_the_oldest_archive_record(self):
        floor = int(time.mktime((2026, 6, 15, 0, 0, 0, 0, 0, -1)))
        start = weewx.jsongenerator._months_back(
            int(time.mktime((2026, 8, 28, 12, 0, 0, 0, 0, -1))), 6, floor)
        assert start == floor


class TestArchiveMemory:
    """What the archive index knows about archive files not written this run."""

    def test_a_missing_index_reads_as_empty_after_another(self, config_dict, tmp_path):
        """Each read of an archive index starts empty, whatever was read before.

        Two reports in one weewxd, or two report cycles, must not see each other's
        archive index.
        """
        data_dir = run_generator(config_dict, tmp_path / 'one')
        read = weewx.jsongenerator.JSONGenerator._read_archive_index
        assert read(os.path.join(data_dir, 'archive'))['years']

        empty = read(str(tmp_path / 'nowhere'))
        assert empty['years'] == {} and empty['titles'] == {}
        assert empty['first'] is None and empty['rebuilt'] is None

    def test_finished_months_stay_available(self, config_dict, tmp_path):
        """The archive index still names finished months outside the 'months' window.

        Only the months inside the window are written. Older month files on disk must
        stay in the archive index, or the JavaScript cannot see them.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'months': '2', 'month_resolution': '3600'}
        # Two runs a month apart, so the first month falls out of the window.
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)

        archive_dir = os.path.join(data_dir, 'archive')
        on_disk = set(tier_files(archive_dir, 'months'))
        assert on_disk, "no month files at all"

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        named = set()
        for group in index['groups']:
            for date in group.get('months', {}):
                named.add('%s-%s.json' % (group['name'], date))
        assert on_disk <= named, "files on disk that the archive index does not name"

    def test_a_lost_index_is_rebuilt_from_the_directory(self, config_dict, tmp_path):
        """A lost index.json is restored from the archive files in the directory.

        Otherwise, deleting index.json would mean calculating every archive file again.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'months': '2', 'month_resolution': '3600'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        index_path = os.path.join(archive_dir, 'index.json')
        with open(index_path, encoding='utf-8') as fd:
            before = json.load(fd)

        os.remove(index_path)
        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options=options)

        with open(index_path, encoding='utf-8') as fd:
            after = json.load(fd)
        named = lambda idx: {(g['name'], y) for g in idx['groups']
                             for y in list(g.get('years', {}))
                             + list(g.get('months', {}))}
        assert named(after) == named(before)

    def test_the_index_drops_files_that_have_gone(self, config_dict, tmp_path):
        """The archive index drops a file that was deleted from the directory.

        A name without a file sends the JavaScript after a 404. A deleted file inside
        the window is written again, so the test deletes a month outside the window.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'months': '2', 'month_resolution': '3600'}
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        months = sorted({m for g in index['groups'] for m in g.get('months', {})})
        assert len(months) > 1, "only one month written, nothing is out of the window"
        oldest = months[0]
        gone = [f for f in os.listdir(archive_dir) if f.endswith('-%s.json' % oldest)]
        assert gone
        for name in gone:
            os.remove(os.path.join(archive_dir, name))

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options=options)

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        for group in index['groups']:
            assert oldest not in group.get('months', {}), \
                "archive index still names %s for %s" % (oldest, group['name'])

    def test_the_index_records_the_aggregation_interval_of_each_file(self, config_dict,
                                                                     tmp_path):
        """Archive files can differ in aggregation interval, so it is named per file."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert groups['tempdew']['year_intervals']['2010'] == ARCHIVE_RESOLUTION


class TestDayTier:
    """One archive file per day, kept for a while and then not."""

    OPTIONS = {'days': '5', 'day_resolution': '1800'}

    @staticmethod
    def days(archive_dir):
        return sorted({date_of(f) for f in tier_files(archive_dir, 'days')})

    def test_one_file_per_day(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        archive_dir = os.path.join(data_dir, 'archive')

        days = self.days(archive_dir)
        assert len(days) == 5, days
        assert days[-1] == time.strftime('%Y-%m-%d', time.localtime(stop_ts))

    def test_the_aggregation_interval_is_the_archive_interval(self, config_dict,
                                                              tmp_path):
        """A day_resolution of 0 uses the archive interval of the day's records."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'days': '2', 'day_resolution': '0'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = tier_files(archive_dir, 'days')[0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == parameters.synthetic_dict['interval']

    def test_a_day_takes_the_archive_interval_most_of_its_records_have(self):
        """A station that changes its archive interval late in a day keeps the old one.

        Taken from the newest record alone, the whole day would get the new archive
        interval, and most of its aggregation intervals would stay empty.
        """
        import sqlite3
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE archive (dateTime INTEGER, interval INTEGER)')
        # Ten records five minutes apart, then three a minute apart.
        stamps = [300 * n for n in range(1, 11)] + [3000 + 60 * n for n in range(1, 4)]
        connection.executemany('INSERT INTO archive VALUES (?, ?)',
                               [(ts, 5 if ts <= 3000 else 1) for ts in stamps])

        class Manager:
            table_name = 'archive'

            @staticmethod
            def getSql(sql, args):
                return connection.execute(sql, tuple(args)).fetchone()

        day = weeutil.weeutil.TimeSpan(0, 86400)
        assert weewx.jsongenerator._archive_interval_of_day(Manager, day) == 300
        # A day without records falls back to five minutes.
        empty = weeutil.weeutil.TimeSpan(86400, 2 * 86400)
        assert weewx.jsongenerator._archive_interval_of_day(Manager, empty) == 300

    def test_days_that_fall_out_of_the_window_are_removed(self, config_dict, tmp_path):
        """Day files that fall out of the 'days' window are deleted.

        Otherwise the day tier would grow by one file per plot group per day, forever.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 3 * 86400,
                      archive_options=self.OPTIONS)
        archive_dir = os.path.join(str(tmp_path), 'data', 'archive')
        before = self.days(archive_dir)

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options=self.OPTIONS)
        after = self.days(archive_dir)

        assert len(after) == 5, after
        assert after[0] > before[0], "the window did not move on"
        for date in before:
            if date < after[0]:
                assert not [f for f in os.listdir(archive_dir)
                            if f.endswith('-%s.json' % date)]

        # The archive index names no deleted day, or the JavaScript would fetch it and
        # get a 404.
        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        for group in index['groups']:
            assert sorted(group['days']) == after, group['name']
            assert sorted(group['day_intervals']) == after, group['name']

    def test_the_index_names_the_days(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert len(groups['tempdew']['days']) == 5
        assert set(groups['tempdew']['day_intervals'].values()) == {1800}

    def test_days_0_turns_it_off(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive_options={'days': '0'})
        archive_dir = os.path.join(data_dir, 'archive')
        assert not tier_files(archive_dir, 'days')


def slow_clock(monkeypatch):
    """Make every file cost the generator 50 s, so a budget of 30 s is spent at once.

    The clock replaces the module 'time' inside weewx.jsongenerator only. Every other
    function of the module stays the real one.
    """
    ticks = itertools.count(0, 50)
    fake = types.SimpleNamespace(**{name: getattr(time, name) for name in dir(time)
                                    if not name.startswith('_')})
    fake.time = lambda: next(ticks)
    monkeypatch.setattr(weewx.jsongenerator, 'time', fake)


class TestBudget:
    """Building a long history across several runs instead of one long one."""

    OPTIONS = {'budget': '30', 'months': '2', 'month_resolution': '3600'}

    @staticmethod
    def archive(data_dir):
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        return {(g['name'], date) for g in index['groups'] for tier, _ in
                weewx.jsongenerator.TIERS for date in g.get(tier, {})}

    def test_a_spent_budget_defers_whole_files(self, config_dict, tmp_path, monkeypatch):
        """Once the budget is spent, a run starts no further file.

        The newest timespan comes first, so the month in progress is written before
        the month before it.
        """
        slow_clock(monkeypatch)
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        this_month = time.strftime('%Y-%m', time.localtime(stop_ts))
        assert self.archive(data_dir) == {('tempdew', this_month)}

    def test_later_runs_finish_the_archive_files(self, config_dict, tmp_path_factory,
                                                 monkeypatch):
        """Built across runs or all at once, the files have to say the same thing."""
        slow_clock(monkeypatch)
        stop_ts = parameters.synthetic_dict['stop_ts']
        pieces = tmp_path_factory.mktemp('pieces')
        seen = []
        for _ in range(20):
            data_dir = run_generator(config_dict, pieces, gen_ts=stop_ts,
                                     archive_options=self.OPTIONS)
            seen.append(len(self.archive(data_dir)))
            if len(seen) > 1 and seen[-1] == seen[-2]:
                break
        assert seen == sorted(seen) and seen[-1] > seen[0], seen

        whole = tmp_path_factory.mktemp('whole')
        options = dict(self.OPTIONS, budget='0')
        one_go = run_generator(config_dict, whole, gen_ts=stop_ts, archive_options=options)
        assert self.archive(data_dir) == self.archive(one_go)
        for name in tier_files(os.path.join(one_go, 'archive'), 'months') \
                + tier_files(os.path.join(one_go, 'archive'), 'years'):
            with open(os.path.join(data_dir, 'archive', name), encoding='utf-8') as fd:
                built_up = json.load(fd)
            with open(os.path.join(one_go, 'archive', name), encoding='utf-8') as fd:
                assert json.load(fd)['series'] == built_up['series'], name

    def test_deferred_files_stay_in_the_index(self, config_dict, tmp_path, monkeypatch):
        """A run that the budget stops early keeps the older files in the archive index.

        Dropping them would hide the history from the JavaScript until a later run
        reaches them again.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        before = self.archive(run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                            archive_options=self.OPTIONS))
        slow_clock(monkeypatch)
        # An hour later, with a rebuild due, every file is due, and the budget is spent
        # after the first.
        after = self.archive(run_generator(
            config_dict, tmp_path, gen_ts=stop_ts + 3600,
            archive_options=dict(self.OPTIONS, rebuild='1')))
        assert after == before

    def test_the_day_view_is_never_deferred(self, config_dict, tmp_path, monkeypatch):
        """The budget never defers the day tier, which the JavaScript draws today from."""
        slow_clock(monkeypatch)
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(
            config_dict, tmp_path, gen_ts=stop_ts,
            archive_options=dict(self.OPTIONS, days='3', day_resolution='1800'))
        archive_dir = os.path.join(data_dir, 'archive')

        days = {date_of(f) for f in tier_files(archive_dir, 'days', 'tempdew')}
        assert len(days) == 3, days


class TestArchiveSeriesShapes:
    """What a series in an archive file carries beyond its values."""

    def test_a_wind_vector_keeps_its_components(self, config_dict, tmp_path):
        """A wind vector series keeps its components in 'vector_x' and 'vector_y'.

        Without them, the JavaScript could not draw the wind vector plot from the
        archive files.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        with open(os.path.join(data_dir, 'archive', 'windvec-2010.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)

        series = payload['series'][0]
        assert series['plot_type'] == 'vector'
        assert len(series['vector_x']) == payload['count']
        assert len(series['vector_y']) == payload['count']
        # The magnitude stays in 'values', so a reader that knows nothing about
        # vectors still gets a line it can draw.
        pairs = [(x, y, v) for x, y, v in zip(series['vector_x'], series['vector_y'],
                                              series['values']) if v is not None]
        assert pairs
        for x, y, v in pairs[:20]:
            assert abs((x ** 2 + y ** 2) ** 0.5 - v) < 0.01

    def test_a_line_keeps_its_own_aggregation_interval(self, config_dict, tmp_path):
        """A bar with 'aggregate_interval = 3600' stays hourly in a day file at 900 s.

        Summing per 900 s would give a fraction of the hourly total under an hourly
        label, drawn as a row of hairline bars.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'days': '2', 'day_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = tier_files(archive_dir, 'days', 'rain')[0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == 900
        values = payload['series'][0]['values']
        filled = [i for i, v in enumerate(values) if v is not None]
        assert filled, "no rain at all"
        # An hourly total in a file at a quarter of an hour lands at every fourth
        # position.
        gaps = {b - a for a, b in zip(filled, filled[1:])}
        assert gaps and min(gaps) >= 4, \
            "totals are closer together than the hour they are totalled over: %s" % sorted(gaps)[:5]

    def test_finished_days_meet_without_a_seam(self, config_dict, tmp_path):
        """Each day file ends exactly where the next one starts.

        A day file with an aggregation interval past midnight shares it with the next
        file. No run fills it, because the day is finished and its file is skipped. The
        JavaScript then shows a gap between each pair of days.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'days': '5', 'day_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        files = tier_files(archive_dir, 'days', 'tempdew')
        assert len(files) > 2, files

        extents = []
        for name in files:
            with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
                payload = json.load(fd)
            extents.append((name, payload['start'], payload['count'],
                            payload['interval']))

        # The last file is the day still filling up, so it stops where the database
        # does.
        for (name, start, count, interval), (_, later, _, _) in zip(extents, extents[1:]):
            assert start + count * interval == later, (
                "%s ends at %d, but the next file starts at %d"
                % (name, start + count * interval, later))

    def test_a_finished_day_holds_nothing_from_the_next(self, config_dict, tmp_path):
        """An hourly bar is not placed an aggregation interval early.

        get_series() clips its last aggregation interval to the end of the timespan, so
        the last bar of a day is shorter than an hour. Placed by its end, the bar would
        land one position early and overlap the bar before it.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'days': '5', 'day_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        names = tier_files(archive_dir, 'days', 'rain')
        assert len(names) > 2, names

        # The day still filling up counts too. Its last interval is the one
        # get_series() clips, so it is where a bar goes astray first.
        for name in names:
            with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
                payload = json.load(fd)
            every = payload['series'][0]['aggregate_interval'] // payload['interval']
            filled = [i for i, v in enumerate(payload['series'][0]['values'])
                      if v is not None]
            if len(filled) < 2:
                continue
            gaps = {b - a for a, b in zip(filled, filled[1:])}
            assert min(gaps) >= every, (
                "%s files an hourly bar %d positions after the last, not %d: %s"
                % (name, min(gaps), every, filled[-6:]))
            assert max(filled) < payload['count'], (
                "%s fills position %d of %d" % (name, max(filled), payload['count']))

    def test_named_types_carry_their_extremes(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options={'extremes': 'outTemp'})
        with open(os.path.join(data_dir, 'archive', 'tempdew-2010.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)

        temp = payload['series'][0]
        assert temp['obs_type'] == 'outTemp'
        assert len(temp['min']) == payload['count']
        assert len(temp['max']) == payload['count']
        for lo, mid, hi in zip(temp['min'], temp['values'], temp['max']):
            if None in (lo, mid, hi):
                continue
            assert lo <= mid <= hi

        # dewpoint was not named, so it carries no extremes.
        assert 'min' not in payload['series'][1]

    def test_a_type_not_named_carries_no_extremes(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options={'extremes': 'windGust'})
        with open(os.path.join(data_dir, 'archive', 'tempdew-2010.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)
        assert 'min' not in payload['series'][0]

    def test_a_bar_carries_the_extremes_of_each_interval_of_the_file(self, config_dict,
                                                                    tmp_path):
        """The hourly rain bar in a day file at fifteen minutes carries the extremes.

        The extremes are per aggregation interval of the file, not of the bar, so the
        values of the bar are sorted into the aggregation intervals of the file a
        second time.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'days': '2', 'day_resolution': '900', 'extremes': 'rain'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = tier_files(archive_dir, 'days', 'rain')[0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)
        series = payload['series'][0]
        assert series['aggregate_interval'] == 3600
        assert len(series['max']) == payload['count']

        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        binder = weewx.manager.DBBinder(cd)
        try:
            mgr = binder.get_manager('wx_binding')
            start, interval = payload['start'], payload['interval']
            for i, highest in enumerate(series['max']):
                timespan = weeutil.weeutil.TimeSpan(start + i * interval,
                                                    start + (i + 1) * interval)
                expected = weewx.units.convert(
                    weewx.xtypes.get_aggregate('rain', timespan, 'max', mgr),
                    payload['unit'])
                if expected[0] is None:
                    assert highest is None, i
                else:
                    assert highest == pytest.approx(expected[0], abs=0.001), i
            assert any(highest is not None for highest in series['max'])
        finally:
            binder.close()

    def test_extending_carries_the_extra_arrays_too(self, config_dict,
                                                    tmp_path_factory):
        """Vectors and extremes have to survive the extending path, like values do."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'extremes': 'outTemp', 'rebuild': '0'}

        grown = tmp_path_factory.mktemp('shapes_grown')
        for n in range(4, 0, -1):
            run_generator(config_dict, grown, archive_options=options,
                          gen_ts=stop_ts - (n - 1) * ARCHIVE_RESOLUTION)
        built = tmp_path_factory.mktemp('shapes_built')
        run_generator(config_dict, built, gen_ts=stop_ts,
                      archive_options=options)

        for name in ('tempdew-2010.json', 'windvec-2010.json'):
            with open(os.path.join(str(grown), 'data', 'archive', name),
                      encoding='utf-8') as fd:
                a = json.load(fd)
            with open(os.path.join(str(built), 'data', 'archive', name),
                      encoding='utf-8') as fd:
                b = json.load(fd)
            assert a['series'] == b['series'], name


class TestRebuildDue:

    DAY = 86400

    def test_never_rebuilt_means_rebuild(self):
        assert weewx.jsongenerator._rebuild_due(None, 1000, self.DAY)

    def test_turned_off(self):
        assert not weewx.jsongenerator._rebuild_due(None, 1000, 0)

    def test_same_calendar_day(self):
        morning = int(time.mktime((2010, 3, 1, 8, 0, 0, 0, 0, -1)))
        evening = int(time.mktime((2010, 3, 1, 23, 59, 0, 0, 0, -1)))
        assert not weewx.jsongenerator._rebuild_due(morning, evening, self.DAY)

    def test_over_midnight(self):
        """Two runs two minutes apart, across midnight, trigger a rebuild."""
        before = int(time.mktime((2010, 3, 1, 23, 59, 0, 0, 0, -1)))
        after = int(time.mktime((2010, 3, 2, 0, 1, 0, 0, 0, -1)))
        assert weewx.jsongenerator._rebuild_due(before, after, self.DAY)

    def test_a_station_that_was_off_over_midnight_still_rebuilds(self):
        before = int(time.mktime((2010, 3, 1, 20, 0, 0, 0, 0, -1)))
        after = int(time.mktime((2010, 3, 3, 9, 0, 0, 0, 0, -1)))
        assert weewx.jsongenerator._rebuild_due(before, after, self.DAY)

    def test_under_a_day_falls_back_to_elapsed_time(self):
        assert weewx.jsongenerator._rebuild_due(1000, 1000 + 3600, 3600)
        assert not weewx.jsongenerator._rebuild_due(1000, 1000 + 3599, 3600)


class TestArchiveSettings:

    def test_the_horizon_skin_sets_the_defaults(self):
        """The options in the Horizon skin.conf are examples, not changes.

        A default that differs from what the skin sets is a default nobody uses.
        """
        conf = configobj.ConfigObj(os.path.join(TestSkinLocalization.SKIN, 'skin.conf'),
                                   encoding='utf-8', interpolation=False)
        arch_dict = conf['JSONGenerator']['Archive']
        assert weewx.jsongenerator._archive_settings(arch_dict) \
            == weewx.jsongenerator._archive_settings({})


class TestSkinLocalization:
    """Every string the Horizon skin asks for must exist in en.conf.

    English is the fallback, so a string missing from en.conf shows as its raw key.
    Other languages may lag, because an untranslated string falls back to English. For
    them, the tests only check that the file parses.
    """

    SKIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        'weewx_data', 'skins', 'Horizon')

    @staticmethod
    def _requested(skin_dir):
        import glob
        import re
        gettext = re.compile(r"\$gettext\(\s*(['\"])(.*?)\1\s*\)", re.S)
        pgettext = re.compile(r"\$pgettext\(\s*(['\"])(.*?)\1\s*,\s*(['\"])(.*?)\3\s*\)", re.S)

        plain, ctx = set(), set()
        for path in glob.glob(os.path.join(skin_dir, '*.tmpl')) \
                + glob.glob(os.path.join(skin_dir, '*.inc')):
            with open(path, encoding='utf-8') as fd:
                text = fd.read()
            for _, s in gettext.findall(text):
                if '$' not in s:          # skip $gettext($period.capitalize())
                    plain.add(s)
            for _, c, _, s in pgettext.findall(text):
                ctx.add((c, s))

        # The period names go through $gettext($period.capitalize()).
        plain.update(['Day', 'Week', 'Month', 'Year', 'Rainyear'])
        return plain, ctx

    def _texts(self, code):
        path = os.path.join(self.SKIN, 'lang', '%s.conf' % code)
        conf = configobj.ConfigObj(path, encoding='utf-8', interpolation=False)
        texts = conf.get('Texts', {})
        plain = set(texts.scalars) if hasattr(texts, 'scalars') else set()
        ctx = set()
        for sub in (texts.sections if hasattr(texts, 'sections') else []):
            for key in texts[sub].scalars:
                ctx.add((sub, key))
        return plain, ctx

    def test_english_is_complete(self):
        wanted, wanted_ctx = self._requested(self.SKIN)
        assert wanted, "no translatable strings found -- has the skin moved?"

        have, have_ctx = self._texts('en')
        missing = sorted(wanted - have)
        missing_ctx = sorted(wanted_ctx - have_ctx)

        assert not missing, "en.conf is missing: %s" % ', '.join(missing)
        assert not missing_ctx, "en.conf is missing (with context): %s" % missing_ctx

    def test_every_language_file_parses(self):
        import glob
        for path in glob.glob(os.path.join(self.SKIN, 'lang', '*.conf')):
            configobj.ConfigObj(path, encoding='utf-8', interpolation=False,
                                file_error=True)


class TestHelpers:

    @pytest.mark.parametrize("given,expected", [
        ('#4282b4', '#4282b4'),        # already CSS
        ('blue', 'blue'),              # English name, valid CSS
        ('0xb44242', '#4242b4'),       # WeeWX's BGR notation, byte-swapped
        ('0x0000ff', '#ff0000'),       # pure red in BGR
    ])
    def test_normalize_color(self, given, expected):
        assert weewx.jsongenerator._normalize_color(given) == expected

    def test_normalize_color_survives_nonsense(self):
        assert weewx.jsongenerator._normalize_color('0xnothex') == '0xnothex'
        assert weewx.jsongenerator._normalize_color(None) is None

    def test_split_vectors_leaves_scalars_alone(self):
        values, directions = weewx.jsongenerator._split_vectors([1.0, None, 3.0])
        assert values == [1.0, None, 3.0]
        assert directions is None

    def test_split_vectors_splits_complex(self):
        # 3+4j has magnitude 5. Direction follows WeeWX's compass convention.
        values, directions = weewx.jsongenerator._split_vectors([complex(3, 4), None])
        assert values[0] == pytest.approx(5.0)
        assert values[1] is None
        assert directions[0] is not None
        assert directions[1] is None
        assert 0 <= directions[0] <= 360

