#
#    Copyright (c) 2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.wxformulas"""

import unittest

import weewx.wxformulas


class WXFormulasTest(unittest.TestCase):

    def test_dewpoint(self):
        self.assertEqual("%.1f" % weewx.wxformulas.dewpointF(68, 50), "48.7")
        self.assertEqual("%.1f" % weewx.wxformulas.dewpointF(32, 50), "15.5")
        self.assertEqual("%.1f" % weewx.wxformulas.dewpointF(-10, 50), "-23.5")

    def test_heatindex(self):
        self.assertEqual("%.1f" % weewx.wxformulas.heatindexF(75.0, 50.0), "75.0")
        self.assertEqual("%.1f" % weewx.wxformulas.heatindexF(80.0, 50.0), "80.8")
        self.assertEqual("%.1f" % weewx.wxformulas.heatindexF(80.0, 95.0), "86.4")
        self.assertEqual("%.1f" % weewx.wxformulas.heatindexF(90.0, 50.0), "94.6")
        self.assertEqual("%.1f" % weewx.wxformulas.heatindexF(90.0, 95.0), "126.6")

    def test_altimeter_pressure(self):
        self.assertEqual("%.3f" % weewx.wxformulas.altimeter_pressure_US(28.0, 0.0), "28.002")
        self.assertEqual("%.3f" % weewx.wxformulas.altimeter_pressure_US(28.0, 1000.0), "29.043")
        self.assertEqual("%.1f" % weewx.wxformulas.altimeter_pressure_Metric(948.08, 0.0), "948.2")
        self.assertEqual("%.1f" % weewx.wxformulas.altimeter_pressure_Metric(948.08, 304.8), "983.4")

    def test_solar_rad(self):
        results = ["%.2f" % weewx.wxformulas.solar_rad_Bras(42, -72, 0, t * 3600 + 1422936471) for t in range(24)]
        self.assertEqual(results,
                         ['0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '1.86', '100.81', '248.71',
                          '374.68', '454.90', '478.76', '443.47', '353.23', '220.51', '73.71', '0.00', '0.00', '0.00',
                          '0.00', '0.00', '0.00'])
        results = ["%.2f" % weewx.wxformulas.solar_rad_RS(42, -72, 0, t * 3600 + 1422936471) for t in range(24)]
        self.assertEqual(results,
                         ['0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.09', '79.31', '234.77',
                          '369.80', '455.66', '481.15', '443.44', '346.81', '204.64', '52.63', '0.00', '0.00', '0.00',
                          '0.00', '0.00', '0.00'])

    def test_humidex(self):
        self.assertEqual("%.2f" % weewx.wxformulas.humidexC(30.0, 80.0), "43.64")
        self.assertEqual("%.2f" % weewx.wxformulas.humidexC(30.0, 20.0), "30.00")
        self.assertEqual("%.2f" % weewx.wxformulas.humidexC(0.0, 80.0), "0.00")
        self.assertIsNone(weewx.wxformulas.humidexC(30.0, None))

    def test_equation_of_time(self):
        # 1 October
        self.assertEqual("%.4f" % weewx.wxformulas.equation_of_time(274), "0.1889")

    def test_hour_angle(self):
        self.assertEqual("%.4f" % weewx.wxformulas.hour_angle(15.5, -16.25, 274), "0.6821")
        self.assertEqual("%.4f" % weewx.wxformulas.hour_angle(0, -16.25, 274), "2.9074")

    def test_solar_declination(self):
        # 1 October
        self.assertEqual("%.6f" % weewx.wxformulas.solar_declination(274), "-0.075274")

    def test_sun_radiation(self):
        self.assertEqual("%.3f" % weewx.wxformulas.sun_radiation(doy=274,
                                                                 latitude_deg=16.217, longitude_deg=-16.25,
                                                                 tod_utc=16.0,
                                                                 interval=1.0), "3.543")

    def test_longwave_radiation(self):
        # In mm/day
        self.testEqual("%.1f" % weewx.wxformulas.longwave_radiation(Tmin_C=19.1, Tmax_C=25.1,
                                                                    ea=2.1, Rs=14.5, Rso=18.8, rh=50), "3.5")
        self.testEqual("%.1f" % weewx.wxformulas.longwave_radiation(Tmin_C=28, Tmax_C=28,
                                                                    ea=3.402, Rs=0, Rso=0, rh=40), "2.4")

    def test_ET(self):
        sr_mean_wpm2 = 680.56  # == 2.45 MJ/m^2/hr
        timestamp = 1475337600  # 1-Oct-2016 at 16:00UTC
        self.testEqual("%.2f" % weewx.wxformulas.evapotranspiration_Metric(Tmin_C=38, Tmax_C=38,
                                                                           rh_min=52, rh_max=52,
                                                                           sr_mean_wpm2=sr_mean_wpm2, ws_mps=3.3,
                                                                           wind_height_m=2,
                                                                           latitude_deg=16.217, longitude_deg=-16.25,
                                                                           altitude_m=8, timestamp=timestamp), "0.63")

        sr_mean_wpm2 = 0.0  # Night time
        timestamp = 1475294400  # 1-Oct-2016 at 04:00UTC (0300 local)
        self.assertEqual("%.2f" % weewx.wxformulas.evapotranspiration_Metric(Tmin_C=28, Tmax_C=28,
                                                                             rh_min=90, rh_max=90,
                                                                             sr_mean_wpm2=sr_mean_wpm2, ws_mps=3.3,
                                                                             wind_height_m=2,
                                                                             latitude_deg=16.217, longitude_deg=-16.25,
                                                                             altitude_m=8, timestamp=timestamp), "0.03")
        sr_mean_wpm2 = 860
        timestamp = 1469829600  # 29-July-2016 22:00 UTC (15:00 local time)
        self.assertEqual("%.3f" % weewx.wxformulas.evapotranspiration_US(Tmin_F=87.8, Tmax_F=89.1,
                                                                         rh_min=34, rh_max=38,
                                                                         sr_mean_wpm2=sr_mean_wpm2, ws_mph=9.58,
                                                                         wind_height_ft=6,
                                                                         latitude_deg=45.7, longitude_deg=-121.5,
                                                                         altitude_ft=700, timestamp=timestamp), "0.028")

    if __name__ == '__main__':
        unittest.main()
