#
#    Copyright (c) 2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test algorithms in the Report Engine"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement

import logging
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
CONFIG_DICT = weeutil.config.config_from_str(CONFIG_DICT_INI)

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
        # import json
        # print(json.dumps(skin_dict, indent=2))

    def test_defaults_with_defaults_override(self):
        """Test override in [[Defaults]]"""
        # Override the units to be used for group pressure
        self.config_dict['StdReport']['Defaults'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_unit_system_override(self):
        """Test conflicting unit override"""
        # Specify that US be used for this report
        self.config_dict['StdReport']['SeasonsReport']['unit_system'] = 'us'
        # But override the default unit to be used for pressure
        self.config_dict['StdReport']['Defaults'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_defaults_with_reports_override(self):
        """Test override in [[SeasonsReport]]"""
        # Override the units to be used for group pressure
        self.config_dict['StdReport']['Defaults'].update(
            {'Units': {'Groups': {'group_pressure': 'mmHg'}}})
        # Override again for the report SeasonsReport
        self.config_dict['StdReport']['SeasonsReport'].update(
            {'Units': {'Groups': {'group_pressure': 'mbar'}}})
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_pressure'], 'mbar')

    def test_defaults_lang(self):
        """Test adding a lang spec to a report"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'mm')
        self.assertEqual(skin_dict['Units']['Labels']['day'], [" Tag", " Tage"])
        self.assertEqual(skin_dict['Texts']['Language'], "Deutsch")

    def test_report_lang(self):
        """Test adding a lang spec to a report"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'fr'
        self.config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Units']['Groups']['group_rain'], 'mm')
        self.assertEqual(skin_dict['Units']['Labels']['day'], [" Tag", " Tage"])
        self.assertEqual(skin_dict['Texts']['Language'], "Deutsch")

    def test_override_lang(self):
        """Test using a language spec in Defaults, then override in Defaults"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        self.config_dict['StdReport']['Defaults'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'foo')

    def test_override_lang2(self):
        """Test using a language spec in Defaults, then override in a report"""
        self.config_dict['StdReport']['Defaults']['lang'] = 'de'
        self.config_dict['StdReport']['SeasonsReport'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'foo')

    def test_override_lang3(self):
        """Test using a language spec in a report, then override in Defaults."""
        self.config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
        self.config_dict['StdReport']['Defaults'].update(
            {'Labels': {'Generic': {'inTemp': 'foo'}}}
        )
        skin_dict = _build_skin_dict(self.config_dict, 'SeasonsReport')
        self.assertEqual(skin_dict['Labels']['Generic']['inTemp'], 'foo')


if __name__ == '__main__':
    unittest.main()
