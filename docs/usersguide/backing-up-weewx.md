# Backup and restore

To back up a WeeWX installation, you will need to make a copy of

 * The configuration information (`weewx.conf`);
 * skins and templates;
 * any custom code or extensions you have installed; and
 * the WeeWX database.

It is not necessary to back up the generated images, HTML files, or NOAA reports, because WeeWX can easily regenerate them.

It is also not necessary to back up the WeeWX code, because it can be installed again. However,
it doesn't hurt to do so.

!!! Note
    Do not make the copy of the SQLite database while in the middle of a transaction! Schedule the backup for immediately after an archive record is written, and then make sure the backup completes before the next archive record arrives. Alternatively, stop WeeWX, perform the backup, then restart WeeWX.

For a MySQL configuration, save a dump of the archive database.


## Pip installs

For pip installs, simply back up the directory `~/weewx-data`.

## Package installs

For package installs, save the following items:

| Item                       | Where                      |
|----------------------------|----------------------------|
| User data and skins        | `/etc/weewx`               |
| Custom code and extensions | `/usr/share/weewx/user`    |
| Database                   | `/var/lib/weewx/weewx.sdb` |


# Restoring from backup
To restore from backup, do a fresh install of WeeWX, replace the default files with those from a backup, then start WeeWX.