#
#    Copyright (c) 2021-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test algorithms in the Report Engine"""

import logging
from pathlib import Path

import pytest

import weeutil.config
import weeutil.logger
import weeutil.weeutil
import weewx
from weewx.reportengine import build_skin_dict

log = logging.getLogger(__name__)
weewx.debug = 1

# Find where the skins are stored. Unfortunately, the following strategy won't work if the
# resources are stored as a zip file. But, the alternative is too messy. After all, this is just
# for testing.
with weeutil.weeutil.get_resource_path('weewx_data', 'skins') as skin_resource:
    SKIN_DIR = skin_resource

CONFIG_DICT_INI = f"""
WEEWX_ROOT = '../../..'

[StdReport]
    SKIN_ROOT = {SKIN_DIR}
    [[SeasonsReport]]
        skin = Seasons
    [[Defaults]]
"""
# Find WEEWX_ROOT by working up from this file's location:
CONFIG_DICT = weeutil.config.config_from_str(CONFIG_DICT_INI)
CONFIG_DICT['WEEWX_ROOT'] = str(Path(__file__).resolve().parents[3])

weeutil.logger.setup('weetest_reportengine', CONFIG_DICT)


@pytest.fixture
def config_dict():
    return weeutil.config.deep_copy(CONFIG_DICT)

def test_default(config_dict):
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Units']['Groups']['group_pressure'] == 'inHg'
    assert skin_dict['Units']['Labels']['day'] == [" day", " days"]
    # Without a 'lang' entry, there should not be a 'Texts' section:
    assert 'Texts' not in skin_dict

def test_defaults_with_defaults_override(config_dict):
    """Test override in [[Defaults]]"""
    # Override the units to be used for group pressure
    config_dict['StdReport']['Defaults'].update(
        {'Units': {'Groups': {'group_pressure': 'mbar'}}})
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Units']['Groups']['group_pressure'] == 'mbar'

def test_defaults_with_reports_override(config_dict):
    """Test override for a specific report"""
    # Override the units to be used for group pressure
    config_dict['StdReport']['SeasonsReport'].update(
        {'Units': {'Groups': {'group_pressure': 'mbar'}}})
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Units']['Groups']['group_pressure'] == 'mbar'

def test_override_unit_system_in_defaults(config_dict):
    """Test specifying a unit system in [[Defaults]]"""
    # Specify that metric be used by default
    config_dict['StdReport']['Defaults']['unit_system'] = 'metricwx'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Units']['Groups']['group_pressure'] == 'mbar'

def test_override_unit_system_in_report(config_dict):
    """Test specifying a unit system for a specific report"""
    # Specify that metric be used for this specific report
    config_dict['StdReport']['SeasonsReport']['unit_system'] = 'metricwx'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Units']['Groups']['group_pressure'] == 'mbar'

def test_override_unit_system_in_report_and_defaults(config_dict):
    """Test specifying a unit system for a specific report, versus overriding a unit
    in the [[Defaults]] section"""
    # Specify that US be used for this specific report
    config_dict['StdReport']['SeasonsReport']['unit_system'] = 'us'
    # But override the default unit to be used for pressure
    config_dict['StdReport']['Defaults'].update(
        {'Units': {'Groups': {'group_pressure': 'mbar'}}})
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # Because the override for the specific report has precedence,
    # the units should be unchanged.
    assert skin_dict['Units']['Groups']['group_pressure'] == 'inHg'

def test_override_unit_system_in_report_and_unit_in_defaults(config_dict):
    """Test a default unit system, versus overriding a unit for a specific report.
    This is basically the inverse of the above."""
    # Specify that US be used as a default
    config_dict['StdReport']['Defaults']['unit_system'] = 'us'
    # But override the default unit to be used for pressure for a specific report
    config_dict['StdReport']['SeasonsReport'].update(
        {'Units': {'Groups': {'group_pressure': 'mbar'}}})
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # The override for the specific report should take precedence.
    assert skin_dict['Units']['Groups']['group_pressure'] == 'mbar'

def test_defaults_lang(config_dict):
    """Test adding a lang spec to a report"""
    # Specify that the default language is German
    config_dict['StdReport']['Defaults']['lang'] = 'de'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # That should change the unit system, as well as make translation texts available.
    assert skin_dict['Units']['Groups']['group_rain'] == 'mm'
    assert skin_dict['Units']['Labels']['day'] == [" Tag", " Tage"]

def test_report_lang(config_dict):
    """Test adding a lang spec to a specific report"""
    # Specify that the default should be French...
    config_dict['StdReport']['Defaults']['lang'] = 'fr'
    # ... but ask for German for this report.
    config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # The results should reflect German
    assert skin_dict['Units']['Groups']['group_rain'] == 'mm'
    assert skin_dict['Units']['Labels']['day'] == [" Tag", " Tage"]

def test_override_lang(config_dict):
    """Test using a language spec in Defaults, as well as overriding a label."""
    config_dict['StdReport']['Defaults']['lang'] = 'de'
    config_dict['StdReport']['Defaults'].update(
        {'Labels': {'Generic': {'inTemp': 'foo'}}}
    )
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Labels']['Generic']['inTemp'] == 'foo'

def test_override_lang2(config_dict):
    """Test using a language spec in Defaults, then override for a specific report"""
    config_dict['StdReport']['Defaults']['lang'] = 'de'
    config_dict['StdReport']['SeasonsReport'].update(
        {'Labels': {'Generic': {'inTemp': 'foo'}}}
    )
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['Labels']['Generic']['inTemp'] == 'foo'

def test_override_lang3(config_dict):
    """Test using a language spec in a report, then override a label in Defaults."""
    config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
    config_dict['StdReport']['Defaults'].update(
        {'Labels': {'Generic': {'inTemp': 'foo'}}}
    )
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # Because the override for the specific report has precedence, we should stay with German.
    assert skin_dict['Labels']['Generic']['inTemp'] == 'Raumtemperatur'

def test_lang_override_unit_system_defaults(config_dict):
    """Specifying a language can specify a unit system. Test overriding it.
    Test [[Defaults]]"""
    config_dict['StdReport']['Defaults']['lang'] = 'de'
    config_dict['StdReport']['Defaults']['unit_system'] = 'metric'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # The unit_system override should win. NB: 'metric' uses cm for rain. 'metricwx' uses mm.
    assert skin_dict['Units']['Groups']['group_rain'] == 'cm'

def test_lang_override_unit_system_report(config_dict):
    """Specifying a language can specify a unit system. Test overriding it.
    Test a specific report"""
    config_dict['StdReport']['SeasonsReport']['lang'] = 'de'
    config_dict['StdReport']['SeasonsReport']['unit_system'] = 'metric'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    # The unit_system override should win. NB: 'metric' uses cm for rain. 'metricwx' uses mm.
    assert skin_dict['Units']['Groups']['group_rain'] == 'cm'

def test_override_root(config_dict):
    config_dict['StdReport']['SeasonsReport']['SKIN_ROOT'] = 'alt_skins'
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['SKIN_ROOT'] == 'alt_skins'

def test_default_log_specs(config_dict):
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert skin_dict['log_success']

def test_override_defaults_log_specs(config_dict):
    config_dict['StdReport']['Defaults']['log_success'] = False
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert not skin_dict['log_success']

def test_override_report_log_specs(config_dict):
    config_dict['StdReport']['log_success'] = False
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert not skin_dict['log_success']

def test_global_override_log_specs(config_dict):
    config_dict['log_success'] = False
    skin_dict = build_skin_dict(config_dict, 'SeasonsReport')
    assert not skin_dict['log_success']
