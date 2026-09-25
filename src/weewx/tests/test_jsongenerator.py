#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test the JSON generator.

Use pytest to run the tests.
"""

import json
import os
import time

import configobj
import pytest

import parameters
import weewx
import weewx.defaults
import weewx.imagegenerator
import weewx.jsongenerator
import weewx.reportengine
import weewx.station
import weewx.units
import weewx.xtypes
from weeutil.config import accumulateLeaves

# The grid the archive tests are written on. Four hours rather than the hour a station
# would use: get_series() runs one aggregate query per slot, so the resolution decides
# what these tests cost, and nothing they check depends on which one it is.
ARCHIVE_RESOLUTION = 14400

# The generator works off plot definitions in the [ImageGenerator] syntax. This is a
# small but representative one: a two-line plot, a bar plot with aggregation, and a
# plot of a type the test database does not have (which must be skipped).
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
    """A skin dictionary complete enough for the generator to run against."""
    # The delta-time formats contain things like %(minute_label)s, which ConfigObj would
    # otherwise try to resolve as interpolation. The report engine turns interpolation
    # off for the same reason.
    weewx.defaults.defaults.interpolation = False

    mine = configobj.ConfigObj(PLOT_CONF.splitlines(), interpolation=False)

    json_conf = {'json_dest_dir': 'data', 'round': '3',
                 'Archive': {'resolution': str(ARCHIVE_RESOLUTION),
                             'stale_age': '3600'}}
    json_conf['Archive'].update(archive_options or {})

    # Assemble as a plain dict, then hand the whole thing to ConfigObj at once.
    # accumulateLeaves() walks the parent chain up to the root, and only a
    # dictionary built in one piece has that chain wired correctly -- merging
    # sections into an existing ConfigObj leaves them parented elsewhere.
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


def run_generator(config_dict, tmp_path, gen_ts=None, archive_options=None):
    """Run the generator against the test database and return its output directory."""
    html_root = str(tmp_path)
    skin_dict = build_skin_dict(html_root, archive_options=archive_options)

    # WEEWX_ROOT is left as the test configuration set it, so the database is still
    # found. HTML_ROOT is absolute, and os.path.join() ignores the prefix for those.
    config_dict = configobj.ConfigObj(config_dict.dict(), interpolation=False)

    stn_info = weewx.station.StationInfo(**config_dict['Station'])
    if gen_ts is None:
        gen_ts = parameters.synthetic_dict['stop_ts']

    generator = weewx.jsongenerator.JSONGenerator(
        config_dict, skin_dict, gen_ts, first_run=True, stn_info=stn_info)
    try:
        generator.start()
    finally:
        generator.finalize()

    return os.path.join(html_root, 'data')


class TestPlotDefinitions:

    @staticmethod
    def run(config_dict, skin_dict, stop_event=True):
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'], first_run=True,
            stn_info=weewx.station.StationInfo(**cd['Station']))
        if not stop_event:
            del generator.stop_event
        try:
            generator.start()
        finally:
            generator.finalize()
        return os.path.join(skin_dict['HTML_ROOT'], 'data')

    @staticmethod
    def archived(data_dir):
        """The plot groups with an archive file for 2010."""
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

        Counted as a time span, [[Archive]] would leave the generator nothing to
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
                'daymything': {'time_length': '6h', 'outTemp': {'label': 'Mine'}},
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
        with open(os.path.join(data_dir, 'index.json'), encoding='utf-8') as fd:
            assert json.load(fd)['spans'] == {'day_images': 6 * 3600}

    def test_the_image_generator_section_still_serves(self, config_dict, tmp_path):
        """A skin written before the JSON generator needs no new configuration."""
        data_dir = self.run(config_dict, build_skin_dict(str(tmp_path)))
        assert self.archived(data_dir) == ['rain', 'tempdew', 'windvec']

    def test_no_plot_definitions_anywhere_is_reported(self, config_dict, tmp_path):
        """A skin without plots writes nothing."""
        skin_dict = build_skin_dict(str(tmp_path))
        del skin_dict['ImageGenerator']
        self.run(config_dict, skin_dict)
        assert not os.path.isdir(os.path.join(str(tmp_path), 'data'))

    def test_a_skin_without_a_json_section_runs(self, config_dict, tmp_path):
        """[ImageGenerator] alone is enough.

        search_up() climbs the section tree through .parent. A plain dict in place
        of [JSONGenerator] has no .parent, and every search_up() on it raises.
        """
        skin_dict = build_skin_dict(str(tmp_path))
        del skin_dict['JSONGenerator']
        data_dir = self.run(config_dict, skin_dict)
        assert os.path.exists(os.path.join(data_dir, 'index.json'))
        assert self.archived(data_dir)

    def test_it_runs_where_there_is_no_stop_event(self, config_dict, tmp_path):
        """ReportGenerator gained stop_event in v5.5.0.

        Under an earlier WeeWX, stop_event is never set. The JSON generator runs
        there as an extension.
        """
        data_dir = self.run(config_dict, build_skin_dict(str(tmp_path)),
                            stop_event=False)
        assert self.archived(data_dir)


class TestIndex:

    @staticmethod
    def index(data_dir):
        with open(os.path.join(data_dir, 'index.json'), encoding='utf-8') as fd:
            return json.load(fd)

    def test_the_index_says_whether_images_are_drawn(self, config_dict, tmp_path):
        """The skin says it once, in [Generators]."""
        skin_dict = build_skin_dict(str(tmp_path))
        skin_dict['Generators'] = {
            'generator_list': 'weewx.jsongenerator.JSONGenerator',
        }

        def images():
            return self.index(TestPlotDefinitions.run(config_dict, skin_dict))['images']

        assert images() is False

        # A generator with 'image' in its name is not the ImageGenerator.
        skin_dict['Generators']['generator_list'] = \
            'weewx.jsongenerator.JSONGenerator, user.gallery.ImageGalleryGenerator'
        assert images() is False

        skin_dict['Generators']['generator_list'] = \
            'weewx.jsongenerator.JSONGenerator, weewx.imagegenerator.ImageGenerator'
        assert images() is True

    def test_the_index_gives_the_length_of_each_span(self, config_dict, tmp_path):
        index = self.index(run_generator(config_dict, tmp_path))
        assert index['spans'] == {'day_images': 27 * 3600, 'week_images': 7 * 86400}

    def test_the_index_says_which_units_the_report_used(self, config_dict, tmp_path):
        """The forecast arrives in Celsius. The page converts it into the report's unit.

        Without units['report'], the page converts the forecast only after the reader
        picks a unit system by hand.
        """
        data_dir = run_generator(config_dict, tmp_path)
        units = self.index(data_dir)['units']

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
        """One archive run, shared by the tests that only read what it wrote.

        Writing it costs an aggregate query per grid slot, which is most of what this
        file costs to run. The tests below look at the same output instead of each
        building their own; the ones that need a second run still make it.
        """
        data_dir = run_generator(config_dict, tmp_path_factory.mktemp('archive'))
        return os.path.join(data_dir, 'archive')

    def test_writes_one_file_per_group_and_year(self, archive_dir):
        written = sorted(f for f in os.listdir(archive_dir) if f.endswith('.json'))

        # The test data sit in 2010, and the group name has the 'day' prefix stripped.
        assert 'tempdew-2010.json' in written
        assert 'index.json' in written

    def test_grid_is_regular_and_timestamps_implied(self, archive_dir):
        with open(os.path.join(archive_dir, 'tempdew-2010.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == ARCHIVE_RESOLUTION
        assert payload['start'] % ARCHIVE_RESOLUTION == 0
        # No 'time' array at all: that is the point of the fixed grid.
        for series in payload['series']:
            assert 'time' not in series
            assert len(series['values']) == payload['count']

    def test_values_land_in_the_right_slots(self, archive_dir):
        with open(os.path.join(archive_dir, 'tempdew-2010.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        series = payload['series'][0]
        filled = [i for i, v in enumerate(series['values']) if v is not None]
        assert filled, "archive holds no data at all"
        # The synthetic database is gapless, so the run of filled slots must be dense.
        assert len(filled) > 0.9 * (filled[-1] - filled[0] + 1)

    def test_fresh_files_are_not_rewritten(self, config_dict, tmp_path):
        """A second run right after the first must not touch anything.

        This is the case that matters in practice: reports run every archive interval,
        and the archive must cost almost nothing on all the runs after the first.
        """
        data_dir = run_generator(config_dict, tmp_path)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path)

        assert os.path.getmtime(path) == before

    def test_a_new_grid_slot_rewrites_the_file(self, config_dict, tmp_path):
        """The current year is rewritten once the data reach into the next slot."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path,
                                 gen_ts=stop_ts - ARCHIVE_RESOLUTION)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path, gen_ts=stop_ts)

        assert os.path.getmtime(path) != before

    def test_catchup_data_reach_the_archive(self, config_dict, tmp_path):
        """A file minutes old can still be hours behind.

        Stop the station, restart it, and the logger hands over everything it recorded
        meanwhile. The file on disk is younger than any age test would trip on, and
        missing a day of data. Reported by tkeffer in #1111.
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

        assert after['covered'] > before['covered']
        filled = lambda p: sum(1 for v in p['series'][0]['values'] if v is not None)
        # Two days of catch-up, so nearly two days of grid slots have to fill in.
        slots = 2 * 86400 // ARCHIVE_RESOLUTION
        assert filled(after) - filled(before) > 0.8 * slots

    def test_an_import_rebuilds_finished_years(self, config_dict, tmp_path):
        """Data reaching further back than last time mean an import.

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

        assert index['interval'] == ARCHIVE_RESOLUTION
        groups = {g['name']: g for g in index['groups']}
        assert 'tempdew' in groups
        assert 2010 in groups['tempdew']['years']

    def test_a_finer_grid_is_written_for_the_recent_past(self, config_dict, tmp_path):
        """An hourly grid flattens a single day, so recent months also get a fine one."""
        data_dir = run_generator(config_dict, tmp_path,
                                 archive_options={'fine_months': '2',
                                                  'fine_resolution': '300'})
        archive_dir = os.path.join(data_dir, 'archive')
        fine = sorted(f for f in os.listdir(archive_dir) if '-fine-' in f)
        assert fine, "no fine files written"

        with open(os.path.join(archive_dir, fine[0]), encoding='utf-8') as fd:
            payload = json.load(fd)
        assert payload['interval'] == 300

        # The coarse file for the same group is still there, on the wide grid.
        group = fine[0].split('-fine-')[0]
        with open(os.path.join(archive_dir, '%s-2010.json' % group), encoding='utf-8') as fd:
            assert json.load(fd)['interval'] == ARCHIVE_RESOLUTION

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        assert index['fine_interval'] == 300
        groups = {g['name']: g for g in index['groups']}
        # The month the fine file covers is named, so a client knows to ask for it.
        assert fine[0].split('-fine-')[1][:-5] in groups[group]['fine']

    def test_a_grid_that_is_not_finer_is_refused(self, config_dict, tmp_path):
        """'5m' means five months. Silently writing that would be worse than saying so."""
        data_dir = run_generator(config_dict, tmp_path,
                                 archive_options={'fine_months': '2',
                                                  'fine_resolution': '28800'})
        archive_dir = os.path.join(data_dir, 'archive')
        assert not [f for f in os.listdir(archive_dir) if '-fine-' in f]


class TestArchiveExtension:
    """Carrying a file forward instead of working the whole span out again.

    A file already holds every slot but its last, so a report only has to calculate
    from there on. That is one aggregate query rather than one per slot in the year,
    and it is the difference between the archive costing seconds every report and
    costing nothing. What the tests here are for is the other half of that trade: the
    result has to be what the long way round would have produced.
    """

    # What a run leaves behind that says when it ran rather than what it found.
    # 'covered' and the resume pair belong to the last run that wrote the file, and a
    # run whose slot has not moved does not write one. So a chain of reports ending on
    # a skipped one carries the stamps of the report before it, while a single run at
    # the same instant carries its own. Neither is in the data the page draws.
    BOOKKEEPING = ('covered', 'resume_ts', 'resume_slot')

    @classmethod
    def payloads(cls, archive_dir, only=None):
        """The drawable contents of every archive file, keyed by name."""
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
        """Report once per step from first_ts to last_ts, extending each time."""
        options = {'rebuild': '0'}
        options.update(archive_options or {})
        gen_ts = first_ts
        data_dir = None
        while True:
            data_dir = run_generator(config_dict, root, gen_ts=gen_ts,
                                     archive_options=options)
            if gen_ts >= last_ts:
                break
            # The last report lands on 'last_ts' itself, whatever the step. A day the
            # clocks change is 23 or 25 hours long, so a fixed step does not divide the
            # span, and the walk would otherwise stop short of the rebuild it is
            # compared against and be handed less of the database.
            gen_ts = min(gen_ts + step, last_ts)
        return os.path.join(data_dir, 'archive')

    def test_extending_matches_a_full_rebuild(self, config_dict, tmp_path_factory):
        """Six reports, each carrying the last forward, against one that does the lot."""
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
        """intervalgen() keeps local time constant, so a slot can be three hours long.

        The grid a file is written on is worked out from its own start, and an extending
        run starts from further along than the run that first wrote it. Where the clocks
        change, the two could disagree about where a slot begins.
        """
        # 2010-03-14 02:00 PST is 03:00 PDT. Straddle it.
        first_ts = int(time.mktime((2010, 3, 13, 12, 0, 0, 0, 0, -1)))
        last_ts = int(time.mktime((2010, 3, 15, 0, 0, 0, 0, 0, -1)))
        # Both sides have to end on the same slot boundary. A file is rewritten once
        # its newest reading reaches the next slot, not once per report, so a walk
        # that stops in the middle of a slot leaves the file as the report before it
        # wrote it while the rebuild writes it fresh.
        last_ts -= last_ts % ARCHIVE_RESOLUTION

        grown = self.walk_forward(config_dict, tmp_path_factory.mktemp('dst_grown'),
                                  first_ts, last_ts, ARCHIVE_RESOLUTION)
        built = os.path.join(
            run_generator(config_dict, tmp_path_factory.mktemp('dst_built'),
                          gen_ts=last_ts), 'archive')

        assert self.payloads(grown) == self.payloads(built)

    def test_extending_matches_a_full_rebuild_on_the_fine_grid(
            self, config_dict, tmp_path_factory):
        """The fine files are the expensive ones, and they are per month, not per year.

        Only the month in progress is compared. Whole months either side of it are
        written once and then kept, so the run that wrote one decides where it starts,
        and a later run that skips it leaves that alone.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'fine_months': '2', 'fine_resolution': '3600'}
        first_ts = stop_ts - 4 * 3600
        current_month = '-fine-%s' % time.strftime('%Y-%m', time.localtime(stop_ts))

        grown = self.walk_forward(config_dict, tmp_path_factory.mktemp('fine_grown'),
                                  first_ts, stop_ts, 3600, options)
        built = os.path.join(
            run_generator(config_dict, tmp_path_factory.mktemp('fine_built'),
                          gen_ts=stop_ts, archive_options=options),
            'archive')

        grown_files = self.payloads(grown, only=current_month)
        assert grown_files, "no fine file for the month in progress"
        assert grown_files == self.payloads(built, only=current_month)

    def test_extending_costs_one_query_per_new_slot(self, config_dict, tmp_path,
                                                    monkeypatch):
        """The whole point. A year's file must not cost a query per slot in the year."""
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
        # A call over more than a day is the archive working out the year again.
        # Carrying the file forward makes that unnecessary.
        assert max(span.stop - span.start for span in calls) <= 86400

    def test_a_rebuild_happens_once_a_calendar_day(self, config_dict, tmp_path):
        """Anything that changed further back than the last report needs this."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        index_path = lambda d: os.path.join(d, 'archive', 'index.json')
        rebuilt_at = lambda d: json.load(open(index_path(d), encoding='utf-8'))['rebuilt']

        data_dir = run_generator(config_dict, tmp_path,
                                 gen_ts=stop_ts - 86400)
        first = rebuilt_at(data_dir)
        assert first is not None

        # Later the same day: carried forward, so the stamp does not move.
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
        """A file whose series are not the ones being written cannot be carried on.

        This is what a changed skin looks like from here: same name, same grid, other
        contents. Taking its values would put one observation's readings under another
        one's label.
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


class TestResumeFrom:
    """Whether a file on disk can be carried forward, and from where."""

    @staticmethod
    def file(**overrides):
        payload = {'start': 1000, 'interval': 100, 'count': 10,
                   'resume_ts': 1900, 'resume_slot': 9,
                   'series': [{'obs_type': 'outTemp', 'values': [1.0] * 10}]}
        payload.update(overrides)
        return payload

    def test_resumes_where_the_file_says_it_stopped(self):
        # The instant comes out of the file, not from slot arithmetic: see the
        # docstring on _resume_from().
        assert weewx.jsongenerator._resume_from(self.file(), 1000, 100, 20) == (1900, 9)

    def test_no_file_means_no_resuming(self):
        assert weewx.jsongenerator._resume_from(None, 1000, 100, 20) is None

    @pytest.mark.parametrize('overrides, reason', [
        ({'start': 2000}, 'max_days moved the start'),
        ({'interval': 50}, 'resolution changed'),
        ({'count': 1}, 'too short to carry anything'),
        ({'series': []}, 'no series in it'),
        ({'count': 'nonsense'}, 'not a number'),
        ({'resume_ts': None}, 'written before the field existed'),
        ({'resume_slot': None}, 'written before the field existed'),
        ({'resume_slot': 10}, 'points past the slots the file has'),
        ({'resume_ts': 500}, 'before the file even starts'),
    ])
    def test_a_file_that_cannot_be_used(self, overrides, reason):
        assert weewx.jsongenerator._resume_from(self.file(**overrides),
                                                1000, 100, 20) is None, reason

    def test_a_file_reaching_past_the_span_is_refused(self):
        """A clock that went backwards leaves more slots on disk than are wanted."""
        assert weewx.jsongenerator._resume_from(self.file(count=30), 1000, 100, 20) is None

    def test_carried_series_matches_by_position_and_type(self):
        previous = self.file()
        assert weewx.jsongenerator._carried_series(previous, 0, 'outTemp', 10) is not None
        assert weewx.jsongenerator._carried_series(previous, 0, 'dewpoint', 10) is None
        assert weewx.jsongenerator._carried_series(previous, 1, 'outTemp', 10) is None

    def test_carried_series_checks_its_length(self):
        """A file whose values do not fill its own grid cannot be trusted."""
        previous = self.file(series=[{'obs_type': 'outTemp', 'values': [1.0] * 3}])
        assert weewx.jsongenerator._carried_series(previous, 0, 'outTemp', 10) is None


class TestTiers:
    """Which grid a calendar year's file is written on."""

    @staticmethod
    def grid(year, this_year=2026, recent=2, fine=3600, coarse=14400, existing=None):
        return weewx.jsongenerator._year_grid(year, this_year, recent, fine, coarse,
                                              existing)

    def test_the_recent_years_get_the_finer_grid(self):
        assert self.grid(2026) == 3600
        assert self.grid(2025) == 3600

    def test_older_years_get_the_coarse_one(self):
        assert self.grid(2024) == 14400
        assert self.grid(2016) == 14400

    def test_without_a_recent_window_every_year_is_the_same(self):
        assert self.grid(2016, recent=0) == 3600

    def test_a_file_already_finer_keeps_what_it_has(self):
        """Rewriting a year to hold less than it does would be work spent backwards."""
        assert self.grid(2016, existing=3600) == 3600

    def test_a_file_coarser_than_wanted_is_refined(self):
        assert self.grid(2026, existing=14400) == 3600


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

    def test_it_does_not_go_before_the_record(self):
        floor = int(time.mktime((2026, 6, 15, 0, 0, 0, 0, 0, -1)))
        start = weewx.jsongenerator._months_back(
            int(time.mktime((2026, 8, 28, 12, 0, 0, 0, 0, -1))), 6, floor)
        assert start == floor


class TestArchiveMemory:
    """What the archive knows about files it did not write this run."""

    def test_finished_months_stay_available(self, config_dict, tmp_path):
        """A month that has ended never changes, so its file is good forever.

        Only the months inside the writing window are written. Everything older that
        is still on disk has to stay named in the index, or the page cannot see it and
        the detail is there for nobody.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'fine_months': '2', 'fine_resolution': '3600'}
        # Two runs a month apart, so the first month falls out of the window.
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)

        archive_dir = os.path.join(data_dir, 'archive')
        on_disk = {f for f in os.listdir(archive_dir) if '-fine-' in f}
        assert on_disk, "no fine files at all"

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        named = set()
        for group in index['groups']:
            for stamp in group.get('fine', {}):
                named.add('%s-fine-%s.json' % (group['name'], stamp))
        assert on_disk <= named, "files on disk that the index does not name"

    def test_a_lost_index_is_rebuilt_from_the_directory(self, config_dict, tmp_path):
        """The directory is the truth. Losing the index must not lose the work.

        Every answer is already in the files. Without this, deleting one small file
        would mean working out the whole record again.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'fine_months': '2', 'fine_resolution': '3600'}
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
                             for y in list(g.get('covered', {}))
                             + list(g.get('fine', {}))}
        assert named(after) == named(before)

    def test_the_index_drops_files_that_have_gone(self, config_dict, tmp_path):
        """An index naming a file that is not there sends the reader after a 404.

        A file inside the writing window is simply written again, so the case that
        needs catching is one outside it: a month the run no longer visits, deleted by
        whoever was tidying up the directory.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'fine_months': '2', 'fine_resolution': '3600'}
        run_generator(config_dict, tmp_path, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        months = sorted({m for g in index['groups'] for m in g.get('fine', {})})
        assert len(months) > 1, "only one month written, nothing is out of the window"
        oldest = months[0]
        gone = [f for f in os.listdir(archive_dir) if f.endswith('-fine-%s.json' % oldest)]
        assert gone
        for name in gone:
            os.remove(os.path.join(archive_dir, name))

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options=options)

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        for group in index['groups']:
            assert oldest not in group.get('fine', {}), \
                "index still names %s for %s" % (oldest, group['name'])

    def test_the_index_records_the_grid_of_each_file(self, config_dict, tmp_path):
        """Files are not all on the same grid, so the reader is told per file."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert groups['tempdew']['intervals']['2010'] == ARCHIVE_RESOLUTION


class TestRawTier:
    """The station's own readings, one file per day, kept for a while and then not."""

    OPTIONS = {'raw_days': '5', 'raw_resolution': '1800'}

    @staticmethod
    def days(archive_dir):
        return sorted({f.split('-raw-')[1][:-len('.json')]
                       for f in os.listdir(archive_dir) if '-raw-' in f})

    def test_one_file_per_day(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        archive_dir = os.path.join(data_dir, 'archive')

        days = self.days(archive_dir)
        assert len(days) == 5, days
        assert days[-1] == time.strftime('%Y-%m-%d', time.localtime(stop_ts))

    def test_the_grid_is_the_archive_interval(self, config_dict, tmp_path):
        """0 means 'as fine as the record', read off a record rather than a setting."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'raw_days': '2', 'raw_resolution': '0'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = [f for f in os.listdir(archive_dir) if '-raw-' in f][0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == parameters.synthetic_dict['interval']

    def test_days_that_fall_out_of_the_window_are_removed(self, config_dict, tmp_path):
        """The one tier with a horizon. Left alone it would grow a file a day forever."""
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
        for stamp in before:
            if stamp < after[0]:
                assert not [f for f in os.listdir(archive_dir)
                            if f.endswith('-raw-%s.json' % stamp)]

    def test_the_index_names_the_raw_days(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert len(groups['tempdew']['raw']) == 5
        assert set(groups['tempdew']['raw_intervals'].values()) == {1800}

    def test_it_is_off_unless_asked_for(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        archive_dir = os.path.join(data_dir, 'archive')
        assert not [f for f in os.listdir(archive_dir) if '-raw-' in f]


class TestBudget:
    """Building a long history across several reports instead of one long one."""

    _whole = {}

    @classmethod
    def whole_count(cls, config_dict, tmp_path_factory=None):
        """How many slots the file has when nothing gets in the way."""
        if 'count' not in cls._whole:
            import tempfile
            target = tempfile.mkdtemp(prefix='whole-')
            data_dir = run_generator(config_dict, target,
                                     gen_ts=parameters.synthetic_dict['stop_ts'])
            with open(os.path.join(data_dir, 'archive', 'tempdew-2010.json'),
                      encoding='utf-8') as fd:
                cls._whole['count'] = json.load(fd)['count']
        return cls._whole['count']

    def test_a_file_too_big_for_the_budget_is_finished_later(self, config_dict,
                                                             tmp_path):
        """The budget cuts inside a file, not between files.

        A year on a slow machine can cost more than a whole budget on its own. Waiting
        for it would be a report that runs long; skipping it would be a year that never
        gets built. So the file is written holding what was worked out, and the next
        run carries on from there, which is what extending already does.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        name = os.path.join('data', 'archive', 'tempdew-2010.json')
        path = os.path.join(str(tmp_path), name)

        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options={'budget': '1'})
        with open(path, encoding='utf-8') as fd:
            first = json.load(fd)
        assert first['count'] < self.whole_count(config_dict), \
            "the budget did not cut the file short"

        seen = [first['count']]
        for _ in range(3):
            run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                          archive_options={'budget': '1'})
            with open(path, encoding='utf-8') as fd:
                seen.append(json.load(fd)['count'])

        assert seen == sorted(seen), "the file did not grow monotonically: %s" % seen
        assert seen[-1] > seen[0], "later runs added nothing"

    def test_the_short_file_says_how_far_it_got(self, config_dict, tmp_path):
        """'covered' has to be the truth, or the next run thinks it is done."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options={'budget': '1'})
        path = os.path.join(str(tmp_path), 'data', 'archive', 'tempdew-2010.json')
        with open(path, encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['covered'] < stop_ts
        assert payload['covered'] <= payload['start'] + payload['count'] * payload['interval']
        assert payload['resume_ts'] is not None

    def test_it_ends_up_the_same_as_doing_it_in_one_go(self, config_dict,
                                                       tmp_path_factory):
        """Built in pieces or all at once, the file has to say the same thing."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        pieces = tmp_path_factory.mktemp('pieces')
        for _ in range(40):
            run_generator(config_dict, pieces, gen_ts=stop_ts,
                          archive_options={'budget': '1'})
        whole = tmp_path_factory.mktemp('whole')
        run_generator(config_dict, whole, gen_ts=stop_ts)

        name = os.path.join('data', 'archive', 'tempdew-2010.json')
        with open(os.path.join(str(pieces), name), encoding='utf-8') as fd:
            built_up = json.load(fd)
        with open(os.path.join(str(whole), name), encoding='utf-8') as fd:
            one_go = json.load(fd)

        assert built_up['count'] == one_go['count'], "the pieces did not reach the end"
        assert built_up['series'] == one_go['series']

    def test_deferred_files_stay_in_the_index(self, config_dict, tmp_path):
        """A run that stops early must not un-name what earlier runs wrote.

        The index is built from what this run touched. Everything else is on disk and
        correct, and dropping it would take the page's history away until the run that
        happens to reach it again.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        full = run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        index_path = os.path.join(full, 'archive', 'index.json')
        with open(index_path, encoding='utf-8') as fd:
            before = json.load(fd)

        # Nothing is due now, and the budget is spent at once. The index must come out
        # the same anyway, because every file is still there.
        run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                      archive_options={'budget': '1'})
        with open(index_path, encoding='utf-8') as fd:
            after = json.load(fd)

        named = lambda idx: {(g['name'], y) for g in idx['groups']
                             for y in g.get('covered', {})}
        assert named(after) == named(before)
        assert {g['name'] for g in after['groups']} == {g['name'] for g in before['groups']}

    def test_the_day_view_is_never_deferred(self, config_dict, tmp_path):
        """The raw tier is what the page draws today from. It is not metered."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(
            config_dict, tmp_path, gen_ts=stop_ts,
            archive_options={'budget': '1', 'raw_days': '3', 'raw_resolution': '1800'})
        archive_dir = os.path.join(data_dir, 'archive')

        days = {f.split('-raw-')[1][:-len('.json')]
                for f in os.listdir(archive_dir) if '-raw-' in f}
        assert len(days) == 3, days


class TestArchiveSeriesShapes:
    """What a series in an archive file can carry beyond one number per slot."""

    def test_a_wind_vector_keeps_its_components(self, config_dict, tmp_path):
        """A vector is a pair. The evenly spaced grid holds it as two arrays.

        Without this the wind vector plot is the one chart the archive cannot draw,
        and the page would need a second source just for it.
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
        """"Rain, hourly total" has to stay an hour, on any grid.

        The plot says 'aggregate_interval = 3600'. Summing per slot on a finer grid
        gives a number a fraction of the size, under a label that says otherwise, and
        a row of hairline bars instead of one a reader can compare.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'raw_days': '2', 'raw_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = [f for f in os.listdir(archive_dir) if f.startswith('rain-raw-')][0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == 900
        values = payload['series'][0]['values']
        filled = [i for i, v in enumerate(values) if v is not None]
        assert filled, "no rain at all"
        # An hourly total on a quarter-hour grid lands on every fourth slot.
        gaps = {b - a for a, b in zip(filled, filled[1:])}
        assert gaps and min(gaps) >= 4, \
            "readings are closer together than the hour they are totalled over: %s" % sorted(gaps)[:5]

    def test_finished_days_meet_without_a_seam(self, config_dict, tmp_path):
        """The end of one raw day file is the start of the next, exactly.

        A day that runs a slot past midnight owns an instant the next file owns too,
        and it can never fill it: the run that could is the one that finds the day
        finished and skips the file. The page then draws every reading it has with a
        hole between each pair of days.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'raw_days': '5', 'raw_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        files = sorted(f for f in os.listdir(archive_dir)
                       if f.startswith('tempdew-raw-'))
        assert len(files) > 2, files

        spans = []
        for name in files:
            with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
                payload = json.load(fd)
            spans.append((name, payload['start'], payload['count'],
                          payload['interval']))

        # The last file is the day still filling up, so it stops where the readings do.
        for (name, start, count, interval), (_, later, _, _) in zip(spans, spans[1:]):
            assert start + count * interval == later,                 "%s ends at %d, but the next file starts at %d"                 % (name, start + count * interval, later)

    def test_a_finished_day_holds_nothing_from_the_next(self, config_dict, tmp_path):
        """A bar totalled over an hour must not be filed a slot early.

        get_series() clips its last interval to the end of the span, so the last bar
        of a day covers less than the hour it is meant to. Counted back from its end
        it lands before the slot it belongs in, which puts part of tomorrow's rain at
        the end of today, overlapping the bar that is already there.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'raw_days': '5', 'raw_resolution': '900'}
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')

        names = sorted(f for f in os.listdir(archive_dir) if f.startswith('rain-raw-'))
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
            assert min(gaps) >= every,                 "%s files an hourly bar %d slots after the last, not %d: %s"                 % (name, min(gaps), every, filled[-6:])
            assert max(filled) < payload['count'],                 "%s fills slot %d of %d" % (name, max(filled), payload['count'])

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

    def test_extremes_are_off_by_default(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, gen_ts=stop_ts)
        with open(os.path.join(data_dir, 'archive', 'tempdew-2010.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)
        assert 'min' not in payload['series'][0]

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

    def test_no_stamp_means_rebuild(self):
        assert weewx.jsongenerator._rebuild_due(None, 1000, self.DAY)

    def test_turned_off(self):
        assert not weewx.jsongenerator._rebuild_due(None, 1000, 0)

    def test_same_calendar_day(self):
        morning = int(time.mktime((2010, 3, 1, 8, 0, 0, 0, 0, -1)))
        evening = int(time.mktime((2010, 3, 1, 23, 59, 0, 0, 0, -1)))
        assert not weewx.jsongenerator._rebuild_due(morning, evening, self.DAY)

    def test_over_midnight(self):
        """Two minutes apart, and due, where 24 hours of elapsed time would not be."""
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


class TestSkinLocalization:
    """Every string the Horizon skin asks for must exist in en.conf.

    English is the fallback: if a string is missing there, the reader sees the raw key.
    Other languages may lag behind -- an untranslated string falls back to English,
    which is fine -- so they are reported but do not fail.
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

