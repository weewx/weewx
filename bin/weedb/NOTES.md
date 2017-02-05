This table shows how the various MySQLdb and sqlite exceptions are mapped to a weedb exception.

#weewx Version 3.6 or earlier:

| weedb class        | Sqlite class       | MySQLdb class      | MySQLdb error number | Description                     |
|--------------------|--------------------|--------------------|:--------------------:|---------------------------------|
| `CannotConnect`    | *N/A*              | `OperationalError` |         2002         | Server down                     |
| `OperationalError` | *N/A*              | `OperationalError` |         2005         | Unknown host                    |
| `OperationalError` | *N/A*              | `OperationalError` |         1045         | Bad or non-existent password    |
| `NoDatabase`       | *N/A*              | `OperationalError` |         1008         | Drop non-existent database      |
| `NoDatabase`       | `OperationalError` | `OperationalError` |         1044         | No permission                   |
| `OperationalError` | *N/A*              | `OperationalError` |         1049         | Open non-existent database      |
| `DatabaseExists`   | *N/A*              | `ProgrammingError` |         1007         | Database already exists         |
| `OperationalError` | `OperationalError` | `OperationalError` |         1050         | Table already exists            |
| `ProgrammingError` | `OperationalError` | `ProgrammingError` |         1146         | SELECT non-existing table       |
| `OperationalError` | `OperationalError` | `OperationalError` |         1054         | SELECT non-existing column      |
| `ProgrammingError` | *N/A*              | `ProgrammingError` |         1146         | SELECT on non-existing database |
| `IntegrityError`   | `IntegrityError`   | `IntegrityError`   |         1062         | Duplicate key                   |

Exception hierarchy

~~~
StandardError -> weedb.DatabaseError -> weedb.IntegrityError
                                        weedb.ProgrammingError
                                        weedb.OperationalError
                                        weedb.DatabaseExists
                                        weedb.CannotConnect
                                        weedb.NoDatabase
~~~