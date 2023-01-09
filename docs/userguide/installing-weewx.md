# Installing WeeWX

## Required Skills

In the world of open-source hobbyist software, WeeWX is pretty easy to install and configure. There are not many package dependencies, the configuration is simple, and this guide includes extensive instructions. There are thousands of people who have successfully done an install. However, there is no "point-and-click" interface, so you will have to do some manual configuring.

You should have the following skills:

* The patience to read and follow this guide.
* Willingness and ability to edit a configuration file.
* Some familiarity with Linux or other Unix derivatives.
* Ability to do simple Unix tasks such as changing file permissions and running commands.

No programming experience is necessary unless you wish to extend WeeWX. In this case, you should be comfortable programming in Python.
If you get stuck, there is a very active [User's Group](https://groups.google.com/forum/#!forum/weewx-user) to help.


## Installation Overview
This is an outline of the process to install, configure, and run WeeWX:

* Read the [hardware notes](https://weewx.com/docs/hardware.htm) for your weather station. This will let you know of any features, limitations, or quirks of your hardware.
* Install WeeWX. Use the step-by-step instructions in one of the [installation methods](index.md) below.
* Configure the hardware. This involves setting things like the onboard archive interval, rain bucket size, etc. You may have to follow directions given by your hardware manufacturer, or you may be able to use the utility [wee_device](https://weewx.com/docs/utilities.htm#wee_device_utility).
* Launch the **weewxd** program. It is run from the command line, either as a [daemon](https://weewx.com/docs/usersguide.htm#Running_as_a_daemon), or [directly](https://weewx.com/docs/usersguide.htm#Running_directly).
* Tune the installation. Typically this is done by changing settings in the WeeWX configuration file. For example, you might want to [register your station](https://weewx.com/docs/usersguide.htm#station_registry), so it shows up on a world-wide map of WeeWX installations.
* [Customize](https://weewx.com/docs/customizing.htm) the installation. This is an advanced topic, which allows you to shape WeeWX exactly to your liking!



## Installation methods
WeeWX can be installed from a DEB (Debian) or RPM (Redhat, SUSE) package, or it can be installed using the standard Python utility setup.py.

The DEB or RPM package approach is simpler and is the recommended method for beginners. However, it requires root privileges, and will install the bits and pieces of WeeWX in standard operating system locations across the file system instead of in a single directory. The net effect is that configuration files, templates, and code will all be installed in separate locations, most of which will require root privileges to modify.

Installation using **setup.py** is the recommended method for those who plan to write custom services and reports for WeeWX. It will put everything in a single directory, making it easier to modify WeeWX. If the user installing WeeWX has permission to write to the directory, root privileges will not be required to install, run, or modify WeeWX. However, root privileges might be required to communicate with hardware.

[Installing from DEB package](install-debian.md) : For Debian, Ubuntu, Mint, and Raspbian operating  systems, follow the Instructions for Debian-based Systems.


[Installing from Redhat RPM package](redhat.md): For Redhat, CentOS, Fedora operating systems, follow the the instructions for Redhat-based systems.

[Installing from SuSE RPM package](install-suse.md): For SuSE and OpenSUSE, follow the instructions for SuSE-based systems.

[Installing on MacOS](install-macos.md): For MacOS, follow the instructions for MacOS systems.

[Installing using the Python tool setup.py](install-setup-py.md): For all other operating systems, follow the setup.py instructions. This method can also be used on Debian-, Redhat-, and SUSE-based operating systems.


## Where to find things


Here is a summary of the layout for the different install methods, along with the symbolic names used for each role. These names are used throughout the documentation.

=== "Debian"
    | Role | Symbolic Name | Normal Installation Location |
    | ---- | ------------- | ---------------------------- |
    | WeeWX root directory | WEEWX_ROOT | /home/weewx/ |
    | Executables | BIN_ROOT | /home/weewx/bin/ |
    | Configuration directory | CONFIG_ROOT | /home/weewx/ |
    | Skins and templates | SKIN_ROOT | /home/weewx/skins/ |
    | SQLite databases | SQLITE_ROOT | /home/weewx/archive/ |
    | Web pages and images | HTML_ROOT | /home/weewx/public_html/ |
    | Documentation | DOC_ROOT | /home/weewx/docs/ |
    | Examples | EXAMPLE_ROOT | /home/weewx/examples/ |
    | User directory | | /home/weewx/bin/user | 
    | PID file | | /var/run/weewx.pid |
    | Log file | | /var/log/syslog |

=== "RedHat/SUSE"
    | Role | Symbolic Name | Normal Installation Location |
    | ---- | ------------- | ---------------------------- |
    | WeeWX root directory | WEEWX_ROOT | / |
    | Executables | BIN_ROOT | /usr/share/weewx/ |
    | Configuration directory | CONFIG_ROOT | /etc/weewx/ |
    | Skins and templates | SKIN_ROOT | /etc/weewx/skins/ |
    | SQLite databases | SQLITE_ROOT | /var/lib/weewx/ |
    | Web pages and images | HTML_ROOT | /var/www/html/weewx/ |
    | Documentation	| DOC_ROOT | /usr/share/doc/weewx-x.y.z/ |
    | Examples | EXAMPLE_ROOT | /usr/share/doc/weewx-x.y.z/examples/ |
    | User directory | | /usr/share/weewx/user |
    | PID file | | /var/run/weewx.pid |
    | Log file | | /var/log/messages |

=== "MacOS"
    | Role | Symbolic Name | Normal Installation Location |
    | ---- | ------------- | ---------------------------- |
    | WeeWX root directory | WEEWX_ROOT | /Users/Shared/weewx/ |
    | Executables | BIN_ROOT | /Users/Shared/weewx/bin/ |
    | Configuration directory | CONFIG_ROOT	| /Users/Shared/weewx/ |
    | Skins and templates |	SKIN_ROOT |	/Users/Shared/weewx/skins/ |
    | SQLite databases | SQLITE_ROOT | /Users/Shared/weewx/archive/ |
    | Web pages and images | HTML_ROOT | /Users/Shared/weewx/public_html/ |
    | Documentation | DOC_ROOT | /Users/Shared/weewx/docs/ |
    | Examples | EXAMPLE_ROOT |	/Users/Shared/weewx/examples/ |
    | User directory | | /Users/Shared/weewx/bin/user |
    | PID file | | /var/run/weewx.pid |
    | Log file | | /var/log/system.log |

=== "Setup.py"
    | Role | Symbolic Name | Normal Installation Location |
    | ---- | ------------- | ---------------------------- |
    | WeeWX root directory | WEEWX_ROOT | /home/weewx/ |
    | Executables |	BIN_ROOT | /home/weewx/bin/ |
    | Configuration directory |	CONFIG_ROOT | /home/weewx/ |
    | Skins and templates |	SKIN_ROOT | /home/weewx/skins/ |
    | SQLite databases | SQLITE_ROOT | /home/weewx/archive/ |
    | Web pages and images | HTML_ROOT | /home/weewx/public_html/ |
    | Documentation | DOC_ROOT | /home/weewx/docs/ |
    | Examples | EXAMPLE_ROOT |	/home/weewx/examples/ |
    | User directory | | /home/weewx/bin/user |
    | PID file | | /var/run/weewx.pid |
    | Log file | | /var/log/syslog |

