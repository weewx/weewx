#
#    Copyright (c) 2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

import logging
import os.path
import sys

import configobj
import pytest

import gen_fake_data
import weedb
import weeutil.logger
import weewx.manager
from parameters import synthetic_dict, alt_dict

log = logging.getLogger(__name__)

# Set up logging using the defaults.
weeutil.logger.setup('conftest')


# Run the tests twice, once with sqlite and once with mysql
@pytest.fixture(scope="session",
                params=[
                    'sqlite',
                    'mysql',
                    # 'postgresql',
                ])
def build_config(request):
    """Generate a config file set to use a particular database type
    (such as 'sqlite' or 'mysql')."""
    db_type = request.param
    if db_type == 'mysql' and os.environ.get('WEEWX_TEST_MYSQL', '1') == '0':
        pytest.skip("MySQL testing disabled via WEEWX_TEST_MYSQL=0")

    # Find the configuration file. It's assumed to be in the same directory as me:
    config_path = os.path.join(os.path.dirname(__file__), "testgen.conf")

    # Read it in
    try:
        weewx_config = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
    except IOError:
        sys.stderr.write("Unable to open configuration file %s" % config_path)
        # Reraise the exception (this will eventually cause the program to exit)
        raise
    except configobj.ConfigObjError:
        sys.stderr.write("Error while parsing configuration file %s" % config_path)
        raise

    # Patch the config file so that the two bindings use the appropriate database:
    weewx_config['DataBindings']['wx_binding']['database'] = "archive_" + db_type
    weewx_config['DataBindings']['alt_binding']['database'] = "alt_" + db_type

    yield weewx_config


@pytest.fixture
def database(build_config, tmp_path):
    """Yield connection options for a new database, removing it after each test."""
    database_name = build_config['DataBindings']['wx_binding']['database']
    db_dict = weewx.manager.get_database_dict_from_config(build_config, database_name)

    # Keep databases created by individual tests separate from the generated data.
    if db_dict['driver'] == 'weedb.sqlite':
        db_dict['database_name'] = str(tmp_path / 'archive.sdb')
    else:
        db_dict['database_name'] = 'test_weedb'

    try:
        weedb.drop(db_dict)
    except weedb.NoDatabaseError:
        pass
    try:
        yield db_dict
    finally:
        try:
            weedb.drop(db_dict)
        except weedb.NoDatabaseError:
            pass


@pytest.fixture(scope="session")
def config_dict(build_config):
    """Provisions the 'wx_binding' and 'alt_binding' databases."""
    gen_fake_data.provision_binding(build_config, 'wx_binding', synthetic_dict)
    gen_fake_data.provision_binding(build_config, 'alt_binding', alt_dict)
    yield build_config
    # This would be the place to drop the generated databases. For now, we leave them in place.
