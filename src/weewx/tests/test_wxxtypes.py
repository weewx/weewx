#
#    Copyright (c) 2019-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test weather-related XTypes extensions."""

import logging
import math
import pytest
from unittest import mock

import weewx.wxxtypes
import weeutil.logger
from weewx.units import ValueTuple
import weewx.schemas.wview_extended
import gen_fake_data

# weewx.debug = 1

log = logging.getLogger(__name__)
# Set up logging using the defaults.
weeutil.logger.setup('weetest_wxxtypes')

altitude_vt = weewx.units.ValueTuple(700, "foot", "group_altitude")
latitude = 45
longitude = -122

# Test values:
record_1 = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 88.7,
    'inHumidity': 54.0, 'outHumidity': 90.0, 'windSpeed': 12.0, 'windDir': 250.0, 'windGust': 15.0,
    'windGustDir': 270.0, 'rain': 0.02,
}

# These are the correct values
correct = {
    'dewpoint': 85.37502296294483,
    'inDewpoint': 55.3580124202402,
    'windchill': 88.7,
    'heatindex': 116.1964007023,
    'humidex': 121.31401772489724,
    'appTemp': 99.36405806590201,
    'beaufort': 3,
    'windrun': 1.0
}


class TestSimpleFunctions:

    def setup_method(self):
        # Make a copy. We may be modifying it.
        self.record = dict(record_1)
        self.wx_calc = weewx.wxxtypes.WXXTypes(altitude_vt, latitude, longitude)

    def test_appTemp(self):
        self.calc('appTemp', 'outTemp', 'outHumidity', 'windSpeed')

    def test_beaufort(self):
        self.calc('beaufort', 'windSpeed')

    def test_dewpoint(self):
        self.calc('dewpoint', 'outTemp', 'outHumidity')

    def test_heatindex(self):
        self.calc('heatindex', 'outTemp', 'outHumidity')

    def test_humidex(self):
        self.calc('humidex', 'outTemp', 'outHumidity')

    def test_inDewpoint(self):
        self.calc('inDewpoint', 'inTemp', 'inHumidity')

    def test_windchill(self):
        self.calc('windchill', 'outTemp', 'windSpeed')

    def test_windrun(self):
        self.calc('windrun', 'windSpeed')

    def test_windDir_default(self):
        # With the default, windDir should be set to None if the windSpeed is zero.
        self.record['windSpeed'] = 0.0
        result = self.wx_calc.get_scalar('windDir', self.record, None)
        assert result[0] is None

    def test_windDir_no_ignore(self):
        # Now let's not ignore zero wind. This should become a No-op, which is signaled by
        # raising weewx.NoCalculate
        wx_calc = weewx.wxxtypes.WXXTypes(altitude_vt, latitude, longitude, force_null=False)
        with pytest.raises(weewx.NoCalculate):
            wx_calc.get_scalar('windDir', self.record, None)

    def calc(self, key, *crits):
        """Calculate derived type 'key'. Parameters in "crits" are required to perform the
        calculation. Their presence will be tested.
        """
        result = self.wx_calc.get_scalar(key, self.record, None)
        assert result[0] == pytest.approx(correct[key], abs=1e-3)
        # Now try it, but with a critical key missing
        for crit in crits:
            # Restore the record
            self.setup_method()
            # Set the critical key to None
            self.record[crit] = None
            result = self.wx_calc.get_scalar(key, self.record, None)
            # Result should be None
            assert result[0] is None
            # Try again, but delete the key completely. Should raise an exception.
            with pytest.raises(weewx.CannotCalculate):
                del self.record[crit]
                self.wx_calc.get_scalar(key, self.record, None)

    def test_unknownKey(self):
        """Make sure get_scalar() raises weewx.UnknownType when presented with an unknown key"""
        with pytest.raises(weewx.UnknownType):
            self.wx_calc.get_scalar('foo', self.record, None)


# Test values for the PressureCooker test:
record_2 = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'inTemp': 73.0, 'outTemp': 55.7,
    'inHumidity': 54.0, 'outHumidity': 90.0, 'windSpeed': 0.0, 'windDir': None, 'windGust': 2.0,
    'windGustDir': 270.0, 'rain': 0.0, 'windchill': 55.7, 'heatindex': 55.7,
    'pressure': 29.259303850622302, 'barometer': 29.99, 'altimeter': 30.012983156964353,
}

# These are the correct values
pressure = 29.259303850622302
barometer = 30.01396476909608
altimeter = 30.012983156964353


class TestPressureCooker:
    """Test the class PressureCooker"""

    @pytest.fixture(autouse=True)
    def setup(self):
        # Make a copy. We will be modifying it.
        self.record = dict(record_2)

    def test_get_temperature_12h(self):
        pc = weewx.wxxtypes.PressureCooker(altitude_vt)

        # Mock a database in US units
        db_manager = mock.Mock()
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            # Make sure the mocked database manager got called with a time 12h ago
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            # The results should be in US units
            assert t == (80.3, 'degree_F', 'group_temperature')

        # Make sure the value has been cached:
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            # The cached value should have been used
            mock_mgr.assert_not_called()
            assert t == (80.3, 'degree_F', 'group_temperature')

    def test_get_temperature_12h_metric(self):
        pc = weewx.wxxtypes.PressureCooker(altitude_vt)

        # Mock a database in METRICWX units
        db_manager = mock.Mock()
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX,
                                             'outTemp': 30.0}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            # Make sure the mocked database manager got called with a time 12h ago
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            assert t == (30.0, 'degree_C', 'group_temperature')

    def test_get_temperature_12h_missing(self):
        pc = weewx.wxxtypes.PressureCooker(altitude_vt)

        db_manager = mock.Mock()
        # Mock a database missing a record from 12h ago
        with mock.patch.object(db_manager, 'getRecord',
                               return_value=None) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            assert t is None

        # Mock a database that has a record from 12h ago, but it's missing outTemp
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX}) as mock_mgr:
            t = pc._get_temperature_12h(self.record['dateTime'], db_manager)
            mock_mgr.assert_called_once_with(self.record['dateTime'] - 12 * 3600, max_delta=1800)
            assert t is None

    def test_pressure(self):
        """Test interface pressure()"""

        # Create a pressure cooker
        pc = weewx.wxxtypes.PressureCooker(altitude_vt)

        # Mock up a database manager in US units
        db_manager = mock.Mock()
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.US, 'outTemp': 80.3}):
            p = pc.pressure(self.record, db_manager)
            assert p == (pressure, 'inHg', 'group_pressure')

            # Remove 'outHumidity' and try again. Should now raise exception.
            del self.record['outHumidity']
            with pytest.raises(weewx.CannotCalculate):
                pc.pressure(self.record, db_manager)

        # Mock a database missing a record from 12h ago
        with mock.patch.object(db_manager, 'getRecord',
                               return_value=None):
            with pytest.raises(weewx.CannotCalculate):
                pc.pressure(self.record, db_manager)

        # Mock a database that has a record from 12h ago, but it's missing outTemp
        with mock.patch.object(db_manager, 'getRecord',
                               return_value={'usUnits': weewx.METRICWX}):
            with pytest.raises(weewx.CannotCalculate):
                pc.pressure(self.record, db_manager)

    def test_altimeter(self):
        """Test interface altimeter()"""

        # First, try the example in wxformulas.py. This has elevation 1,000 feet
        pc = weewx.wxxtypes.PressureCooker((1000.0, 'foot', 'group_altitude'))
        a = pc.altimeter({'usUnits': 1, 'pressure': 28.0})
        assert a[0] == pytest.approx(29.04, abs=1e-2)
        assert a[1:] == ('inHg', 'group_pressure')

        pc = weewx.wxxtypes.PressureCooker(altitude_vt)
        a = pc.altimeter(self.record)
        assert a == (altimeter, 'inHg', 'group_pressure')

        # Remove 'pressure' from the record and check for exception
        del self.record['pressure']
        with pytest.raises(weewx.CannotCalculate):
            pc.altimeter(self.record)

    def test_barometer(self):
        """Test interface barometer()"""

        # Create a pressure cooker
        pc = weewx.wxxtypes.PressureCooker(altitude_vt)

        b = pc.barometer(self.record)
        assert b == (barometer, 'inHg', 'group_pressure')

        # Remove 'outTemp' from the record and check for exception
        del self.record['outTemp']
        with pytest.raises(weewx.CannotCalculate):
            pc.barometer(self.record)


class RainGenerator:
    """Generator object that returns an increasing deluge of rain."""

    def __init__(self, timestamp, time_increment=60, rain_increment=0.01):
        """Initialize the rain generator."""
        self.timestamp = timestamp
        self.time_increment = time_increment
        self.rain_increment = rain_increment
        self.rain = 0

    def __iter__(self):
        return self

    def __next__(self):
        """Advance and return the next rain event"""
        event = {'dateTime': self.timestamp, 'usUnits': weewx.US, 'interval': self.time_increment,
                 'rain': self.rain}
        self.timestamp += self.time_increment
        self.rain += self.rain_increment
        return event

    # For Python 2 compatibility:
    next = __next__


class TestRainRater:
    start = 1571083200  # 14-Oct-2019 1300 PDT
    rain_period = 900  # 15 minute sliding window
    retain_period = 915

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up and populate an in-memory database"""
        self.db_manager = weewx.manager.Manager.open_with_create(
            {
                'database_name': ':memory:',
                'driver': 'weedb.sqlite'
            },
            schema=weewx.schemas.wview_extended.schema)
        # Create a generator that will issue rain records on demand
        self.rain_generator = RainGenerator(TestRainRater.start)
        # Populate the database with 30 minutes worth of rain.
        N = 30
        for record in self.rain_generator:
            self.db_manager.addRecord(record)
            N -= 1
            if not N:
                break
        yield
        self.db_manager.close()
        self.db_manager = None

    def test_add_US(self):
        """Test adding rain data in the US system"""
        rain_rater = weewx.wxxtypes.RainRater(TestRainRater.rain_period,
                                              TestRainRater.retain_period)

        # Get the next record out of the rain generator.
        record = next(self.rain_generator)
        # Make sure the event is what we think it is
        assert record['dateTime'] == TestRainRater.start + 30 * 60
        # Add it to the RainRater object
        rain_rater.add_loop_packet(record)
        # Get the rainRate out of it
        rate = rain_rater.get_scalar('rainRate', record, self.db_manager)
        # Check its values
        assert rate[0] == pytest.approx(13.80, abs=1e-2)
        assert rate[1:] == ('inch_per_hour', 'group_rainrate')

    def test_add_METRICWX(self):
        """Test adding rain data in the METRICWX system"""
        rain_rater = weewx.wxxtypes.RainRater(TestRainRater.rain_period,
                                              TestRainRater.retain_period)

        # Get the next record out of the rain generator.
        record = next(self.rain_generator)
        # Make sure the event is what we think it is
        assert record['dateTime'] == TestRainRater.start + 30 * 60
        # Convert to metric:
        record_metric = weewx.units.to_METRICWX(record)
        # Add it to the RainRater object
        rain_rater.add_loop_packet(record_metric)
        # The results should be in metric.
        # Get the rainRate out of it
        rate = rain_rater.get_scalar('rainRate', record, self.db_manager)
        # Check its values
        assert rate[0] == pytest.approx(350.52, abs=1e-2)
        assert rate[1:] == ('mm_per_hour', 'group_rainrate')

    def test_trim(self):
        """"Test trimming old events"""
        rain_rater = weewx.wxxtypes.RainRater(TestRainRater.rain_period,
                                              TestRainRater.retain_period)

        # Add 20 minutes worth of rain
        N = 20
        for record in self.rain_generator:
            rain_rater.add_loop_packet(record)
            N -= 1
            if not N:
                break

        # The rain record object should have the last 15 minutes worth of rain in it. Let's peek
        # inside to check. The first value should be 15 minutes old
        assert rain_rater.rain_events[0][0] == record['dateTime'] - 15 * 60
        # The last value should be the record we just put in it:
        assert rain_rater.rain_events[-1][0] == record['dateTime']

        # Get the rainRate
        rate = rain_rater.get_scalar('rainRate', record, self.db_manager)
        # Check its values
        assert rate[0] == pytest.approx(25.20, abs=1e-2)
        assert rate[1:] == ('inch_per_hour', 'group_rainrate')


class TestDelta:
    """Test XTypes extension 'Delta'."""

    def test_delta(self):
        # Instantiate a Delta for calculating 'rain' from 'totalRain':
        delta = weewx.wxxtypes.Delta({'rain': {'input': 'totalRain'}})

        # Add a new total rain to it:
        record = {'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'totalRain': 0.05}
        val = delta.get_scalar('rain', record, None)
        assert val[0] is None

        # Add the same record again. No change in totalRain, so rain should be zero
        val = delta.get_scalar('rain', record, None)
        assert val[0] == 0.0

        # Add a little rain.
        record['totalRain'] += 0.01
        val = delta.get_scalar('rain', record, None)
        assert val[0] == pytest.approx(0.01, abs=1e-6)

        # Adding None should reset counter
        record['totalRain'] = None
        val = delta.get_scalar('rain', record, None)
        assert val[0] is None

        # Try an unknown type
        with pytest.raises(weewx.UnknownType):
            delta.get_scalar('foo', record, None)

class TestET:
    # Start in the middle of summer
    start = 1562007600  # 1-Jul-2019 1200
    rain_period = 900  # 15 minute sliding window
    retain_period = 915

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up an in-memory database"""
        self.db_manager = weewx.manager.Manager.open_with_create(
            {
                'database_name': ':memory:',
                'driver': 'weedb.sqlite'
            },
            schema=weewx.schemas.wview_extended.schema)

        # Populate the database with 60 minutes worth of data at 5 minute
        # intervals. Set the annual phase to half a year, so that the
        # temperatures will be high. Set the daily phase to pi/2, so it will be
        # around noon.
        for record in gen_fake_data.gen_fake_records(TestET.start, TestET.start + 3600,
                                                     interval=300,
                                                     annual_phase_offset=math.pi,
                                                     day_phase_offset=math.pi):
            # Add some radiation and humidity:
            record['radiation'] = 860
            record['outHumidity'] = 50
            self.db_manager.addRecord(record)
        yield
        # Clean up
        self.db_manager.close()
        self.db_manager = None

    def test_ET(self):
        wx_xtypes = weewx.wxxtypes.ETXType(altitude_vt,
                                           latitude_f=latitude,
                                           longitude_f=longitude)
        ts = self.db_manager.lastGoodStamp()
        record = self.db_manager.getRecord(ts)
        et_vt = wx_xtypes.get_scalar('ET', record, self.db_manager)

        assert et_vt[0] == pytest.approx(0.002077, abs=1e-5)
        assert (et_vt[1], et_vt[2]) == ("inch", "group_rain")


class TestWindRun:
    """Windrun calculations always seem to give us trouble..."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.wx_calc = weewx.wxxtypes.WXXTypes(altitude_vt, latitude, longitude)

    def test_US(self):
        record = {'usUnits': weewx.US, 'interval': 5, 'windSpeed': 3.8}
        result = self.wx_calc.get_scalar('windrun', record, None)
        assert result[0] == pytest.approx(0.3167, abs=1e-4)

    def test_METRIC(self):
        record = {'usUnits': weewx.METRIC, 'interval': 5, 'windSpeed': 3.8}
        result = self.wx_calc.get_scalar('windrun', record, None)
        assert result[0] == pytest.approx(0.3167, abs=1e-4)

    def test_METRICWX(self):
        record = {'usUnits': weewx.METRICWX, 'interval': 5, 'windSpeed': 3.8}
        result = self.wx_calc.get_scalar('windrun', record, None)
        assert result[0] == pytest.approx(1.14, abs=1e-4)
