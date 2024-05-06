## Future

- mw or tk: Look into unifying the two versions of the systemd weewx service
  files.
- mw respect the state/masking of weewx unit
- mw ensure clean migration of weewx-multi
- mw filter the units for debconf
- mw for upgrades (and new?), get HTML_ROOT from the config file to determine
   where to chown/chmod
- mw be sure to stop/start all existing weewxd processes during upgrade


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

