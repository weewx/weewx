# Making backups
To backup a WeeWX installation, you will need to make a copy of

 * configuration information
 * skins and templates
 * any custom code or extensions you have installed
 * the WeeWX database.

It is not necessary to backup the generated images, HTML files, or NOAA reports since WeeWX will easily create these again.

Individual instructions follow.


## Configuration
Save the weewx.conf file.

| Method | Location of file to backup |
| ------ | -------------------------- |
| setup.py: | /home/weewx/weewx.conf |
| DEB/RPM: | /etc/weewx/weewx.conf |

## Skins and templates

Save the contents of the skins directory if you have modified the default skin or if you have added any new skins or template files.

| Method | Location of file to backup |
| ------ | -------------------------- |
| setup.py: | /home/weewx/skins |
| DEB/RPM: | /etc/weewx/skins |

## Custom code or extensions

Save the contents of the user directory if you have modified the database schema or added any extensions. If the extensions save data to a database you should backup those databases as well.

| Method | Location of file to backup |
| ------ | -------------------------- |
| setup.py: | /home/weewx/bin/user |
| DEB/RPM: | /usr/share/weewx/user |

## Database

Finally, you will need to backup the database.  For a SQLite configuration, make a copy of the weewx.sdb file.

| Method | Location of file to backup |
| ------ | -------------------------- |
| setup.py: | /home/weewx/archive/weewx.sdb |
| DEB/RPM: | /var/lib/weewx/weewx.sdb |

!!! Note
    Do not make the copy of the SQLite database while in the middle of a transaction! Schedule the backup for immediately after an archive record is written, and then make sure the backup completes before the next archive record arrives. Alternatively, stop WeeWX, perform the backup, then restart WeeWX.

For a MySQL configuration, save a dump of the archive database.


# Restoring from backup
To restore from backup, do a fresh install of WeeWX, replace the default files with those from a backup, then start WeeWX.