## 5.0.1

- mw doing 'apt purge weewx' does the right thing if your first install was
    v5.  but if your first install was v4, then doing a purge will destroy
    the skins.  this is probably because the skins were declared as conffiles
    in v4.  is there a way to remove that in v5 so that v5 'fixes' the confness
    of skins?

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

