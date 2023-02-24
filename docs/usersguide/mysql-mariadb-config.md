# Configuring MySQL / MariaDB

This section applies only to those who wish to use the MySQL database, instead of the default SQLite database. It assumes that you have installed a working version of MySQL or MariaDB.

1. Install the client libraries. How to do this depends on your operating system. Use the table below as a guide.

    === "Debian | Raspbian | Ubuntu | Mint"
        ```
        sudo apt install mysql-client
        sudo apt install python3-mysqldb
        ```
    === "Redhat"
        ```
        sudo yum install MySQL-python
        ```
    === "openSUSE"
        ```
        sudo zypper install python3-mysqlclient
        ```
    === "pip"

        Nothing needs to be done: the MySQL libraries are included as part of the normal pip install.

2. Change the WeeWX configuration to use MySQL instead of SQLite. In the WeeWX configuration file, change the `[[wx_binding]]` section to point to the MySQL database, `archive_mysql`, instead of the SQLite database `archive_sqlite`.

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

3. Configure the MySQL host and credentials. Assuming that you want to use the default database configuration, the `[[MySQL]]` section should look something like this:

    ```
        [[MySQL]]
            driver = weedb.mysql
            host = localhost
            user = weewx
            password = weewx
    ```
    
    This assumes user `weewx` has the password `weewx`. Adjust as necessary.

4. Configure MySQL to give the necessary permissions for the database `weewx` to whatever MySQL user you choose. Here are the necessary minimum permissions, again assuming user `weewx` with password `weewx`. Adjust as necessary.:

    ``` sql
    mysql> CREATE USER 'weewx'@'localhost' IDENTIFIED BY 'weewx';
    mysql> GRANT select, update, create, delete, insert, alter, drop ON weewx.* TO weewx@localhost;
    ```

