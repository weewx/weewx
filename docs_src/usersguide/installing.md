# Installing WeeWX

## Required skills

In the world of open-source hobbyist software, WeeWX is pretty easy to install
and configure. There are not many package dependencies, the configuration is
simple, and this guide includes extensive instructions. There are thousands of
people who have successfully done an install. However, there is no
"point-and-click" interface, so you will have to do some manual configuring.

You should have the following skills:

* The patience to read and follow this guide.

* Willingness and ability to edit a configuration file.

* Some familiarity with Linux or other Unix derivatives.

* Ability to do simple Unix tasks such as changing file permissions and
  running commands.

No programming experience is necessary unless you wish to extend WeeWX. In
this case, you should be comfortable programming in Python.

If you get stuck, there is a very active
[User's Group](https://groups.google.com/g/weewx-user) to help.


## Installation overview

This is an outline of the process to install, configure, and run WeeWX:

* Check the [_Hardware guide_](../hardware/drivers.md).  This will let you
  know of any features, limitations, or quirks of your hardware. If your weather
  station is not in the guide, you will have to download the driver after you
  install WeeWX.

* Install WeeWX. Use the step-by-step instructions in one of the
  [installation methods](#installation-methods).

* If the driver for your hardware is not included with WeeWX, install the
  driver as explained in the [installing a driver](#installing-a-driver)
  section.

* Configure the hardware. This involves setting things like the onboard
  archive interval, rain bucket size, etc. You may have to follow directions
  given by your hardware manufacturer, or you may be able to use the utility
  [weectl device](../utilities/weectl-device.md).

* Run WeeWX by launching the `weewxd` program, either
  [directly](running.md#running-directly), or as a
  [daemon](running.md#running-as-a-daemon).

* Customize the installation. Typically, this is done by changing settings in
  the WeeWX [configuration file `weewx.conf`](../reference/weewx-options/introduction.md).
  For example, you might want to [register your
  station](../reference/weewx-options/stdrestful.md#stationregistry), so it
  shows up on a world-wide map of WeeWX installations. To make changes to reports,
  see the [_Customization Guide_](../custom/introduction.md).


## Installation methods

There are several different ways to install WeeWX.

<table>
  <tr><th>Installer</th><th>Systems</th><th>Best for...</th></tr>
  <tr>
    <td><a href="../../quickstarts/debian">Debian</a></td>
    <td>including Ubuntu, Mint, Raspberry Pi OS, Devuan</td>
    <td rowspan=3>
      This is the fastest and easiest way to get up and running. The Debian,
      Redhat, and SUSE package installers use <em>apt</em>, <em>yum</em>, and
      <em>zypper</em>, respectively. You will need root access to install and
      run.
    </td>
  </tr>
  <tr>
    <td><a href="../../quickstarts/redhat">Redhat</a></td>
    <td>including Fedora, CentOS, Rocky</td>
  </tr>
  <tr>
    <td><a href="../../quickstarts/suse">SUSE</a></td>
    <td>including openSUSE</td>
  </tr>
  <tr>
    <td><a href="../../quickstarts/pip">pip</a></td>
    <td>any operating system</td>
    <td>
The pip installer will work on any operating system. Use this approach for
macOS or one of the BSDs, or if you are using an older operating system. When
used in a Python "virtual environment" (recommended), this approach is least
likely to disturb other applications on your computer. This is also a good
approach if you plan to do a lot of customization, or if you are developing a
driver, skin, or other extension. Root access is not needed to install, but
may be needed to run.
    </td>
  </tr>
  <tr>
    <td><a href="../../quickstarts/git">git</a></td>
    <td>any operating system</td>
    <td>
If you want to install WeeWX on a system with very little storage, or if you
want to experiment with code that is under development, then you may want to
run directly from the WeeWX sources.  Root access is not needed to install,
but may be needed to run.
    </td>
  </tr>
</table>

## Installing a driver

If your hardware requires a driver that is not included with WeeWX, use the
WeeWX extension management utility to download and install the driver.

First locate the driver for your hardware - start by looking in the drivers
section of the [WeeWX Wiki](https://github.com/weewx/weewx/wiki#drivers). You
will need the URL for the driver release; the URL will refer to a `zip` or
`tgz` file.

Then install the driver, using the driver's URL:
```
weectl extension install https://github.com/path/to/driver.zip
```

Finally, reconfigure WeeWX to use the driver:
```
weectl station reconfigure
```

See the documentation for
[`weectl extension`](../utilities/weectl-extension.md) and
[`weectl station`](../utilities/weectl-station.md) for details.

## Installing a skin, uploader or other extension

There are many skins and other extensions available that add features and
functionality to the core WeeWX capabilities.  Use the WeeWX extension
management utility to download, install, and manage these extensions.

Start by looking in the extensions section of the
[WeeWX Wiki](https://github.com/weewx/weewx/wiki).  When you find an
extension you like, make note of the URL to that extension. The URL will refer
to a `zip` or `tgz` file.

Then install the extension, using the URL:
```
weectl extension install https://github.com/path/to/extension.zip
```

Some extensions work with no further changes required.  Others might require
changes to the WeeWX configuration file, for example, login credentials
required to upload data to an MQTT broker.  If so, modify the WeeWX
configuration file using a text editor such as `nano`, and see the
extension documentation for details.

In most cases, you will then have to restart WeeWX.

See the documentation for [`weectl
extension`](../utilities/weectl-extension.md) for details.
