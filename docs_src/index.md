# Introduction to WeeWX

The WeeWX weather system is written in Python and runs on Linux, MacOSX,
Solaris, and *BSD. It collects data from many types of weather stations and
sensors, then generates plots, HTML pages, and monthly and yearly summary
reports. It can push plots, pages, and reports to a web server, and data to
many online weather services.

Initial development began in the winter of 2008-2009, with the first release in
2009. WeeWX is about 25,000 lines of code, plus another 15,000 for the hardware
drivers.

The source code is hosted on [GitHub](https://github.com/weewx/weewx).
Installation instructions and releases are available at
[weewx.com/downloads](http://weewx.com/downloads).

See the [hardware list](https://weewx.com/hardware.html) for a complete list
of supported stations, and for pictures to help identify your hardware!  The
[hardware comparison](https://weewx.com/hwcmp.html) shows specifications for
many types of hardware, including some not yet supported by WeeWX.

The WeeWX distribution includes drivers for many types of hardware. These
are listed in the driver list in the [Hardware Guide](hardware/drivers.md).
See the [WeeWX Wiki](https://github.com/weewx/weewx/wiki) for additional
drivers and other extensions.


## Installation

If you're an old hand at installing software on Unix systems, you may be able
to use one of our _Quickstart guides_:

* [Debian](quickstarts/debian.md) - including Ubuntu, Mint, Raspberry Pi 
  OS, Devuan. Uses `apt`.
* [Redhat](quickstarts/redhat.md) - including Fedora, CentOS, Rocky. Uses
  `yum`.
* [SUSE](quickstarts/suse.md) - including openSUSE. Uses `zypper`.
* [pip](quickstarts/pip.md) - any operating system. Uses `pip`
* [git](quickstarts/git.md) - any operating system. Run directly from
  repository.

Otherwise, see the section [_Installing WeeWX_](usersguide/installing.md) in
the _User's Guide_.

## Documentation

WeeWX includes extensive documentation, and the WeeWX developers work hard to
keep it relevant and up to date. If you have questions, please consult the
documentation first.

* [User's Guide](usersguide/introduction.md) - installation, getting started,
  where to find things, backup/restore, troubleshooting
* [Customization Guide](custom/introduction.md) - instructions for customizing
  reports and plots, localization, formatting, writing extensions
* [Utilities Guide](utilities/weewxd.md) - tools to manage stations, reports,
  and data
* [Hardware Guide](hardware/drivers.md) - how to configure hardware, features
  of supported hardware
* [Upgrade Guide](upgrade.md) - detailed changes in each release
* [Reference](reference/weewx-options/introduction.md) - application options,
  skin options, definition of units and unit systems
* [Notes for developers](devnotes.md) - things you should know if you write
  drivers or skins

## Support

Please first try to solve any problems yourself by reading the documentation.
If that fails, check the answers to frequently-asked questions, browse the
latest guides and software in the WeeWX Wiki, or post a question to the WeeWX
user group.

### FAQ

The Frequently Asked Questions (FAQ) is contributed by WeeWX users. It contains
pointers to more information for problems and questions most frequently asked
in the WeeWX forums.

https://github.com/weewx/weewx/wiki/WeeWX-Frequently-Asked-Questions

### Wiki

The wiki content is contributed by WeeWX users. It contains suggestions and
experiences with different types of hardware, skins, extensions to WeeWX, and
other useful tips and tricks.

https://github.com/weewx/weewx/wiki

### Forums

[weewx-user](https://groups.google.com/group/weewx-user) is for general issues
such as installation, sharing skins and templates, reporting unexpected
behavior, and suggestions for improvement.

[weewx-development](https://groups.google.com/group/weewx-development) is for
discussions about developing drivers, extensions, or working on the core code.

## Licensing and Copyright

WeeWX is licensed under the GNU Public License v3.

© [Copyright](copyright.md) 2009-2024 Thomas Keffer, Matthew Wall, and Gary
Roderick
