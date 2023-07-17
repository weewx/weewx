# Installing WeeWX

## Required Skills

In the world of open-source hobbyist software, WeeWX is pretty easy to install and configure. There are not many package dependencies, the configuration is simple, and this guide includes extensive instructions. There are thousands of people who have successfully done an install. However, there is no "point-and-click" interface, so you will have to do some manual configuring.

You should have the following skills:

* The patience to read and follow this guide.
* Willingness and ability to edit a configuration file.
* Some familiarity with Linux or other Unix derivatives.
* Ability to do simple Unix tasks such as changing file permissions and running commands.

No programming experience is necessary unless you wish to extend WeeWX. In
this case, you should be comfortable programming in Python.

If you get stuck, there is a very active [User's Group](https://groups.google.com/g/weewx-user) to help.


## Installation overview

This is an outline of the process to install, configure, and run WeeWX:

* Check the [hardware guide](../../hardware/drivers).  This will let you know of any features, limitations, or quirks of your hardware. If your weather station is not in the guide, you will have to download the driver after you install WeeWX.
* Install WeeWX. Use the step-by-step instructions in one of the [installation methods](#installation-methods).
* If the driver for your hardware if it is not included with WeeWX, install the driver as explained in the [installing a driver](#installing-a-driver) section.
* Configure the hardware. This involves setting things like the onboard archive interval, rain bucket size, etc. You may have to follow directions given by your hardware manufacturer, or you may be able to use the utility [wee_device](../../utilities/wee_device).
* Run WeeWX by launching the `weewxd` program, either [directly](../running-weewx/#running-directly), or as a [daemon](../running-weewx/#running-as-a-daemon).
* Customize the installation. Typically this is done by changing settings in the WeeWX [configuration file](../weewx-config-file). For example, you might want to [register your station](../weewx-config-file/stdrestful-config/#stationregistry), so it shows up on a world-wide map of WeeWX installations. To make changes to reports, see the [Customization Guide](../../custom/).


## Installation methods

There are a few different ways to install WeeWX.  There are packages available
for Debian (`apt`), Redhat (`yum`), and SUSE (`zypper`) systems, WeeWX can be
installed using the Package Installer for Python (`pip`) on any operating
system, or WeeWX can be run directly from source (e.g., using git).

The Debian, Redhat, and SUSE installers use the conventions and software
management tools for their respective operating systems; these are the fastest
and easiest way to get up and running.

The pip installer will work on any operating system; use this approach
for macOS or one of the BSDs, or if you are using an older operating system.
This is also a good approach if you plan to do a lot of customization, or if
you are developing a driver, skin, or other extension.

If you want to install WeeWX on a system with very little storage, or if you
want to experiment with code that is under development, then you may want to
run directly from the WeeWX sources.

| | apt/yum/zypper | pip | git |
|---|---|---|---|
| Operating system | Only systems based on Debian, Redhat, or SUSE | Any operating system | Any operating system |
| Installation steps | Single | Multiple | Multiple |
| Privileges required | root | Install, configure, or upgrade does not require root | Install, configure, or upgrade does not require root |
| Software location | Installs into locations that are standard for the operating system | Installs into locations that are standard for Python | No files are installed |
| Configuration location | /etc/weewx | ~/weewx-data | ~/weewx-data |
| Database location | /var/lib/weewx | ~/weewx-data | ~/weewx-data |
| Report location | /var/www/html/weewx | ~/weewx-data | ~/weewx-data |
| Log location | syslog | syslog | syslog |

The quick start guides contain installation instructions for each method:

* [Debian](../../quickstarts/debian) - including Ubuntu, Mint, Raspberry Pi OS, Devuan
* [Redhat](../../quickstarts/redhat) - including Fedora, CentOS, Rocky
* [SUSE](../../quickstarts/suse) - including openSUSE
* [pip](../../quickstarts/pip) - any operating system
* [git](../../quickstarts/git) - any operating system


## Installing a driver

If your hardware requires a driver that is not included with WeeWX, use the
WeeWX extension management utility to download and install the driver.

First locate the driver for your hardware - start by looking in the drivers section of the [WeeWX Wiki](https://github.com/weewx/weewx/wiki#drivers). You will need the URL for the driver release (a `zip` or `tgz` file).

Then install the driver, using the driver's URL:
```
weectl extension install https://github.com/path/to/driver.zip
```

Finally, reconfigure WeeWX to use the driver:
```
weectl station reconfigure
```

See the [extension utility](../../utilities/weectl-extension) for details.
