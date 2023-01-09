# [Databases]

This section lists actual databases. The name of each database is given in double brackets, for example, **[[archive_sqlite]]**. Each database section contains the parameters necessary to create and manage the database. The number of parameters varies depending on the type of database.

**[[archive_sqlite]]**
This definition uses the [SQLite](https://sqlite.org/) database engine to store data. SQLite is open-source, simple, lightweight, highly portable, and memory efficient. For most purposes it serves nicely.

**database_type**

Set to **SQLite** to signal that this is a SQLite database.

**database_name**

The path to the SQLite file relative to the **SQLITE_ROOT** option. Default is **weewx.sdb**.

## [[archive_mysql]]
This definition uses the MySQL database engine to store data. It is free, highly-scalable, but more complicated to administer.

**database_type**

Set to **MySQL** to signal that this is a MySQL database.

**database_name**

The name of the database. Default is weewx. Required.

# [DatabaseTypes]

This section defines defaults for the various kinds of databases.

## [[SQLite]]
This section defines default values for SQLite databases. They can be overridden by individual databases.

**driver**

The sqlite driver name. Required.

**SQLITE_ROOT**

The location of the directory holding the SQLite databases. For **setup.py** installations, the default is the** WEEWX_ROOT/archive** directory. For DEB or RPM installations, it is **/var/lib/weewx**.

**timeout**

When the database is accessed by multiple threads and one of those threads modifies the database, the SQLite database is locked until that transaction is completed. The timeout option specifies how long other threads should wait for the lock to go away before raising an exception. The default is 5 seconds.

**isolation_level**

Set the current isolation level. See the pysqlite documentation on [isolation levels](https://docs.python.org/2.7/library/sqlite3.html#sqlite3.Connection.isolation_level) for more information. There is no reason to change this, but it is here for completeness. Default is **None** (autocommit).

## [[MySQL]]

This section defines default values for MySQL databases. They can be overridden by individual databases.

!!! Note 
    that if you choose the [MySQL](https://www.mysql.com/) database, it is assumed that you know how to administer it. In particular, you will have to set up a user with appropriate create and modify privileges.

**driver**

The MySQL driver name. Required.

**host**

The name of the server on which the database is located. Default is **localhost**.

**user**

The user name to be used to log into the server. Required.

**password**

The password. Required.

**port**

The port number to be used. Optional. Default is 3306.

**engine**

The type of MySQL database storage engine to be used. This should not be changed without a good reason. Default is **INNODB**.