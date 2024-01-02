# Backup and restore

## Backup

To back up a WeeWX installation, you will need to make a copy of

 * the configuration information (`weewx.conf`),
 * skins and templates,
 * custom code, and
 * the WeeWX database.

The location of these items depends on how you installed WeeWX.

=== "Debian"

    | Item          | Location                   |
    |---------------|----------------------------|
    | Configuration | `/etc/weewx/weewx.conf`    |
    | Skins         | `/etc/weewx/skins`         |
    | Custom code   | `/etc/weewx/bin/user`      |
    | Database      | `/var/lib/weewx/weewx.sdb` |

=== "Redhat"

    | Item          | Location                   |
    |---------------|----------------------------|
    | Configuration | `/etc/weewx/weewx.conf`    |
    | Skins         | `/etc/weewx/skins`         |
    | Custom code   | `/etc/weewx/bin/user`      |
    | Database      | `/var/lib/weewx/weewx.sdb` |

=== "openSUSE"

    | Item          | Location                   |
    |---------------|----------------------------|
    | Configuration | `/etc/weewx/weewx.conf`    |
    | Skins         | `/etc/weewx/skins`         |
    | Custom code   | `/etc/weewx/bin/user`      |
    | Database      | `/var/lib/weewx/weewx.sdb` |

=== "pip"

    | Item          | Location                          |
    |---------------|-----------------------------------|
    | Configuration | `~/weewx-data/weewx.conf`         |
    | Skins         | `~/weewx-data/skins`              |
    | Custom code   | `~/weewx-data/bin/user`           |
    | Database      | `~/weewx-data/archive/weewx.sdb`  |

It is not necessary to back up the generated images, HTML files, or NOAA
reports, because WeeWX can easily regenerate them.

It is also not necessary to back up the WeeWX code, because it can be
installed again. However, it doesn't hurt to do so.

!!! Note
    For a SQLite configuration, do not make the copy of the database file
    while in the middle of a transaction! Schedule the backup for immediately
    after an archive record is written, and then make sure the backup
    completes before the next archive record arrives. Alternatively, stop
    WeeWX, perform the backup, then start WeeWX.

!!! Note
    For a MySQL/MariaDB configuration, save a dump of the archive database.

## Restore

To restore from backup, do a fresh installation of WeeWX, replace the
configuration file, skins, and database with those from a backup, then start
`weewxd`.
