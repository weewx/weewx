# V5.0 "To Do"

## `weectl`

Some of the routines should probably ask for a confirmation before proceeding.
For example, `weectl extension uninstall` just uninstalls without confirmation. 

## Package installers

- need to test all of this on older versions of systemd (e.g., debian 10)
- Get pre-log-initialization output to show up properly
- Verify that process name still works on non-systemd systems
- need to set permissions for cc3000 and vantage udev devices
- still need --daemon, but is it correct?  see daemonize.Daemonize
- new installs default to separate log file for weewx
- verify the weewx-multi scenario using systemd
- for weewx-multi, ensure that this will work:
    - make weewxd logging go to /var/log/weewx/weewxd.log
    - make weewx-sdr go to /var/log/weewx/sdr.log, etc
    - make weectl logging go to /var/log/weewx/weectl.log 

For upgrades:
* Convert `WEEWX_ROOT=/` to`WEEWX_ROOT=/etc/weewx`
* Copy contents of `/usr/share/weewx/user` to `/etc/weewx/bin/user`, then
rename `/usr/share/weewx/user` to `/usr/share/weewx/user-YYmmdd`

Resolved:

- no need for loop-on-init arg to weewxd?
   KEEP IT

- if all logging is specified in the config file, then no need for log-label?
   only if logging is initialized *after* config file is read.  what happens
   to weewxd output before reading config file, or if there are config probs?
   STILL NEED LOG-LABEL (for syslog)

- for deb/rpm, should we use /home/weewx/weewx-data instead of /etc/weewx?
   if so, should an upgrade leave /etc/weewx in place, or move it to
   /home/weewx/weewx-data?
   NO

- for deb/rpm upgrades, if we do not change to run-as-weewx, then we need
   a mechanism to conditionally *not* change file ownership in weewx.spec
   NOT AN ISSUE - upgrade will shift all to weewx.weewx

- for logging, use weewx vs weewxd for log label?
  WEEWX

- if separate log file, we just do one: ~/weewx-data/log/weewx.log
  ONLY weewx.log

Done:

For new install:
* Set `WEEWX_ROOT=/etc/weewx`
* Create user+group `weewx`, then run as `weewx.weewx`
* Install the udev file with permissions set for user `weewx`

Punt:

For upgrades:
* Do not changeover to running as weewx.weewx


For the documentation:

When installing with pip, the weewx installation belongs to the user who did
the install.  When installing using apt/yum/zypper, the installation belongs
to the system, so a weewx user owns it all.

  pip - tinkerer, developer, system without apt/yum/zypper
  apt/yum/zypper - easiest install, appliance
  git(src) - developer, minimal system, multiple python configurations

We want /var/log/weewx so that weewx-multi will emit single log for each
weewxd instance.

We want all logs to /var/log/weewx/weewx.log so that it is clear if someone
is running weewxd and weectl at the same time.

For deb/rpm upgrades, the config file is only modified if you select the
'take maintainer changes' option.  That takes your old config and 'upgrades'
it.  (This is always a questionable thing to do, since it depends on the
'version' label, which cannot be trusted and may not even exist.  Note that
this *could* be trusted if we ensure that the uprade is based on
structure/contents, not the 'version' label.)  The 'maintainer' version of the
config file is always emitted, whether or not you choose it.


## Testing

Automate the testing of install/upgrade/uninstall for each installation
method.


## Drivers

The `fousb` driver needs to be ported to Python 12.


## Docs

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.

Need a page on how to provision a second instance, for both a pip install and a
package install.



# Before final release

## `pyproject.toml`

Change parameter `description`.

## Logging

Update the logging wiki.

Log to `~/weewx-data/weewx.log` by default. Use 
[TimedRotatingFileHandler](https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler)


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

