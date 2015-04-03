#!/usr/bin/env python
#
#    weewx --- A simple, high-performance weather station server
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

from __future__ import with_statement

import os.path
import sys

import configobj

from distutils.core import setup
from distutils.command.install import install
from distutils.command.install_data import install_data
from distutils.command.install_lib import install_lib
from distutils.command.install_scripts import install_scripts
from distutils.command.sdist import sdist

# Find the install bin subdirectory:
this_file = os.path.join(os.getcwd(), __file__)
this_dir = os.path.abspath(os.path.dirname(this_file))
bin_dir = os.path.abspath(os.path.join(this_dir, 'bin'))

# Now that we've found the bin subdirectory, inject it into the path:
sys.path.insert(0, bin_dir)

# Now we can import some weewx modules
import weewx
VERSION = weewx.__version__
import config_util

#==============================================================================
# install
#==============================================================================

class weewx_install(install):
    # Add an option for --no-prompt:
    user_options = install.user_options + [('no-prompt', None, 'Do not prompt for info')]

    def run(self, *args, **kwargs):
        config_path = os.path.join(self.home, 'weewx.conf')
        if os.path.isfile(config_path):
            # The config file already exists. Extract the station
            # info from it
            config_dict = configobj.ConfigObj(config_path)
            stn_info = config_util.get_station_info(config_dict)
        else:
            # No old config file. Must be a new install.
            if self.no_prompt:
                # The user does not want to be bothered. Supply a minimal stn_info:
                stn_info = {'driver': 'weewx.drivers.simulator'}
            else:
                # Prompt the user for the station information:
                stn_info = config_util.prompt_for_info()
                driver = config_util.prompt_for_driver(stn_info.get('driver'))
                stn_info['driver'] = driver
                stn_info.update(config_util.prompt_for_driver_settings(driver))

        install.run(self, *args, **kwargs)

    def initialize_options(self, *args, **kwargs):
        self.no_prompt = False
        install.initialize_options(self, *args, **kwargs)


#==============================================================================
# sdist
#==============================================================================

class weewx_sdist(sdist):
    """Specialized version of sdist which checks for password information in
    the configuration file before creating the distribution.

    For other sdist methods, see:
 http://epydoc.sourceforge.net/stdlib/distutils.command.sdist.sdist-class.html
    """

    def copy_file(self, f, install_dir, **kwargs):
        """Specialized version of copy_file.

        Return a tuple (dest_name, copied): 'dest_name' is the actual name of
        the output file, and 'copied' is true if the file was copied (or would
        have been copied, if 'dry_run' true)."""
        # If this is the configuration file, then check it for passwords
        if f == 'weewx.conf':
            import configobj
            config = configobj.ConfigObj(f)

            try:
                password = config['StdReport']['FTP']['password']
                sys.exit("\n*** FTP password found in configuration file. Aborting ***\n\n")
            except KeyError:
                pass

            try:
                password = config['StdRESTful']['Wunderground']['password']
                sys.exit("\n*** Wunderground password found in configuration file. Aborting ***\n\n")
            except KeyError:
                pass

            try:
                password = config['StdRESTful']['Wunderground']['password']
                sys.exit("\n*** PWSweather password found in configuration file. Aborting ***\n\n")
            except KeyError:
                pass

        # Pass on to my superclass:
        return sdist.copy_file(self, f, install_dir, **kwargs)

#==============================================================================
# main entry point
#==============================================================================

if __name__ == "__main__":
    # Get the data to be installed from the manifest:

    # now invoke the standard python setup
    setup(name='weewx',
          version=VERSION,
          description='weather software',
          long_description="weewx interacts with a weather station to produce graphs, "
          "reports, and HTML pages.  weewx can upload data to services such as the "
          "WeatherUnderground, PWSweather.com, or CWOP.",
          author='Tom Keffer',
          author_email='tkeffer@gmail.com',
          url='http://www.weewx.com',
          license='GPLv3',
          classifiers=['Development Status :: 5 - Production/Stable',
                       'Intended Audience :: End Users/Desktop',
                       'License :: GPLv3',
                       'Operating System :: OS Independent',
                       'Programming Language :: Python',
                       'Programming Language :: Python :: 2',
                       ],
          requires=['configobj(>=4.5)',
                    'serial(>=2.3)',
                    'Cheetah(>=2.0)',
                    'sqlite3(>=2.5)',
                    'PIL(>=1.1.6)'],
          provides=['weedb',
                    'weeplot',
                    'weeutil',
                    'weewx'],
          cmdclass={"sdist" : weewx_sdist,
                      "install" : weewx_install},
#           cmdclass    = {"install_data": weewx_install_data,
#                          "install_lib": weewx_install_lib,
#                          "sdist": weewx_sdist,
#                          "install_scripts": weewx_install_scripts},
          platforms=['any'],
          package_dir={'': 'bin'},
          packages=['examples',
                    'schemas',
                    'user',
                    'weedb',
                    'weeplot',
                    'weeutil',
                    'weewx',
                    'weewx.drivers'],
          py_modules=['daemon',
                      'config_util'],
          scripts=['bin/wee_config_database',
                   'bin/wee_config_device',
                   'bin/weewxd',
                   'bin/wee_reports'],
          data_files=[
                      ('',
                       ['LICENSE.txt',
                        'README',
                        'weewx.conf']),
                      ('docs',
                       ['docs/changes.txt',
                        'docs/copyright.htm',
                        'docs/customizing.htm',
                        'docs/debian.htm',
                        'docs/readme.htm',
                        'docs/redhat.htm',
                        'docs/setup.htm',
                        'docs/suse.htm',
                        'docs/upgrading.htm',
                        'docs/usersguide.htm']),
                      ('docs/css',
                       ['docs/css/jquery.tocify.css',
                        'docs/css/weewx_docs.css']),
                      ('docs/css/ui-lightness',
                       ['docs/css/ui-lightness/jquery-ui-1.10.4.custom.css',
                        'docs/css/ui-lightness/jquery-ui-1.10.4.custom.min.css']),
                      ('docs/css/ui-lightness/images',
                       ['docs/css/ui-lightness/images/animated-overlay.gif',
                        'docs/css/ui-lightness/images/ui-bg_diagonals-thick_18_b81900_40x40.png',
                        'docs/css/ui-lightness/images/ui-bg_diagonals-thick_20_666666_40x40.png',
                        'docs/css/ui-lightness/images/ui-bg_flat_10_000000_40x100.png',
                        'docs/css/ui-lightness/images/ui-bg_glass_100_f6f6f6_1x400.png',
                        'docs/css/ui-lightness/images/ui-bg_glass_100_fdf5ce_1x400.png',
                        'docs/css/ui-lightness/images/ui-bg_glass_65_ffffff_1x400.png',
                        'docs/css/ui-lightness/images/ui-bg_gloss-wave_35_f6a828_500x100.png',
                        'docs/css/ui-lightness/images/ui-bg_highlight-soft_100_eeeeee_1x100.png',
                        'docs/css/ui-lightness/images/ui-bg_highlight-soft_75_ffe45c_1x100.png',
                        'docs/css/ui-lightness/images/ui-icons_222222_256x240.png',
                        'docs/css/ui-lightness/images/ui-icons_228ef1_256x240.png',
                        'docs/css/ui-lightness/images/ui-icons_ef8c08_256x240.png',
                        'docs/css/ui-lightness/images/ui-icons_ffd27a_256x240.png',
                        'docs/css/ui-lightness/images/ui-icons_ffffff_256x240.png']),
                      ('docs/images',
                       ['docs/images/day-gap-not-shown.png',
                        'docs/images/day-gap-showing.png',
                        'docs/images/daycompare.png',
                        'docs/images/daytemp_with_avg.png',
                        'docs/images/daywindvec.png',
                        'docs/images/ferrites.jpg',
                        'docs/images/funky_degree.png',
                        'docs/images/image_parts.png',
                        'docs/images/image_parts.xcf',
                        'docs/images/logo-apple.png',
                        'docs/images/logo-centos.png',
                        'docs/images/logo-debian.png',
                        'docs/images/logo-fedora.png',
                        'docs/images/logo-linux.png',
                        'docs/images/logo-mint.png',
                        'docs/images/logo-opensuse.png',
                        'docs/images/logo-redhat.png',
                        'docs/images/logo-suse.png',
                        'docs/images/logo-ubuntu.png',
                        'docs/images/logo-weewx.png',
                        'docs/images/sample_monthrain.png',
                        'docs/images/weekgustoverlay.png',
                        'docs/images/weektempdew.png',
                        'docs/images/yearhilow.png']),
                      ('docs/js',
                       ['docs/js/jquery-1.11.1.min.js',
                        'docs/js/jquery-ui-1.10.4.custom.min.js',
                        'docs/js/jquery.toc-1.1.4.min.js',
                        'docs/js/jquery.tocify-1.9.0.js',
                        'docs/js/jquery.tocify-1.9.0.min.js',
                        'docs/js/weewx.js']),
                      ('skins/Ftp',
                       ['skins/Ftp/skin.conf']),
                      ('skins/Rsync',
                       ['skins/Rsync/skin.conf']),
                      ('skins/Standard',
                       ['skins/Standard/favicon.ico',
                        'skins/Standard/index.html.tmpl',
                        'skins/Standard/mobile.css',
                        'skins/Standard/mobile.html.tmpl',
                        'skins/Standard/month.html.tmpl',
                        'skins/Standard/skin.conf',
                        'skins/Standard/week.html.tmpl',
                        'skins/Standard/weewx.css',
                        'skins/Standard/year.html.tmpl']),
                      ('skins/Standard/NOAA',
                       ['skins/Standard/NOAA/NOAA-YYYY-MM.txt.tmpl',
                        'skins/Standard/NOAA/NOAA-YYYY.txt.tmpl']),
                      ('skins/Standard/RSS',
                       ['skins/Standard/RSS/weewx_rss.xml.tmpl']),
                      ('skins/Standard/backgrounds',
                       ['skins/Standard/backgrounds/band.gif',
                        'skins/Standard/backgrounds/butterfly.jpg',
                        'skins/Standard/backgrounds/drops.gif',
                        'skins/Standard/backgrounds/flower.jpg',
                        'skins/Standard/backgrounds/leaf.jpg',
                        'skins/Standard/backgrounds/night.gif']),
                      ('skins/Standard/smartphone',
                       ['skins/Standard/smartphone/barometer.html.tmpl',
                        'skins/Standard/smartphone/custom.js',
                        'skins/Standard/smartphone/humidity.html.tmpl',
                        'skins/Standard/smartphone/index.html.tmpl',
                        'skins/Standard/smartphone/radar.html.tmpl',
                        'skins/Standard/smartphone/rain.html.tmpl',
                        'skins/Standard/smartphone/temp_outside.html.tmpl',
                        'skins/Standard/smartphone/wind.html.tmpl']),
                      ('skins/Standard/smartphone/icons',
                       ['skins/Standard/smartphone/icons/icon_ipad_x1.png',
                        'skins/Standard/smartphone/icons/icon_ipad_x2.png',
                        'skins/Standard/smartphone/icons/icon_iphone_x1.png',
                        'skins/Standard/smartphone/icons/icon_iphone_x2.png']),
                      ('util/apache/conf.d',
                       ['util/apache/conf.d/weewx.conf']),
                      ('util/init.d',
                       ['util/init.d/weewx.bsd',
                        'util/init.d/weewx.debian',
                        'util/init.d/weewx.lsb',
                        'util/init.d/weewx.redhat',
                        'util/init.d/weewx.suse']),
                      ('util/launchd',
                       ['util/launchd/com.weewx.weewxd.plist']),
                      ('util/logrotate.d',
                       ['util/logrotate.d/weewx']),
                      ('util/logwatch/conf/logfiles',
                       ['util/logwatch/conf/logfiles/weewx.conf']),
                      ('util/logwatch/conf/services',
                       ['util/logwatch/conf/services/weewx.conf']),
                      ('util/logwatch/scripts/services',
                       ['util/logwatch/scripts/services/weewx']),
                      ('util/rsyslog.d',
                       ['util/rsyslog.d/weewx.conf']),
                      ('util/systemd',
                       ['util/systemd/weewx.service'])
                      ]
          )
