This table shows how the various MySQLdb and sqlite exceptions are mapped to a weedb exception.

#weewx Version 3.6 or earlier:

| weedb class        | Sqlite class       | MySQLdb class      | MySQLdb error number | Description                     |
|--------------------|--------------------|--------------------|:--------------------:|---------------------------------|
| `OperationalError` | *N/A*              | `OperationalError` |         2002         | Server down                     |
| `OperationalError` | *N/A*              | `OperationalError` |         2005         | Unknown host                    |
| `OperationalError` | *N/A*              | `OperationalError` |         1045         | Bad or non-existent password    |
| `NoDatabase`       | *N/A*              | `OperationalError` |         1008         | Drop non-existent database      |
| `NoDatabase`       | `OperationalError` | `OperationalError` |         1044         | No permission                   |
| `OperationalError` | *N/A*              | `OperationalError` |         1049         | Open non-existent database      |
| `DatabaseExists`   | *N/A*              | `ProgrammingError` |         1007         | Database already exists         |
| `OperationalError` | `OperationalError` | `OperationalError` |         1050         | Table already exists            |
| `ProgrammingError` | *N/A*              | `ProgrammingError` |         1146         | SELECT on non-existing database |
| `ProgrammingError` | `OperationalError` | `ProgrammingError` |         1146         | SELECT non-existing table       |
| `OperationalError` | `OperationalError` | `OperationalError` |         1054         | SELECT non-existing column      |
| `IntegrityError`   | `IntegrityError`   | `IntegrityError`   |         1062         | Duplicate key                   |

###V3.6 Exception hierarchy

~~~
StandardError
|__DatabaseError
   |__IntegrityError
   |__ProgrammingError
   |__OperationalError
   |__DatabaseExists
   |__NoDatabase
~~~


#weewx Version 3.7 and later:

| weedb class           | Sqlite class       | MySQLdb class      | MySQLdb error number | Description                     |
|-----------------------|--------------------|--------------------|:--------------------:|---------------------------------|
| `CannotConnectError`  | *N/A*              | `OperationalError` |         2002         | Server down                     |
| `CannotConnectError`  | *N/A*              | `OperationalError` |         2003         | Host error                      |
| `CannotConnectError`  | *N/A*              | `OperationalError` |         2005         | Unknown host                    |
| `BadPasswordError`    | *N/A*              | `OperationalError` |         1045         | Bad or non-existent password    |
| `NoDatabaseError`     | *N/A*              | `OperationalError` |         1008         | Drop non-existent database      |
| `PermissionError`     | `OperationalError` | `OperationalError` |         1044         | No permission                   |
| `NoDatabaseError`     | *N/A*              | `OperationalError` |         1049         | Open non-existent database      |
| `DatabaseExistsError` | *N/A*              | `ProgrammingError` |         1007         | Database already exists         |
| `TableExistsError`    | `OperationalError` | `OperationalError` |         1050         | Table already exists            |
| `NoTableError`        | *N/A*              | `ProgrammingError` |         1146         | SELECT on non-existing database |
| `NoTableError`        | `OperationalError` | `ProgrammingError` |         1146         | SELECT non-existing table       |
| `NoColumnError`       | `OperationalError` | `OperationalError` |         1054         | SELECT non-existing column      |
| `IntegrityError`      | `IntegrityError`   | `IntegrityError`   |         1062         | Duplicate key                   |

###V3.7 Exception hierarchy

~~~
StandardError
|__DatabaseError
   |__IntegrityError
   |__ProgrammingError
      |__DatabaseExistsError
      |__TableExistsError
      |__NoTableError
   |__OperationalError
      |__NoDatabaseError
      |__CannotConnectError
      |__NoColumnError
      |__BadPasswordError
      |__PermissionError
~~~

