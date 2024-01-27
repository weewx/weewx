## 5.0.1

- mw using 'sudo weectl' on a deb/rpm install breaks permissions.  new files
    are owned by root:root instead of weewx:weewx.  also problem when updating
    the database?

    here are options:

    a) sudo as weewx for each weectl
    sudo -u weewx weectl ...
    requires sudo.  requires sudoers.d/$USER with NOPASSWD

    b) do operation as someone in weewx group
    weectl ...
    must do this once:
    sudo usermod -a -G weewx $USER
    but what if installed as root?
    also ensure 2775 on directories (does it always work for root?)

    c) login as weewx user before weectl
    su -u weewx       # requires passwd for weewx
    sudo su weewx     # uses user's passwd, but requires sudo
    weectl ...

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

