# [DatabaseTypes]

This section defines default parameters for various databases.

## [[SQLite]]

This section defines default values for SQLite databases. They can be
overridden by individual databases.

#### driver

The sqlite driver name. Required.

#### SQLITE_ROOT

The location of the directory that contains the SQLite database files. If this
is a relative path, it is relative to [`WEEWX_ROOT`](general.md#weewx_root).

#### timeout

When the database is accessed by multiple threads and one of these threads
modifies the database, the SQLite database is locked until the transaction
is completed. The timeout option specifies how long other threads should wait
in seconds for the lock to go away before raising an exception.

The default is `5`.

#### isolation_level

Set the current isolation level. See the pysqlite documentation on
[isolation levels](https://docs.python.org/2.7/library/sqlite3.html#sqlite3.Connection.isolation_level)
for more information. There is no reason to change this, but it is here for
completeness.

Default is `None` (autocommit).

## [[MySQL]]

This section defines default values for MySQL databases. They can be
overridden by individual databases.

!!! Note 
    If you choose the [MySQL](https://www.mysql.com/) database, it is assumed
    that you know how to administer it. In particular, you will have to set
    up a user with appropriate create and modify privileges.

!!! Tip
    In what follows, if you wish to connect to a MySQL server using a Unix
    socket instead of a TCP/IP connection, set `host` to an empty string
    (`''`), then add an option `unix_socket` with the socket address.
    ```ini
    [[MySQL]]
        ...
        host = ''
        unix_socket = /var/run/mysqld/mysqld.sock
        ...
    ```

#### driver

The MySQL driver name. Required.

#### host

The name of the server on which the database is located.

Default is `localhost`.

#### user

The username to be used to log into the server.

Required.

#### password

The password.

Required.

#### port

The port number to be used.

Optional.

Default is `3306`.

#### engine

The type of MySQL database storage engine to be used. This should not be
changed without a good reason. Default is `INNODB`.
