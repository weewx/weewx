#
#    Copyright (c) 2021-2022 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test algorithms in the Report Engine"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import logging
import os.path
import sys
import unittest

import weeutil.config
import weeutil.logger
import weewx
from weewx.reportengine import _build_skin_dict

log = logging.getLogger(__name__)
weewx.debug = 1

CONFIG_DICT_INI = """
WEEWX_ROOT = '../../..'

[StdReport]
    SKIN_ROOT = skins
    [[SeasonsReport]]
        skin = Seasons
    [[Defaults]]
"""
# Find WEEWX_ROOT by working up from this file's location:
CONFIG_DICT = weeutil.config.config_from_str(CONFIG_DICT_INI)
CONFIG_DICT['WEEWX_ROOT'] = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../..'))

# For MacOS, the default logging logs to /var/log/weewx.log, which is a privileged location.
# Change to something unprivileged, so we don't have to run test suites as root.
if sys.platform == 'darwin':
    LOGGING = {
        'Logging': {
            'handlers': {
                'rotate': {
                    'filename': '/var/tmp/weewx.log'
                }
            }
        }
    }
    CONFIG_DICT.merge(LOGGING)

weeutil.logger.setup('test_reportengine', CONFIG_DICT)


class TestReportEngine(unittest.TestCase):
    """Test elements of StdReportEngine"""

    def setUp(self):
        self.config_dict = weeutil.config.deep_copy(CONFIG_DICT)

    def test_default(self):
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'inHg')
        self.assertEqual(skin_dict['Units']['Labels']['day'], [" day", " days"])
        # Without a 'lang' entry, there should not be a 'Texts' section:
        self.assertNotIn('Texts', skin_dict)

    def test_defaults_with_defaults_override(self):
        """Test override in [[Defaults]]"""
        # Override the units to be used for group pressure
        self.config_dict['StdReport']['Defaults'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_defaults_with_reports_override(self):
        """Test override for a specific report"""
        # Override the units to be used for group pressure
        self.config_dict['StdReport']['SeasonsReport'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_override_unit_system_in_defaults(self):
        """Test specifying a unit system in [[Defaults]]"""
        # Specify that metric be used by default
        self.config_dict['StdReport']['Defaults']['unit_system'] = 'metricwx'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_override_unit_system_in_report(self):
        """Test specifying a unit system for a specific report"""
        # Specify that metric be used for this specific report
        self.config_dict['StdReport']['SeasonsReport']['unit_system'] = 'metricwx'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_override_unit_system_in_report_and_defaults(self):
        """Test specifying a unit system for a specific report, versus overriding a unit
        in the [[Defaults]] section"""
        # Specify that US be used for this specific report
        self.config_dict['StdReport']['SeasonsReport']['unit_system'] = 'us'
        # But override the default unit to be used for pressure
        self.config_dict['StdReport']['Defaults'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # Because the override for the specific report has precedence,
        # the units should be unchanged.
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'inHg')

    def test_override_unit_system_in_report_and_unit_in_defaults(self):
        """Test a default unit system, versus overriding a unit for a specific report.
        This is basically the inverse of the above."""
        # Specify that US be used as a default
        self.config_dict['StdReport']['Defaults']['unit_system'] = 'us'
        # But override the default unit to be used for pressure for a specific report
        self.config_dict['StdReport']['SeasonsReport'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # The override for the specific report should take precedence.
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_defaults_lang(self):
        """Test adding a lang spec to a report"""
        # Specify that the default language is German
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # That should change the unit system, as well as make translation texts available.
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'mm')
        self.assertEqual(skin_dict['Units']['Labels']['day'], [" Tag", " Tage"])

    def test_report_lang(self):
        """Test adding a lang spec to a specific report"""
        # Specify that the default should be French...
        self.config_dict['StdReport']['Defaults']['lang'] = 'fr'
        # ... but ask for German for this report.
        self.config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # The results should reflect German
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'mm')
        self.assertEqual(skin_dict['Units']['Labels']['day'], [" Tag", " Tage"])

    def test_override_lang(self):
        """Test using a language spec in Defaults, as well as overriding a label."""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        self.config_dict['StdReport']['Defaults'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'foo')

    def test_override_lang2(self):
        """Test using a language spec in Defaults, then override for a specific report"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        self.config_dict['StdReport']['SeasonsReport'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'foo')

    def test_override_lang3(self):
        """Test using a language spec in a report, then override a label in Defaults."""
        self.config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
        self.config_dict['StdReport']['Defaults'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # Because the override for the specific report has precedence, we should stay with German.
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'Raumtemperatur')

    def test_lang_override_unit_system_defaults(self):
        """Specifying a language can specify a unit system. Test overriding it.
        Test [[Defaults]]"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        self.config_dict['StdReport']['Defaults']['unit_system'] = 'metric'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # The unit_system override should win. NB: 'metric' uses cm for rain. 'metricwx' uses mm.
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'cm')

    def test_lang_override_unit_system_report(self):
        """Specifying a language can specify a unit system. Test overriding it.
        Test a specific report"""
        self.config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
        self.config_dict['StdReport']['SeasonsReport']['unit_system'] = 'metric'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        # The unit_system override should win. NB: 'metric' uses cm for rain. 'metricwx' uses mm.
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'cm')

    def test_override_root(self):
        self.config_dict['StdReport']['SeasonsReport']['SKIN_ROOT'] = 'alt_skins'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['SKIN_ROOT'], 'alt_skins')

    def test_default_log_specs(self):
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertTrue(skin_dict['log_success'])

    def test_override_defaults_log_specs(self):
        self.config_dict['StdReport']['Defaults']['log_success'] = False
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertFalse(skin_dict['log_success'])

    def test_override_report_log_specs(self):
        self.config_dict['StdReport']['log_success'] = False
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertFalse(skin_dict['log_success'])

    def test_global_override_log_specs(self):
        self.config_dict['log_success'] = False
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertFalse(skin_dict['log_success'])


if __name__ == '__main__':
    unittest.main()
