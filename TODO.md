# V5.0 "To Do"

## `weectl`

Some of the routines should probably ask for a confirmation before proceeding.
For example, `weectl extension uninstall` just uninstalls without confirmation. 
- Get pre-log-initialization output to show up properly

## Package installers

- verify upgrade behavior on skin files in /etc/weewx/skins.  do the non-
    modified skin files get upgraded from apt/yum?
- the driver files have a shebang, but since they are never invoked directly
    (always 'python xxx.py' and never just 'xxx.py') then why have shebang?
    and if they do have shebang, they should be executable
- weectl should use 'weectl' as the process name. only 'weectl database' does
    this properly?

## Resolved (push these to docs and/or design doc)

- ensure that maintainer's version of weewx.conf is created but no used; ensure
    that existing weewx.conf is not overwritten
    /etc/weewx/weewx.conf - untouched config
    /etc/weewx/weewx.conf.OLD-LATEST - maintainer; 'weewctl upgrade'
    /etc/weewx/weewx.conf.LATEST - distribution

- add steps to purging.  these are for deb/rpm installs
    sudo userdel weewx
    sudo rm -rf /etc/weewx
    sudo rm -rf /var/lib/weewx
    sudo rm -rf /var/log/weewx
    sudo rm -rf /var/www/html/weewx

- verify the weewx-multi scenario using systemd
    create config files - unique: Station.location, HTML_ROOT, database_name
      /etc/weewx/XXX.conf
      /etc/weewx/YYY.conf
    enable
      sudo systemctl enable weewx@XXX
      sudo systemctl enable weewx@YYY
    start/stop
      sudo systemctl start weewx@XXX
      sudo systemctl start weewx@YYY

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

- Continue logging to system log. Unfortunately, the Python logging module is
  not process safe, so we would be unable to have multiple processes write to
  it. So, we stick with syslog.
  
- for weewx-multi, ensure that this will work:
    - make weewxd logging go to /var/log/weewx/weewxd.log
    - make weewx-sdr go to /var/log/weewx/sdr.log, etc
    - make weectl logging go to /var/log/weewx/weectl.log 
  YES. this can be handled using rsyslog.d/weewx.conf, or it can be done with
  a logging configuration in the weewx.conf for each instance.  the latter is
  somewhat dangerous, since a single config file might be use by multiple
  executables concurrently - syslog will handle that, but weewx logging will
  not.
  
* For upgrades: in the weewx config, we convert `WEEWX_ROOT=/` to
  `WEEWX_ROOT=/etc/weewx` only when the config file is explicitly upgraded
  using 'weectl station upgrade'.  The deb/rpm upgrade will *not* touch the
  config file (unless the user requests the maintainer's version).  The
  maintainer's version of the config file *will* include the change to
  WEEWX_ROOT.

Done:

- Verify that process name still works on non-systemd systems
- need to test all of this on older versions of systemd (e.g., debian 10)
- for logging, use weewx vs weewxd for log label? default to 'weewxd'
- need to set permissions for cc3000 and vantage udev devices
For new install:
* Set `WEEWX_ROOT=/etc/weewx`
* Create user+group `weewx`, then run as `weewx.weewx`
* Install the udev file with permissions set for user `weewx`
For upgrades:
* Copy contents of `/usr/share/weewx/user` to `/etc/weewx/bin/user`, then
rename `/usr/share/weewx/user` to `/usr/share/weewx/user-YYmmdd`

Punt:

- new installs default to separate log file for weewx
- For upgrades: Do not changeover to running as weewx.weewx


For the documentation:

When installing with pip, the weewx installation belongs to the user who did
the install.  When installing using apt/yum/zypper, the installation belongs
to the system, so a weewx user owns it all.

  pip - tinkerer, developer, system without apt/yum/zypper
  apt/yum/zypper - easiest install, appliance
  git(src) - developer, minimal system, multiple python configurations


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


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

