This table shows how the various MySQLdb and sqlite exceptions are mapped to a weedb exception.

|   weedb class | Sqlite class | MySQLdb class      | MySQLdb error number | Description                     |
|--------------:|--------------|--------------------|----------------------|---------------------------------|
| CannotConnect |              | `OperationalError` | 2002                 | Server down                     |
| CannotConnect |              | `OperationalError` | 2005                 | Unknown host                    |
|               |              | `OperationalError` | 1045                 | Bad or non-existent password    |
|               |              | `OperationalError` | 1008                 | Drop non-existent database      |
|               |              | `OperationalError` | 1044                 | No permission                   |
|               |              | `OperationalError` | 1049                 | Open non-existent database      |
|               |              | `OperationalError` | 1050                 | Table already exists            |
|               |              | `OperationalError` | 1054                 | Select non-existent column      |
|               |              | `ProgrammingError` | 1007                 | Database already exists         |
|               |              | `ProgrammingError` | 1146                 | Select on non-existent database |
|               |              | `IntegrityError`   | 1062                 | Duplicate key                   |