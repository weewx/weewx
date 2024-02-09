## Future

- mw how to provide output from redhat sriptlets without adding noise to yum
    or dnf output?
- mw or tk: Look into unifying the two versions of the systemd weewx service
  files.
- mw ensure that maintainer scripts use a known working python, not just what
    might be defined in /usr/bin/weectl

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

- mw implement weewx-multi that works on any SysV init (no lsb dependencies)

