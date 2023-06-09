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
* Install WeeWX. Use the step-by-step instructions in one of the [installation methods](#installation-methods) below.
* Install the driver for your hardware if it is not included with WeeWX.
* Configure the hardware. This involves setting things like the onboard archive interval, rain bucket size, etc. You may have to follow directions given by your hardware manufacturer, or you may be able to use the utility [wee_device](../../utilities/wee_device).
* Launch the `weewxd` program, either [directly from the command line](../running-weewx/#running-directly), or as a [daemon](../running-weewx/#running-as-a-daemon).
* Tune the installation. Typically this is done by changing settings in the WeeWX configuration file. For example, you might want to [register your station](../weewx-config-file/stdrestful-config/#stationregistry), so it shows up on a world-wide map of WeeWX installations.
* [Customize](../../custom/) the installation. This is an advanced topic, which allows you to shape WeeWX exactly to your liking!


## Installation methods

There are two general ways of installing WeeWX: using a package installer, or by using pip.

### Install using a package

Installing WeeWX from a package is the fastest and simplest way to get started.

- Available only for systems based on Debian, Redhat, or SUSE
- One-step install - when install completes, WeeWX is up and running
- Requires root privileges to install and modify
- Installs into locations that are standard for the operating system
- Configuration, database, and reports are stored in different locations

These are the instructions for installing from a package:

[Debian DEB](../quickstarts/debian) : For systems based on Debian, including Ubuntu, Mint, Raspberry Pi

[Redhat RPM](../quickstarts/redhat): For systems based on Redhat, including Fedora, CentOS, and Rocky

[SuSE RPM](../quickstarts/suse): For SuSE and OpenSUSE

### Install using pip

Installing WeeWX using pip is often preferred by those who do a lot of
customization or those who develop WeeWX extensions.

- Works on every operating system, including macOS
- Multi-step install - WeeWX, data, and daemon
- Does not require root privileges to install or modify
- Requires root privileges and separate steps to run as a daemon
- Installs into locations that are standard for Python
- Configuration, database, and reports are stored in a single directory

These are the instructions for installing with pip:

[Installation using pip](../quickstarts/pip): For any operating system
