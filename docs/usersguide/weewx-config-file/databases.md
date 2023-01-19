# [Databases]

This section lists actual databases. The name of each database is given in double brackets, for example, `[[archive_sqlite]]`. Each database section contains the parameters necessary to create and manage the database. The number of parameters varies depending on the type of database.

#### [[archive_sqlite]]
This definition uses the [SQLite](https://sqlite.org/) database engine to store data. SQLite is open-source, simple, lightweight, highly portable, and memory efficient. For most purposes it serves nicely.

#### database_type

Set to `SQLite` to signal that this is a SQLite database. The definitions that go with type `SQLite` are defined in section [`[DatabaseTypes] / [[SQLite]]`](../databasetypes#sqlite).

#### database_name

The path to the SQLite file relative to `SQLITE_ROOT`. Default is `weewx.sdb`.

## [[archive_mysql]]
This definition uses the MySQL database engine to store data. It is free, highly-scalable, but more complicated to administer.

#### database_type

Set to `MySQL` to signal that this is a MySQL database. The definitions that go with type `MySQL` are defined in section [`[DatabaseTypes] / [[MySQL]]`](../databasetypes#mysql).

#### database_name

The name of the database. Default is `weewx`.

