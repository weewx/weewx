# V5.0 "To Do"

## startup

- tk before logger is initialized, output to stdout/stderr as appropriate
- tk Rationalize startup procedure, making it consistent.


## deb/rpm installs

- ensure that 'systemctl disable weewx' will also disable any template units
    that might have been created by system administrator


## Testing

- mw convert to pytest
- mw Automate the testing of install/upgrade/uninstall for each installation
    method using vagrant


## Drivers

- mw The `fousb` driver needs to be ported to Python 12.  post weewx 5.0 release


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

# Future

- mw make weewx-multi work on any sysv os (remove lsb dependencies)
