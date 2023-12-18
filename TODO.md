# V5.0 "To Do"

## startup

- tk eliminate daemonize.py
- tk before logger is initialized, output to stdout/stderr as appropriate

## Package installers

- mw verify upgrade behavior on skin files in /etc/weewx/skins.  do the non-
    modified skin files get upgraded from apt/yum?
- mw see if backport of importlib.resources exists for suse 15 and rocky8 for
    python 3.6
- mw ensure that maintainer's version of weewx.conf is created but no used
  ensure that existing weewx.conf is not overwritten
    /etc/weewx/weewx.conf - untouched config
    /etc/weewx/weewx.conf-OLD-LATEST - maintainer; 'weewctl upgrade'
    /etc/weewx/weewx.conf-LATEST - distribution
  update the docs (each quickstart) to make this process explicit

## Resolved (push these to docs and/or design doc)

- verify the weewx-multi scenario using systemd
    configs should be XXX.conf, so log label is weewxd-XXX
      log files are /var/log/weewx/weewxd-XXX.log
      configs are /etc/weewx/XXX.conf
      database should be /var/lib/weewx/XXX.sdb
      html root should be /var/www/html/XXX/ (many variants possible here)

    create config files - unique: Station.location, HTML_ROOT, database_name
      /etc/weewx/XXX.conf
      /etc/weewx/YYY.conf
    enable
      sudo systemctl enable weewx@XXX
      sudo systemctl enable weewx@YYY
    start/stop
      sudo systemctl start weewx@XXX
      sudo systemctl start weewx@YYY

    recipe:
    emacs /etc/weewx/weewx-xxx.conf
       location
       HTML_ROOT
       database_name
    sudo systemctl enable weewx@xxx
    sudo systemctl start weewx@xxx

    when you do 'sudo systemctl stop weewx' that will also stop all template
    instances.  doing a 'start' will *not* start all template instances - you
    must start each manually, and enable each to start at system boot.

- for weewx-multi, ensure that this will work:
    - make weewxd logging go to /var/log/weewx/weewxd.log
    - make weewx-sdr go to /var/log/weewx/sdr.log, etc
    - make weectl logging go to /var/log/weewx/weectl.log 
  YES. this can be handled using rsyslog.d/weewx.conf, or it can be done with
  a logging configuration in the weewx.conf for each instance.  the latter is
  somewhat dangerous, since a single config file might be use by multiple
  executables concurrently - syslog will handle that, but weewx logging will
  not.
  
- ensure logging goes to the right place.  most important part is to use colon
    after the process name in the log string.  otherwise the process name is
    either 'python', or, on systems where systemd has hijacked the logging with
    journald, 'python' OR 'journal', depending on what tool you use to look at
    the log.  this applies only to the syslog handler.  so if you use the
    syslog handler, use the 'standard' log message format.  there is no need
    for the timestamp in the 'verbose' format if you are using syslog.

    the drivers have 'wee_' prepended to their name so that their logs are
    easily matched by syslog rules.  each of the weectl subcommands uses
    wee_XXX so that their logs can go to separate files (default behavior
    for a deb/rpm install).  all of the unit tests start with 'weetest_' for
    the same reason.

    for a pip install, everything will go to system log, but at least this way
    you can easily grep to find what you need.  and if you prefer to use the
    systemd-journald, it still works with that, without breaking standard
    syslog behavior on every other platform.

- syslog is desirable since it handles concurrent write by multiple processes.
    the weewx standalone logging will fail in this case.  syslog is also useful
    because it can feed into log aggregators such as ELK, either directly or
    via a remote logging server.  journalctl has some extra decorations if
    you need some functionality and you do not know how to use grep/awk/sed.

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

## Testing

- mw convert to pytest
- mw Automate the testing of install/upgrade/uninstall for each installation
method using vagrant


## Drivers

- mw The `fousb` driver needs to be ported to Python 12.  post weewx 5.0 release


## Docs

- tk update docs to reflect use of standalone logging
  - each quickstart page
  - where-to-find-things in users guide
  - running-weewx section of users guide



# Before final release

## `pyproject.toml`

Change parameter `description`.


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

