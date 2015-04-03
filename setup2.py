import os.path
import sys

from distutils.core import setup
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
          cmdclass = {"sdist" : weewx_sdist},
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
          py_modules=['daemon'],
          scripts=['bin/wee_config_database',
                   'bin/wee_config_device',
                   'bin/weewxd',
                   'bin/wee_reports'],
          )
