# V5.0 "To Do"

## `weectl`

Some of the routines should probably ask for a confirmation before proceeding.
For example, `weectl extension uninstall` just uninstalls without confirmation. 

## Package installers

/var/run/weewxd.pid is not a valid default for pid, at least not systemd
specifying pid only works for root, otherwise must ensure permissions
weewx vs weewxd for log label?
Make weewxd logging go to /var/log/weewx/weewxd.log
Make weectl logging go to /var/log/weewx/weectl.log
Get pre-log-initialization output to show up properly
Verify that process name still works on non-systemd systems
Try /usr/share/weewx/user as USER_ROOT, since /etc is *not* for code

For new install:
* Set `WEEWX_ROOT=/etc/weewx`
* Create user+group `weewx`, then run as `weewx.weewx`
* Install the udev file with permissions set for user `weewx`

For upgrades:
* Convert `WEEWX_ROOT=/` to`WEEWX_ROOT=/etc/weewx`
* Copy contents of `/usr/share/weewx/user` to `/etc/weewx/bin/user`, then
rename `/usr/share/weewx/user` to `/usr/share/weewx/user-YYmmdd`
* Do not changeover to running as weewx.weewx

- if all logging is specified in the config file, then no need for log-label?
   only if logging is initialized *after* config file is read.  what happens
   to weewxd output before reading config file, or if there are config probs?
- no need for loop-on-init arg to weewxd?
- still need --daemon, but is it correct?  see daemonize.Daemonize
- should we use /home/weewx/weewx-data instead of /etc/weewx?  if so, should
   an upgrade leave /etc/weewx in place, or move it to /home/weewx/weewx-data?

when installing with pip, the weewx installation belongs to the user who did
the install.  when installing using apt/yum/zypper, the installation belongs
to the system, so a weewx user owns it all.  pip is for developer/tinkerer,
whereas apt/yum is for appliance.  git is for developer.


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

