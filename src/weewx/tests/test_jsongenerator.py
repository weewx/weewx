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
from weeutil.config import accumulateLeaves

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


def build_skin_dict(html_root, archive=False):
    """A skin dictionary complete enough for the generator to run against."""
    # The delta-time formats contain things like %(minute_label)s, which ConfigObj would
    # otherwise try to resolve as interpolation. The report engine turns interpolation
    # off for the same reason.
    weewx.defaults.defaults.interpolation = False

    mine = configobj.ConfigObj(PLOT_CONF.splitlines(), interpolation=False)

    json_conf = {'json_dest_dir': 'data', 'round': '3'}
    if archive:
        json_conf['Archive'] = {'enable': 'true', 'resolution': '3600',
                                'stale_age': '3600'}

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


def run_generator(config_dict, tmp_path, archive=False, gen_ts=None):
    """Run the generator against the test database and return its output directory."""
    html_root = str(tmp_path)
    skin_dict = build_skin_dict(html_root, archive=archive)

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
        skin_dict['ImageGenerator']['day_images']['daytempdew']['yscale'] =             ['0.0', '360.0', '45.0']
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


class TestArchive:

    def test_writes_one_file_per_group_and_year(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        archive_dir = os.path.join(data_dir, 'archive')
        written = sorted(f for f in os.listdir(archive_dir) if f.endswith('.json'))

        # The test data sit in 2010, and the group name has the 'day' prefix stripped.
        assert 'tempdew-2010.json' in written
        assert 'index.json' in written

    def test_grid_is_regular_and_timestamps_implied(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        with open(path, encoding='utf-8') as fd:
            payload = json.load(fd)

        assert payload['interval'] == 3600
        assert payload['start'] % 3600 == 0
        # No 'time' array at all: that is the point of the fixed grid.
        for series in payload['series']:
            assert 'time' not in series
            assert len(series['values']) == payload['count']

    def test_values_land_in_the_right_slots(self, config_dict, tmp_path):
        data_dir = run_generator(config_dict, tmp_path, archive=True)
        path = os.path.join(data_dir, 'archive', 'tempdew-2010.json')
        with open(path, encoding='utf-8') as fd:
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
                                 gen_ts=stop_ts - 7200)
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
        assert filled(after) > filled(before) + 40

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

        assert index['interval'] == 3600
        groups = {g['name']: g for g in index['groups']}
        assert 'tempdew' in groups
        assert 2010 in groups['tempdew']['years']


class TestSummaryImage:
    """The picture of the current readings, which is what people actually link to."""

    @staticmethod
    def _run(config_dict, tmp_path, **overrides):
        import weewx.summaryimage

        html_root = str(tmp_path)
        skin_dict = build_skin_dict(html_root)
        summary = {'enable': 'true', 'filename': 'current.png',
                   'observations': 'outTemp, windSpeed, rain, barometer'}
        summary.update(overrides)
        skin_dict['SummaryImageGenerator'] = summary

        config_dict = configobj.ConfigObj(config_dict.dict(), interpolation=False)
        stn_info = weewx.station.StationInfo(**config_dict['Station'])

        generator = weewx.summaryimage.SummaryImageGenerator(
            config_dict, skin_dict, parameters.synthetic_dict['stop_ts'],
            first_run=True, stn_info=stn_info)
        try:
            generator.start()
        finally:
            generator.finalize()
        return os.path.join(html_root, summary['filename'])

    def test_writes_an_image(self, config_dict, tmp_path):
        from PIL import Image

        path = self._run(config_dict, tmp_path)
        assert os.path.exists(path), "no image written"

        with Image.open(path) as img:
            assert img.format == 'PNG'
            # Default width is 900, drawn at 2x and downsampled back.
            assert img.width == 900
            # Tall enough for a title and two rows of readings, not a sliver.
            assert 150 < img.height < 400

    def test_disabled_by_default(self, config_dict, tmp_path):
        path = self._run(config_dict, tmp_path, enable='false')
        assert not os.path.exists(path)

    def test_width_and_columns_are_honoured(self, config_dict, tmp_path):
        from PIL import Image

        one = self._run(config_dict, tmp_path, width='600', columns='1',
                        filename='narrow.png')
        with Image.open(one) as img:
            assert img.width == 600
            narrow_height = img.height

        two = self._run(config_dict, tmp_path, width='600', columns='2',
                        filename='wide.png')
        with Image.open(two) as img:
            # Same readings in two columns need fewer rows, so less height.
            assert img.height < narrow_height

    def test_survives_an_unknown_observation(self, config_dict, tmp_path):
        """A type this station does not have must be skipped, not crash the report."""
        path = self._run(config_dict, tmp_path,
                         observations='outTemp, thisDoesNotExist, barometer')
        assert os.path.exists(path)


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
