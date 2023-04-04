# Installing WeeWX

## Required Skills

In the world of open-source hobbyist software, WeeWX is pretty easy to install and configure. There are not many package dependencies, the configuration is simple, and this guide includes extensive instructions. There are thousands of people who have successfully done an install. However, there is no "point-and-click" interface, so you will have to do some manual configuring.

You should have the following skills:

* The patience to read and follow this guide.
* Willingness and ability to edit a configuration file.
* Some familiarity with Linux or other Unix derivatives.
* Ability to do simple Unix tasks such as changing file permissions and running commands.

No programming experience is necessary unless you wish to extend WeeWX. In this case, you should be comfortable programming in Python.
If you get stuck, there is a very active [User's Group](https://groups.google.com/g/weewx-user) to help.


## Installation overview
This is an outline of the process to install, configure, and run WeeWX:

* Read the [hardware notes](../hardware.htm) for your weather station. This will let you know of any features, limitations, or quirks of your hardware.
* Install WeeWX. Use the step-by-step instructions in one of the [installation methods](#installation-methods) below.
* Configure the hardware. This involves setting things like the onboard archive interval, rain bucket size, etc. You may have to follow directions given by your hardware manufacturer, or you may be able to use the utility [wee_device](../../utilities/utilities.htm#wee_device_utility).
* Launch the `weewxd` program, either [directly from the command line](../running-weewx/#running-directly), or as a [daemon](../running-weewx/#running-as-a-daemon).
* Tune the installation. Typically this is done by changing settings in the WeeWX configuration file. For example, you might want to [register your station](../weewx-config-file/stdrestful-config/#stationregistry), so it shows up on a world-wide map of WeeWX installations.
* [Customize](../../custom/) the installation. This is an advanced topic, which allows you to shape WeeWX exactly to your liking!



## Installation methods

There are two general ways of installing WeeWX: using a package installer, or by using pip.

### Package installers

This is the recommended method for beginners.

- One-step install. When done, WeeWX is up and running.
- Requires root privileges to install.
- Requires root privileges to modify.
- Installs in operating system "standard locations."

Quick guides for common operating systems:

[Debian-based systems](../quickstarts/debian.md) : For Debian, Ubuntu, Mint, and Raspberry Pi OS operating systems.

[Red Hat-based RPM systems](../quickstarts/redhat.md): For Red Hat, CentOS, Fedora operating systems.

[SuSE-based RPM systems](../quickstarts/suse.md): For SuSE and OpenSUSE.

### Installing using pip

Best for those who intend to customize their system.

- Supports most operating systems, including macOS.
- Multi-step install.
- Does not require root privileges to install or modify. 
- Requires root privileges to set up a daemon.
- Installs in "standard locations" for a Python application.
- All user state is held in one location, making backups easy.

For instructions, see [*Installation using pip*](../quickstarts/pip.md).

