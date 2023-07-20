# Backup and restore

## Backup

To back up a WeeWX installation, you will need to make a copy of

 * the configuration information (`weewx.conf`),
 * skins and templates,
 * custom code and/or extensions, and
 * the WeeWX database.

It is not necessary to back up the generated images, HTML files, or NOAA reports, because WeeWX can easily regenerate them.

It is also not necessary to back up the WeeWX code, because it can be installed again. However, it doesn't hurt to do so.

!!! Note
    For a SQLite configuration, do not make the copy of the database file while in the middle of a transaction! Schedule the backup for immediately after an archive record is written, and then make sure the backup completes before the next archive record arrives. Alternatively, stop WeeWX, perform the backup, then start WeeWX.

!!! Note
    For a MySQL configuration, save a dump of the archive database.


### Pip installs

For pip installs, create a backup by saving the contents of the directory `~/weewx-data`.

### Package installs

For DEB and RPM installs, create a backup by saving the following items:

| Item                       | Location                   |
|----------------------------|----------------------------|
| Configuration and skins    | `/etc/weewx`               |
| Custom code and extensions | `/usr/share/weewx/user`    |
| Database                   | `/var/lib/weewx/weewx.sdb` |


## Restore

To restore from backup, do a fresh install of WeeWX, replace the configuration file, skins, and database with those from a backup, then start WeeWX.
