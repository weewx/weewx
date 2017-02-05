This table shows how the various MySQLdb and sqlite exceptions are mapped to a weedb exception.

|   weedb class | Sqlite class         | MySQLdb class      | MySQLdb error number | Description                     |
|:--------------|:---------------------|:-------------------|:--------------------:|:--------------------------------|
|               | *N/A*                | `OperationalError` | 2002                 | Server down                     |
|               | *N/A*                | `OperationalError` | 2005                 | Unknown host                    |
|               | *N/A*                | `OperationalError` | 1045                 | Bad or non-existent password    |
|               | *N/A*                | `OperationalError` | 1008                 | Drop non-existent database      |
|               | `OperationalError`   | `OperationalError` | 1044                 | No permission                   |
|               | *N/A*                | `OperationalError` | 1049                 | Open non-existent database      |
|               | *N/A*                | `ProgrammingError` | 1007                 | Database already exists         |
|               | `OperationalError`   | `OperationalError` | 1050                 | Table already exists            |
|               | `OperationalError`   | `ProgrammingError` | 1146                 | SELECT non-existing table       |
|               | `OperationalError`   | `OperationalError` | 1054                 | SELECT non-existent column      |
|               | *N/A*                | `ProgrammingError` | 1146                 | SELECT on non-existent database |
|               | `IntegrityError`     | `IntegrityError`   | 1062                 | Duplicate key                   |