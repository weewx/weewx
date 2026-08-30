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


def build_skin_dict(html_root, archive=False, archive_options=None):
    """A skin dictionary complete enough for the generator to run against."""
    # The delta-time formats contain things like %(minute_label)s, which ConfigObj would
    # otherwise try to resolve as interpolation. The report engine turns interpolation
    # off for the same reason.
    weewx.defaults.defaults.interpolation = False

    mine = configobj.ConfigObj(PLOT_CONF.splitlines(), interpolation=False)

    json_conf = {'json_dest_dir': 'data', 'round': '3'}
    if archive:
        json_conf['Archive'] = {'enable': 'true',
                                'resolution': str(ARCHIVE_RESOLUTION),
                                'stale_age': '3600'}
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


def run_generator(config_dict, tmp_path, archive=False, gen_ts=None,
                  archive_options=None):
    """Run the generator against the test database and return its output directory."""
    html_root = str(tmp_path)
    skin_dict = build_skin_dict(html_root, archive=archive,
                                archive_options=archive_options)

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


class TestPeriodFiles:

    def test_writes_a_file_per_plot(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        written = {f for f in os.listdir(data_dir) if f.endswith('.json')}
        assert 'daytempdew.json' in written
        assert 'dayrain.json' in written
        assert 'weektempdew.json' in written

    def test_skips_plots_without_data(self, config_dict, tmp_path):
        # soilMoist4 is not in the test database, and skip_if_empty is set.
        data_dir = run_generator(config_dict, tmp_path)
        assert not os.path.exists(os.path.join(data_dir, 'daynothing.json'))

    def test_series_arrays_are_parallel(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['name'] == 'daytempdew'
        assert len(payload['series']) == 2
        for series in payload['series']:
            assert len(series['time']) == len(series['values'])
            assert len(series['time']) > 0
            # Timestamps are integers; gaps are null, never NaN.
            assert all(isinstance(t, int) for t in series['time'])
            assert all(v is None or isinstance(v, (int, float)) for v in series['values'])

    def test_observation_types_and_labels(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert [s['obs_type'] for s in payload['series']] == ['outTemp', 'dewpoint']
        # Labels come from [Labels][Generic], not from the raw observation name.
        assert payload['series'][0]['label'] == 'Outside Temperature'

    def test_colors_come_from_the_skin_palette(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['series'][0]['color'] == '#4282b4'
        assert payload['series'][1]['color'] == '#b44242'

    def test_units_are_converted(self, config_dict, tmp_path):
        # The test database is US; the skin asks for metricwx.
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['unit'] == 'degree_C'
        values = [v for v in payload['series'][0]['values'] if v is not None]
        # Synthetic data runs roughly -20..40 C. Anything in Fahrenheit would blow past.
        assert all(-60 < v < 60 for v in values)

    def test_rounding_is_applied(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        for series in payload['series']:
            for v in series['values']:
                if v is not None:
                    assert round(v, 3) == v

    def test_bar_plots_carry_their_width(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'dayrain.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        series = payload['series'][0]
        assert series['plot_type'] == 'bar'
        assert series['aggregate_type'] == 'sum'
        assert series['aggregate_interval'] == 3600
        assert len(series['bar_width']) == len(series['values'])

    def test_daynight_transitions_are_emitted(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert 'daynight' in payload
        assert payload['daynight']['first'] in ('day', 'night')
        # 27 hours must contain at least one sunrise or sunset outside the polar circles.
        assert len(payload['daynight']['transitions']) >= 1
        for ts in payload['daynight']['transitions']:
            assert payload['start'] <= ts <= payload['stop']

    def test_twilight_bands_are_emitted(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        bands = payload['daynight']['twilight']
        assert bands, "no civil twilight emitted"
        for band in bands:
            assert band['dir'] in ('dawn', 'dusk')
            assert band['from'] < band['to']
            # Civil twilight at 45 degrees latitude runs roughly 25-40 minutes. Allow
            # a generous window, but catch anything absurd.
            minutes = (band['to'] - band['from']) / 60.0
            assert 15 < minutes < 90, "implausible twilight of %.0f minutes" % minutes

        # Dawn ends at sunrise and dusk starts at sunset, so each band boundary that
        # falls inside the window must be one of the horizon crossings.
        crossings = set(payload['daynight']['transitions'])
        for band in bands:
            edge = band['to'] if band['dir'] == 'dawn' else band['from']
            if payload['start'] < edge < payload['stop']:
                assert edge in crossings

    def test_vector_plot_carries_components_and_rotation(self, config_dict, tmp_path):
        """A vector plot needs the components, and the rotation the PNGs use.

        The ImageGenerator negates vector_rotate before handing it to weeplot. Passing
        it through unnegated draws every arrow mirrored against the PNG of the same
        data -- which looks plausible until you put the two side by side.
        """
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daywindvec.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        series = payload['series'][0]
        assert series['plot_type'] == 'vector'

        # Components, one per sample, alongside the magnitude.
        assert len(series['vector_x']) == len(series['values'])
        assert len(series['vector_y']) == len(series['values'])

        # Magnitude has to agree with the components it was derived from.
        for vx, vy, mag in zip(series['vector_x'], series['vector_y'], series['values']):
            if vx is None or mag is None:
                continue
            assert mag == pytest.approx((vx ** 2 + vy ** 2) ** 0.5, abs=0.01)

        # The skin configures 90; what reaches the client must be -90.
        assert series['vector_rotate'] == -90.0

    def test_time_axis_matches_the_image_generator(self, config_dict, tmp_path):
        """The two generators must agree on the window, or a chart and the PNG of the
        same plot show different days."""
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])
        gen_ts = parameters.synthetic_dict['stop_ts']

        img_gen = weewx.imagegenerator.ImageGenerator(
            cd, skin_dict, gen_ts, first_run=True, stn_info=stn_info)
        img_gen.start()
        try:
            plot = img_gen.gen_plot(gen_ts,
                                    accumulateLeaves(
                                        skin_dict['ImageGenerator']['day_images']['daytempdew']),
                                    skin_dict['ImageGenerator']['day_images']['daytempdew'])
        finally:
            img_gen.finalize()
        xmin, xmax, xinc = plot.xscale

        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['start'] == int(xmin)
        assert payload['stop'] == int(xmax)
        assert payload['x_interval'] == int(xinc)

        # The window is snapped, so it is not simply now minus time_length. Without that
        # snapping this test would pass for the wrong reason.
        assert payload['stop'] != int(gen_ts)

    def test_explicit_x_interval_wins(self, config_dict, tmp_path):
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        skin_dict['ImageGenerator']['day_images']['daytempdew']['x_interval'] = '2h'
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        with open(os.path.join(html_root, 'data', 'daytempdew.json'),
                  encoding='utf-8') as fd:
            payload = json.load(fd)
        assert payload['x_interval'] == 7200

    @pytest.mark.parametrize('plot', ['daytempdew', 'dayrain', 'daywindvec'])
    def test_y_axis_matches_the_image_generator(self, config_dict, tmp_path, plot):
        """A line, a bar plot and a vector plot must all land on the PNG's axis."""
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])
        gen_ts = parameters.synthetic_dict['stop_ts']

        img_gen = weewx.imagegenerator.ImageGenerator(
            cd, skin_dict, gen_ts, first_run=True, stn_info=stn_info)
        img_gen.start()
        try:
            section = skin_dict['ImageGenerator']['day_images'][plot]
            image_plot = img_gen.gen_plot(gen_ts, accumulateLeaves(section), section)
            image_plot.render()          # this is what works the y scaling out
        finally:
            img_gen.finalize()

        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, '%s.json' % plot), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['yscale'] == pytest.approx(list(image_plot.yscale))

    def test_configured_yscale_is_honoured(self, config_dict, tmp_path):
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        skin_dict['ImageGenerator']['day_images']['daytempdew']['yscale'] = \
            ['0.0', '360.0', '45.0']
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        with open(os.path.join(html_root, 'data', 'daytempdew.json'),
                  encoding='utf-8') as fd:
            assert json.load(fd)['yscale'] == [0.0, 360.0, 45.0]

    def test_its_own_section_comes_first(self, config_dict, tmp_path):
        """Plots defined under [JSONGenerator] win over [ImageGenerator].

        A skin that draws only in the browser should not have to keep a section
        named after images it never generates.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        skin_dict['JSONGenerator']['day_images'] = {
            'ownplot': {'time_length': '6h', 'outTemp': {'label': 'Own'}},
        }
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        data_dir = os.path.join(html_root, 'data')
        assert sorted(f for f in os.listdir(data_dir) if f.endswith('.json')) \
                == ['index.json', 'ownplot.json']

    def test_settings_are_not_mistaken_for_plots(self, config_dict, tmp_path):
        """[[Archive]] is a subsection too, and defines no plots.

        Counting subsections alone would take it for a time span and leave the
        generator with nothing to draw, silently.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root, archive=True)
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        # Falls back to [ImageGenerator] and writes its plots, not nothing.
        data_dir = os.path.join(html_root, 'data')
        assert 'daytempdew.json' in os.listdir(data_dir)

    def test_plots_can_live_in_this_generators_own_section(self, config_dict, tmp_path):
        """A skin running no ImageGenerator keeps its plots here.

        Sharing [ImageGenerator] means a plot is defined once and both the image
        and the chart have it. A skin that draws only charts has no image
        generator, and should not need a section named after one.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        skin_dict['JSONGenerator'].update({
            'chart_line_colors': '#118844',
            'day_images': {
                'mything': {'time_length': '6h', 'outTemp': {'label': 'Mine'}},
            },
        })
        del skin_dict['ImageGenerator']
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        data_dir = os.path.join(html_root, 'data')
        written = sorted(f for f in os.listdir(data_dir) if f.endswith('.json'))
        assert written == ['index.json', 'mything.json']

        with open(os.path.join(data_dir, 'mything.json'), encoding='utf-8') as fd:
            payload = json.load(fd)
        assert payload['series'][0]['label'] == 'Mine'
        assert payload['series'][0]['color'] == '#118844'
        assert payload['stop'] - payload['start'] == 6 * 3600

    def test_the_image_generator_section_still_serves(self, config_dict, tmp_path):
        """A skin written before this generator existed needs no new configuration."""
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        assert 'daytempdew.json' in os.listdir(os.path.join(html_root, 'data'))

    def test_no_plot_definitions_anywhere_is_reported(self, config_dict, tmp_path):
        """A skin with no plots at all writes nothing, and says why."""
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        del skin_dict['ImageGenerator']
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        assert not os.path.isdir(os.path.join(html_root, 'data'))

    def test_a_skin_without_a_json_section_runs(self, config_dict, tmp_path):
        """[ImageGenerator] on its own is enough, which is what the module promises.

        search_up() climbs the section tree through .parent. An empty dict standing
        in for a missing section has none, so every option read that way raises.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        del skin_dict['JSONGenerator']
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()

        written = {f for f in os.listdir(os.path.join(html_root, 'data'))
                   if f.endswith('.json')}
        assert written

    def test_it_runs_where_there_is_no_stop_event(self, config_dict, tmp_path):
        """ReportGenerator gained stop_event in v5.5.0.

        Under an earlier WeeWX the attribute is never set, and the generator runs
        there as an extension.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        generator = weewx.jsongenerator.JSONGenerator(
            cd, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        del generator.stop_event
        try:
            generator.start()
        finally:
            generator.finalize()

        written = {f for f in os.listdir(os.path.join(html_root, 'data'))
                   if f.endswith('.json')}
        assert written

    def test_manifest_says_whether_images_are_drawn(self, config_dict, tmp_path):
        """A page offering a link to a PNG needs to know if anyone writes it.

        The skin says once, in [Generators]. Telling the page a second time in
        [DisplayOptions] gives two answers that can disagree.
        """
        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        skin_dict['Generators'] = {
            'generator_list': 'weewx.jsongenerator.JSONGenerator',
        }
        cd = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**cd['Station'])

        def run(sd):
            gen = weewx.jsongenerator.JSONGenerator(
                cd, sd, parameters.synthetic_dict['stop_ts'],
                first_run=True, stn_info=stn_info)
            try:
                gen.start()
            finally:
                gen.finalize()
            with open(os.path.join(html_root, 'data', 'index.json'),
                      encoding='utf-8') as fd:
                return json.load(fd)

        assert run(skin_dict)['images'] is False

        # A generator whose name merely holds the word draws no plots.
        skin_dict['Generators']['generator_list'] = \
            'weewx.jsongenerator.JSONGenerator, user.gallery.ImageGalleryGenerator'
        assert run(skin_dict)['images'] is False

        skin_dict['Generators']['generator_list'] = \
            'weewx.jsongenerator.JSONGenerator, weewx.imagegenerator.ImageGenerator'
        assert run(skin_dict)['images'] is True

    def test_manifest_lists_what_exists(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        names = {p['name'] for p in index['plots']}
        assert 'daytempdew' in names
        assert 'daynothing' not in names          # skipped, so not advertised
        entry = next(p for p in index['plots'] if p['name'] == 'daytempdew')
        assert entry['obs_types'] == ['outTemp', 'dewpoint']
        assert entry['title']

    def test_the_index_says_which_units_the_report_used(self, config_dict, tmp_path):
        """A reading the page fetches for itself has to be put in the same units.

        The forecast arrives in Celsius whichever source answered. Without this the
        page can only convert once a reader has picked a system by hand, and
        'Default' then means whatever the reading came in.
        """
        data_dir = run_generator(config_dict, tmp_path)
        with open(os.path.join(data_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        units = index['units']

        # Whatever the skin is set to, this has to be what the files were actually
        # written in. Comparing against a fixed unit would only restate the test
        # skin's configuration.
        plot = next(p for p in index['plots'] if p['name'] == 'daytempdew')
        with open(os.path.join(data_dir, 'daytempdew.json'), encoding='utf-8') as fd:
            written = json.load(fd)['unit']
        assert units['report'][units['groups']['outTemp']] == written
        assert plot['obs_types'][0] == 'outTemp'

        # Every group the page may show a reading from is named, or a reading the
        # page fetches for itself has nothing to be converted into.
        assert set(units['report']) >= set(units['groups'].values()) - {None}


class TestArchive:

    @pytest.fixture(scope='class')
    def archive_dir(self, config_dict, tmp_path_factory):
        """One archive run, shared by the tests that only read what it wrote.

        Writing it costs an aggregate query per grid slot, which is most of what this
        file costs to run. The tests below look at the same output instead of each
        building their own; the ones that need a second run still make it.
        """
        data_dir = run_generator(config_dict, tmp_path_factory.mktemp('archive'),
                                 archive=True)
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
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path, archive=True)

        assert os.path.getmtime(path) == before

    def test_a_new_grid_slot_rewrites_the_file(self, config_dict, tmp_path):
        """The current year is rewritten once the data reach into the next slot."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, archive=True,
                                 gen_ts=stop_ts - ARCHIVE_RESOLUTION)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        before = os.path.getmtime(path)

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)

        assert os.path.getmtime(path) != before

    def test_catchup_data_reach_the_archive(self, config_dict, tmp_path):
        """A file minutes old can still be hours behind.

        Stop the station, restart it, and the logger hands over everything it recorded
        meanwhile. The file on disk is younger than any age test would trip on, and
        missing a day of data. Reported by tkeffer in #1111.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, archive=True,
                                 gen_ts=stop_ts - 2 * 86400)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        with open(path, encoding='utf-8') as fd:
            before = json.load(fd)

        # The file is seconds old at this point. Only the data have moved.
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
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
        data_dir = run_generator(config_dict, tmp_path, archive=True)
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

        run_generator(config_dict, tmp_path, archive=True)

        assert os.path.getmtime(path) != before

    def test_archive_index_lists_years(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        assert index['interval'] == ARCHIVE_RESOLUTION
        groups = {g['name']: g for g in index['groups']}
        assert 'tempdew' in groups
        assert 2010 in groups['tempdew']['years']

    def test_a_finer_grid_is_written_for_the_recent_past(self, config_dict, tmp_path):
        """An hourly grid flattens a single day, so recent months also get a fine one."""
        data_dir = run_generator(config_dict, tmp_path, archive=True,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True,
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
            data_dir = run_generator(config_dict, root, archive=True, gen_ts=gen_ts,
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
            run_generator(config_dict, tmp_path_factory.mktemp('built'), archive=True,
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
                          archive=True, gen_ts=last_ts), 'archive')

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
                          archive=True, gen_ts=stop_ts, archive_options=options),
            'archive')

        grown_files = self.payloads(grown, only=current_month)
        assert grown_files, "no fine file for the month in progress"
        assert grown_files == self.payloads(built, only=current_month)

    def test_extending_costs_one_query_per_new_slot(self, config_dict, tmp_path,
                                                    monkeypatch):
        """The whole point. A year's file must not cost a query per slot in the year."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, archive=True,
                      gen_ts=stop_ts - ARCHIVE_RESOLUTION,
                      archive_options={'rebuild': '0'})

        calls = []
        original = weewx.xtypes.get_series
        monkeypatch.setattr(weewx.xtypes, 'get_series',
                            lambda *args, **kwargs: calls.append(args[1])
                            or original(*args, **kwargs))

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                      archive_options={'rebuild': '0'})

        assert calls, "the second run asked for nothing at all"
        # gen_json() is in here too, and its longest plot is a week. Anything longer
        # than that is the archive asking for a span of the year, which is what
        # carrying the file forward is supposed to have made unnecessary.
        assert max(span.stop - span.start for span in calls) <= 8 * 86400

    def test_a_rebuild_happens_once_a_calendar_day(self, config_dict, tmp_path):
        """Anything that changed further back than the last report needs this."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        index_path = lambda d: os.path.join(d, 'archive', 'index.json')
        rebuilt_at = lambda d: json.load(open(index_path(d), encoding='utf-8'))['rebuilt']

        data_dir = run_generator(config_dict, tmp_path, archive=True,
                                 gen_ts=stop_ts - 86400)
        first = rebuilt_at(data_dir)
        assert first is not None

        # Later the same day: carried forward, so the stamp does not move.
        run_generator(config_dict, tmp_path, archive=True,
                      gen_ts=stop_ts - 86400 + ARCHIVE_RESOLUTION)
        assert rebuilt_at(data_dir) == first

        # The next day: rebuilt, so it does.
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
        assert rebuilt_at(data_dir) != first

    def test_rebuilding_can_be_turned_off(self, config_dict, tmp_path):
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts - 86400,
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
        run_generator(config_dict, tmp_path, archive=True,
                      gen_ts=stop_ts - ARCHIVE_RESOLUTION,
                      archive_options={'rebuild': '0'})
        path = os.path.join(str(tmp_path), 'data', 'archive', 'tempdew-2010.json')

        with open(path, encoding='utf-8') as fd:
            payload = json.load(fd)
        payload['series'][0]['obs_type'] = 'somethingElse'
        payload['series'][0]['values'] = [-99.0] * payload['count']
        with open(path, 'w', encoding='utf-8') as fd:
            json.dump(payload, fd)

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        index_path = os.path.join(archive_dir, 'index.json')
        with open(index_path, encoding='utf-8') as fd:
            before = json.load(fd)

        os.remove(index_path)
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts - 45 * 86400,
                      archive_options=options)
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                      archive_options=options)

        with open(os.path.join(archive_dir, 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)
        for group in index['groups']:
            assert oldest not in group.get('fine', {}), \
                "index still names %s for %s" % (oldest, group['name'])

    def test_the_index_records_the_grid_of_each_file(self, config_dict, tmp_path):
        """Files are not all on the same grid, so the reader is told per file."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        archive_dir = os.path.join(data_dir, 'archive')

        days = self.days(archive_dir)
        assert len(days) == 5, days
        assert days[-1] == time.strftime('%Y-%m-%d', time.localtime(stop_ts))

    def test_the_grid_is_the_archive_interval(self, config_dict, tmp_path):
        """0 means 'as fine as the record', read off a record rather than a setting."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        options = {'raw_days': '2', 'raw_resolution': '0'}
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                                 archive_options=options)
        archive_dir = os.path.join(data_dir, 'archive')
        name = [f for f in os.listdir(archive_dir) if '-raw-' in f][0]
        with open(os.path.join(archive_dir, name), encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == parameters.synthetic_dict['interval']

    def test_days_that_fall_out_of_the_window_are_removed(self, config_dict, tmp_path):
        """The one tier with a horizon. Left alone it would grow a file a day forever."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts - 3 * 86400,
                      archive_options=self.OPTIONS)
        archive_dir = os.path.join(str(tmp_path), 'data', 'archive')
        before = self.days(archive_dir)

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                                 archive_options=self.OPTIONS)
        with open(os.path.join(data_dir, 'archive', 'index.json'), encoding='utf-8') as fd:
            index = json.load(fd)

        groups = {g['name']: g for g in index['groups']}
        assert len(groups['tempdew']['raw']) == 5
        assert set(groups['tempdew']['raw_intervals'].values()) == {1800}

    def test_it_is_off_unless_asked_for(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive=True)
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
            data_dir = run_generator(config_dict, target, archive=True,
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

        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                      archive_options={'budget': '1'})
        with open(path, encoding='utf-8') as fd:
            first = json.load(fd)
        assert first['count'] < self.whole_count(config_dict), \
            "the budget did not cut the file short"

        seen = [first['count']]
        for _ in range(3):
            run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
                          archive_options={'budget': '1'})
            with open(path, encoding='utf-8') as fd:
                seen.append(json.load(fd)['count'])

        assert seen == sorted(seen), "the file did not grow monotonically: %s" % seen
        assert seen[-1] > seen[0], "later runs added nothing"

    def test_the_short_file_says_how_far_it_got(self, config_dict, tmp_path):
        """'covered' has to be the truth, or the next run thinks it is done."""
        stop_ts = parameters.synthetic_dict['stop_ts']
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
            run_generator(config_dict, pieces, archive=True, gen_ts=stop_ts,
                          archive_options={'budget': '1'})
        whole = tmp_path_factory.mktemp('whole')
        run_generator(config_dict, whole, archive=True, gen_ts=stop_ts)

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
        full = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
        index_path = os.path.join(full, 'archive', 'index.json')
        with open(index_path, encoding='utf-8') as fd:
            before = json.load(fd)

        # Nothing is due now, and the budget is spent at once. The index must come out
        # the same anyway, because every file is still there.
        run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
            config_dict, tmp_path, archive=True, gen_ts=stop_ts,
            archive_options={'budget': '1', 'raw_days': '3', 'raw_resolution': '1800'})
        archive_dir = os.path.join(data_dir, 'archive')

        days = {f.split('-raw-')[1][:-len('.json')]
                for f in os.listdir(archive_dir) if '-raw-' in f}
        assert len(days) == 3, days


class TestPeriodSwitch:

    def test_periods_can_be_turned_off(self, config_dict, tmp_path):
        """A skin drawing from the archive does not need the four period files."""
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        assert os.path.exists(os.path.join(data_dir, 'daytempdew.json'))

        fresh = os.path.join(str(tmp_path), 'off')
        skin_dict = build_skin_dict(fresh, archive=True)
        skin_dict['JSONGenerator']['periods'] = 'false'
        cfg = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        generator = weewx.jsongenerator.JSONGenerator(
            cfg, skin_dict, parameters.synthetic_dict['stop_ts'], first_run=True,
            stn_info=weewx.station.StationInfo(**cfg['Station']))
        try:
            generator.start()
        finally:
            generator.finalize()

        data = os.path.join(fresh, 'data')
        assert not os.path.exists(os.path.join(data, 'daytempdew.json'))
        # The archive is untouched by the switch.
        assert os.path.exists(os.path.join(data, 'archive', 'tempdew-2010.json'))


class TestArchiveSeriesShapes:
    """What a series in an archive file can carry beyond one number per slot."""

    def test_a_wind_vector_keeps_its_components(self, config_dict, tmp_path):
        """A vector is a pair. The evenly spaced grid holds it as two arrays.

        Without this the wind vector plot is the one chart the archive cannot draw,
        and the page would need a second source just for it.
        """
        stop_ts = parameters.synthetic_dict['stop_ts']
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts,
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
        data_dir = run_generator(config_dict, tmp_path, archive=True, gen_ts=stop_ts)
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
            run_generator(config_dict, grown, archive=True, archive_options=options,
                          gen_ts=stop_ts - (n - 1) * ARCHIVE_RESOLUTION)
        built = tmp_path_factory.mktemp('shapes_built')
        run_generator(config_dict, built, archive=True, gen_ts=stop_ts,
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

    def test_round_seq_keeps_gaps(self):
        out = weewx.jsongenerator._round_seq([1.23456, None, 2.0], 2)
        assert out == [1.23, None, 2.0]

    def test_round_seq_without_rounding(self):
        assert weewx.jsongenerator._round_seq([1.23456, None], None) == [1.23456, None]

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


# ==============================================================================
#                        points that carry nothing
# ==============================================================================

def entry_with(times, values, **extra):
    e = {'obs_type': 'extraTemp1', 'time': list(times), 'values': list(values)}
    e.update(extra)
    return e


def test_empty_points_are_left_out():
    """A source reporting every five minutes fills one archive record in five."""
    times = [1000 + n * 60 for n in range(10)]
    values = [None] * 10
    for n in (0, 5):
        values[n] = 20.0 + n

    entry = entry_with(times, values)
    weewx.jsongenerator._drop_empty_points(entry, 86400, None)

    assert entry['values'] == [20.0, 25.0]
    assert entry['time'] == [1000, 1300]


def test_a_duration_string_is_understood():
    """time_length may be '27h', the same as everywhere else it is read."""
    entry = entry_with([1000 + n * 60 for n in range(40)],
                       [20.0] + [None] * 38 + [21.0])

    weewx.jsongenerator._drop_empty_points(entry, '27h', 0.1)

    assert entry['values'] == [20.0, 21.0]


def test_the_source_rhythm_decides_what_a_gap_is():
    """Ten minutes between readings is a break for one station and normal for another."""
    # A source on a ten-minute rhythm, one archive record in ten carrying its reading.
    times = [1000 + n * 60 for n in range(41)]
    values = [None] * 41
    for n in range(0, 41, 10):
        values[n] = 20.0 + n

    entry = entry_with(times, values)
    weewx.jsongenerator._drop_empty_points(entry, 86400, None)

    # Its own rhythm, so the line runs through: no gap anywhere.
    assert entry['values'] == [20.0, 30.0, 40.0, 50.0, 60.0]
    assert None not in entry['values']


def test_a_silence_several_times_the_rhythm_is_a_gap():
    times = [1000 + n * 60 for n in range(80)]
    values = [None] * 80
    for n in (0, 10, 20, 30):          # ten-minute rhythm ...
        values[n] = 20.0
    values[79] = 21.0                  # ... then nothing for 49 minutes

    entry = entry_with(times, values)
    weewx.jsongenerator._drop_empty_points(entry, 86400, None)

    assert entry['values'].count(None) == 1
    assert entry['values'][-1] == 21.0


def test_a_long_silence_stays_a_gap():
    """Without this a sensor that stopped for hours would be drawn as a straight line."""
    times = [1000 + n * 60 for n in range(40)]
    values = [None] * 40
    values[0] = 20.0
    values[39] = 21.0

    entry = entry_with(times, values)
    # A tenth of a day is 8640 s; the silence here is 38 minutes, so it is not a gap.
    # Two points are too few to measure a rhythm from, so nothing else applies.
    weewx.jsongenerator._drop_empty_points(entry, 86400, 0.1)
    assert entry['values'] == [20.0, 21.0]

    entry = entry_with(times, values)
    # Against a one-hour plot the same silence is most of it, so it is.
    weewx.jsongenerator._drop_empty_points(entry, 3600, 0.1)
    assert entry['values'] == [20.0, None, 21.0]


def test_leading_and_trailing_nothing_is_dropped():
    entry = entry_with([1, 2, 3, 4, 5], [None, None, 7.0, None, None])
    weewx.jsongenerator._drop_empty_points(entry, 86400, 0.1)

    assert entry['values'] == [7.0]
    assert entry['time'] == [3]


def test_parallel_sequences_are_filtered_along():
    """bar_width and the vector components line up with values, index for index."""
    entry = entry_with([1, 2, 3], [5.0, None, 7.0],
                       bar_width=[3600, 3600, 3600],
                       vector_x=[1.0, 2.0, 3.0], vector_y=[4.0, 5.0, 6.0])
    weewx.jsongenerator._drop_empty_points(entry, 86400, None)

    assert entry['values'] == [5.0, 7.0]
    assert entry['bar_width'] == [3600, 3600]
    assert entry['vector_x'] == [1.0, 3.0]
    assert entry['vector_y'] == [4.0, 6.0]


def test_a_full_series_is_left_exactly_as_it_was():
    entry = entry_with([1, 2, 3], [5.0, 6.0, 7.0])
    weewx.jsongenerator._drop_empty_points(entry, 86400, 0.1)

    assert entry['values'] == [5.0, 6.0, 7.0]
    assert entry['time'] == [1, 2, 3]
