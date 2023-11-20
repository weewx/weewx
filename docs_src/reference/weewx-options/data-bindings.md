# [DataBindings]

A "data binding" associates storage characteristics with a specific database.
Each binding contains a database from the [`[Databases]`](databases.md)
section plus parameters such as schema, table name, and mechanism for
aggregating data.

## [[wx_binding]]

This is the binding normally used for weather data. A typical `[[wx_binding]]`
section looks something like this:

``` ini
[[wx_binding]]
    database = archive_sqlite
    table_name = archive
    manager = weewx.manager.DaySummaryManager
    schema = schemas.wview_extended.schema
```

What follows is more detailed information about each of the binding options.

#### database

The actual database to be used &mdash; it should match one of the sections in
[`[Databases]`](databases.md). Should you decide to use a MySQL database,
instead of the default SQLite database, this is the place to change it. See
the section [*Configuring MySQL/MariaDB*](../../usersguide/mysql-mariadb.md)
for details.

Required.

#### table_name

Internally, the archive data is stored in one, long, flat table. This is the
name of that table. Normally this does not need to be changed.

Optional. Default is `archive`.

#### manager

The name of the class to be used to manage the table.

Optional. Default is class `weewx.manager.DaySummaryManager`. This class
stores daily summaries in the database. Normally, this does not need to be
changed.

#### schema

A Python structure holding the schema to be used to initialize the database.
After initialization, it is not used.

Optional. Default is `schemas.wview_extended.schema`, which is a superset of
the schema used by the _wview_ weather system.
