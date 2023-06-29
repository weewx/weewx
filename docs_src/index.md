# Introduction

The WeeWX weather system is written in Python and runs on Linux, MacOSX,
Solaris, and *BSD.  It collects data from many different types of weather
stations and sensors, then generates plots, HTML pages, and monthly and
yearly summary reports. It can push plots, pages, and reports to a web
server, and data data to many different online weather services.

See the [hardware list](https://weewx.com/hardware.html) for a complete list
of supported stations, and for pictures to help identify your hardware!  The
[hardware comparison](https://weewx.com/hwcmp.html) shows specifications for
many different types of hardware, including some not yet supported by WeeWX.

The WeeWX distribution includes drivers for many types of hardware.  These
are listed in the [hardware guide](../hardware/drivers). If your hardware
is not in the core driver list, you should first install WeeWX, then download
and install the driver for your hardware.

See the [WeeWX Wiki](https://github.com/weewx/weewx/wiki) for drivers and
other extensions. After you install WeeWX, use the `weectl` utility to
download and install drivers or other extensions listed in the wiki.


## Documentation

WeeWX includes extensive documentation, and the WeeWX developers work hard to
keep it relevant and up to date.  If you have questions, please consult the
documentation first.

### Quickstart
* [Debian](quickstarts/debian) - including Ubuntu, Mint, Raspberry Pi OS, Devuan
* [Redhat](quickstarts/redhat) - including Fedora, CentOS, Rocky
* [SUSE](quickstarts/suse) - including openSUSE
* [pip](quickstarts/pip) - any operating system
* [run from source](quickstarts/git) - any operating system

### All about WeeWX
* [User guide](usersguide) - installation, getting started, troubleshooting
* [Customization guide](custom) - reports, plots, localization, formatting, extensions
* [Utilities](utilities) - tools to manage stations, reports, and data
* [Hardware guide](hardware) - how to configure hardware, features of supported hardware
* [Notes for developers](devnotes) - things you should know if you write drivers or skins
* [Upgrade guide](upgrading) - detailed changes in each release


## Support

Please first try to solve any problems yourself by reading the documentation.
If that fails, check the answers to frequently-asked questions, browse the
latest guides and software in the WeeWX Wiki, or post a question to the WeeWX
user group.


### FAQ

The Frequently Asked Questions (FAQ) is contributed by WeeWX users.  It
contains pointers to more information for problems and questions most
frequently asked in the WeeWX forums.

https://github.com/weewx/weewx/wiki/WeeWX-Frequently-Asked-Questions


### Wiki

The wiki content is contributed by WeeWX users. It contains suggestions and
experiences with different types of hardware, skins, extensions to WeeWX,
and other useful tips and tricks.

https://github.com/weewx/weewx/wiki


### Forums

[weewx-user](https://groups.google.com/group/weewx-user) is for general
issues such as installation, sharing skins and templates, reporting
unexpected behavior, and suggestions for improvement.

[weewx-development](https://groups.google.com/group/weewx-development) is
for discussions about developing drivers, extensions, or working on the core
code.


## Licensing and Copyright

WeeWX is licensed under the GNU Public License v3.

© [Copyright](copyright) 2009-2023 Thomas Keffer, Matthew Wall, and Gary
Roderick
