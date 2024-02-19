## Future

- mw or tk: Look into unifying the two versions of the systemd weewx service
  files.
- mw for upgrades (and new?), get HTML_ROOT from the config file to determine
   where to chown/chmod
- mw respect the state/masking of weewx unit
- mw ensure clean migration of weewx-multi
- mw be sure to stop/start all existing weewxd processes during upgrade
- mw respect presets?
- mw 'systemctl enable weewx@ a b c'
- mw remove nologin from weewx user account so that 'su weewx' is possible
- mw emit user/group in weewx startup log message


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

