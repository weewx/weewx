# Configuring MySQL / MariaDB

This section applies only to those who wish to use the MySQL database, instead
of the default SQLite database. It assumes that you already have a working
MySQL or MariaDB server.

### 1. Install the client libraries

The Python client library for MySQL/MariaDB must be installed.  How to do this
depends on your operating system and how you installed WeeWX.

=== "Debian"
    ``` {.shell .copy}
    sudo apt install mysql-client
    sudo apt install python3-mysqldb
    ```
=== "Redhat"
    ``` {.shell .copy}
    sudo yum install MySQL-python
    ```
=== "openSUSE"
    ``` {.shell .copy}
    sudo zypper install python3-mysqlclient
    ```
=== "pip"
    The base MySQL libraries are included as part of a normal pip install. 
    However, you might want to install a standalone MySQL or MariaDB client
    to help with testing.

    If you plan to use MySQL or MariaDB with `sha256_password` or
    `caching_sha2_password` authentication, you will also need to install the
    module `cryptography`. On some operating systems this can be a bit of a
    struggle, but the following usually works. The key step is to update `pip`
    before trying the install.
    
    ```{.shell .copy}
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Make sure pip is up-to-date
    python3 -m pip install pip --upgrade
    # Install cryptography
    python3 -m pip install cryptography
    ```

### 2. Change the WeeWX configuration to use MySQL

In the WeeWX configuration file, change the
[`[[wx_binding]]`](../reference/weewx-options/data-bindings.md#wx_binding)
section to point to the MySQL database, `archive_mysql`, instead of the SQLite
database `archive_sqlite`.

After the change, it will look something like this (change ==Highlighted== ):
```ini hl_lines="3"
    [[wx_binding]]
        # The database should match one of the sections in [Databases]
        database = archive_mysql

        # The name of the table within the database
        table_name = archive

        # The class to manage the database
        manager = weewx.manager.DaySummaryManager

        # The schema defines to structure of the database contents
        schema = schemas.wview_extended.schema
```

### 3. Configure the MySQL host and credentials

Assuming that you want to use the default database configuration, the
[`[[MySQL]]`](../reference/weewx-options/database-types.md#mysql) section
should look something like this:

```ini
    [[MySQL]]
        driver = weedb.mysql
        host = localhost
        user = weewx
        password = weewx
```
    
This assumes user `weewx` has the password `weewx`. Adjust as necessary.

### 4. Configure permissions

Configure MySQL to give the necessary permissions for the database `weewx`
to whatever MySQL user you choose. Here are the necessary minimum permissions,
again assuming user `weewx` with password `weewx`. Adjust as necessary.

``` {.sql .copy}
CREATE USER 'weewx'@'localhost' IDENTIFIED BY 'weewx';
GRANT select, update, create, delete, insert, alter, drop ON weewx.* TO weewx@localhost;
```
