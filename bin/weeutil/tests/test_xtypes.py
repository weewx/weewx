try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

import configobj
import weewx.manager
import weeutil.xtypes


def new_type(obs_type, record):
    if obs_type == 'dewpoint':
        if record['usUnits'] == weewx.US:
            return weewx.wxformulas.dewpointF(record.get('outTemp'), record.get('outHumidity'))
        elif record['usUnits'] == weewx.METRIC or record['usUnits'] == weewx.METRICWX:
            return weewx.wxformulas.dewpointC(record.get('outTemp'), record.get('outHumidity'))
        else:
            raise ValueError("Unknown unit system %s" % record['usUnits'])
    else:
        raise ValueError(obs_type)


record = {
    'dateTime': 1567515300, 'usUnits': 1, 'interval': 5, 'barometer': 29.99, 'pressure': 29.259303850622302,
    'altimeter': 30.001561119603156, 'inTemp': 73.0, 'outTemp': 55.7, 'inHumidity': 54.0, 'outHumidity': 90.0,
    'windSpeed': 0.0, 'windDir': None, 'windGust': 2.0, 'windGustDir': 270.0, 'rainRate': 0.0, 'rain': 0.0,
    'dewpoint': 52.81113360826872, 'windchill': 55.7, 'heatindex': 55.7, 'ET': 0.0, 'radiation': 0.0, 'UV': 0.0
}

print("Dewpoint before is %f", record['dewpoint'])
print("Pressure before is %f", record['pressure'])
del record['dewpoint']
del record['pressure']

config_dict = configobj.ConfigObj('/home/weewx/weewx.conf', encoding='utf8')
db_binder = weewx.manager.DBBinder(config_dict)
db_manager = db_binder.get_manager('wx_binding')
ps = weeutil.xtypes.PressureCooker(700, db_manager)

with mock.patch.object(db_manager, 'getRecord', return_value={'usUnits': 1, 'outTemp':80.3}) as mock_mgr:
    t = ps._get_temperature_12h_F(record['dateTime'])
    print(t)
#
# my_types = weeutil.xtypes.ExtendedTypes(record, {'dewpoint': new_type,
#                                                  'pressure': ps.calc
#                                                  })
#
# print('dewpoint after =', my_types['dewpoint'])
# print('pressure after =', my_types['pressure'])
