# V5.0 "To Do"

## startup

- tk before logger is initialized, output to stdout/stderr as appropriate
- tk Rationalize startup procedure, making it consistent.

- mw make weewx-multi work on any sysv os (remove lsb dependencies)

- log reports that user dir is /etc/weewx/bin but the user dir is actuall
    /etc/weewx/bin/user not /etc/weewx/bin


## deb/rpm installs

- mw verify upgrade behavior for v4 running as root.root - ensure that v5
   runs as root.root (check the user in systemd unit)

- ensure that 'systemctl disable weewx' will also disable any template units
    that might have been created by system administrator

- on debian, an upgrade from 4.10.2 to 5.0.0rc1 leaves /etc/init.d/weewx in
    place (in addition to the systemd unit).  the rc script should be removed.


## Testing

- mw convert to pytest
- mw Automate the testing of install/upgrade/uninstall for each installation
    method using vagrant


## Drivers

- mw The `fousb` driver needs to be ported to Python 12.  post weewx 5.0 release


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

