# Customizing the database

For most users the database defaults will work just fine. However, there
may be occasions when you may want to add a new observation type to your
database, or change its unit system. This section shows you how to do
this.

Every relational database depends on a *schema* to specify which types
to include in the database. When a WeeWX database is first created, it
uses a Python version of the schema to initialize the database. However,
once the database has been created, the schema is read directly from the
database and the Python version is not used again &mdash; any changes to it
will have no effect. This means that the strategy for modifying the
schema depends on whether the database already exists.

## Specifying a schema for a new database

If the database does not exist yet, then you will want to pick an
appropriate starting schema. If it's not exactly what you want, you can
modify it to fit your needs before creating the database.

### Picking a starting schema

WeeWX gives you a choice of three different schemas to choose from when
creating a new database:

|  Name  | Number of<br/>observation types | Comment                                                  |
|------------------|---------------|----------------------------------------------------------|
| `schemas.wview.schema`| 49            | The original schema that came with wview.                |
| `schemas.wview_extended.schema` | 111  | A version of the wview schema,<br/>which has been extended with<br/>many new types.<br/>This is the default version. |
| `schemas.wview_small.schema` | 20            | A minimalist version of the wview schema.                |
  

For most users, the default database schema,
`schemas.wview_extended.schema`, will work just fine.

To specify which schema to use when creating a database, modify option
`schema` in section `[DataBindings]` in
`weewx.conf`. For example, suppose you wanted to use the classic
(and smaller) schema `schemas.wview.schema` instead of the
default `schemas.wview_extended.schema`. Then the section
`[DataBindings]` would look like:

``` ini hl_lines="6"
[DataBindings]
    [[wx_binding]]
        database = archive_sqlite
        table_name = archive
        manager = weewx.manager.DaySummaryManager
        schema = schemas.wview.schema
```

Now, when you start WeeWX, it will use this new choice instead of the
default.

!!! Note
    This only works when the database is *first created*. Thereafter,
    WeeWX reads the schema directly from the database. Changing this option
    will have no effect!

### Modifying a starting schema {#modify-starting-schema}

If none of the three starting schemas that come with WeeWX suits your purposes,
you can easily create your own. Just pick one of the three schemas as a
starting point, then modify it. Put the results in the `user` subdirectory,
where it will be safe from upgrades. For example, suppose you like the
`schemas.wview_small` schema, but you need to store the type `electricity`
from the example
[*Adding a second data source*](service-engine.md#add-data-source). The type
`electricity` does not appear in the schema, so you'll have to add it before
starting up WeeWX. We will call the resulting new schema
`user.myschema.schema`.

If you did a Debian install, here's how you would do this:

``` shell
 # Copy the wview_small schema over to the user subdirectory and rename it myschema:
sudo cp /usr/share/weewx/schemas/wview_small.py /etc/weewx/bin/user/myschema.py

 # Edit it using your favorite text editor
sudo nano /etc/weewx/bin/user/myschema.py
```

If you did a pip install, it can be difficult to find the starting schema
because it can be buried deep in the Python library tree. It's easier to
just download from the git repository and start with that:

``` shell
 # Download the wview_small schema and rename it to myschema.py
cd ~/weewx-data/bin/user
wget https://raw.githubusercontent.com/weewx/weewx/master/bin/schemas/wview_small.py
mv wview_small.py myschema.py

 # Edit it using your favorite text editor
nano myschema.py
```

In `myschema.py` change this:

``` tty
         ...
         ('windchill',            'REAL'),
         ('windDir',              'REAL'),
         ('windGust',             'REAL'),
         ('windGustDir',          'REAL'),
         ('windSpeed',            'REAL'),
         ]
```

to this

``` tty hl_lines="7"
         ...
         ('windchill',            'REAL'),
         ('windDir',              'REAL'),
         ('windGust',             'REAL'),
         ('windGustDir',          'REAL'),
         ('windSpeed',            'REAL'),
         ('electricity',          'REAL'),
         ]
```

The only change was the addition (==highlighted==) of `electricity` to the
list of observation names.

Now change option `schema` under `[DataBindings]` in `weewx.conf` to use
your new schema:

``` tty hl_lines="6"
[DataBindings]
    [[wx_binding]]
        database = archive_sqlite
        table_name = archive
        manager = weewx.manager.DaySummaryManager
        schema = user.myschema.schema
```

Start WeeWX. When the new database is created, it will use your modified
schema instead of the default.

!!! Note
    This will only work when the database is first created!
    Thereafter, WeeWX reads the schema directly from the database and your
    changes will have no effect!


## Modify the schema of an existing database

The previous section covers the case where you do not have an existing
database, so you modify a starting schema, then use it to initialize the
database. But, what if you already have a database, and you want to modify
its schema, perhaps by adding a column or two? Creating a new starting schema
is not going to work because it is only used when the database is first
created. Here is where the command
[`weectl database`](../utilities/weectl-database.md) can be useful.

There are two ways to do this. Both are covered below.

1.  Modify the database *in situ*. This choice works best for small changes.

2.  Reconfigure the old database to a new one while modifying it along the
    way, This choice is best for large modifications.

!!! Warning
    Before using `weectl database`, MAKE A BACKUP!

    Be sure to stop `weewxd` before making any changes to the database.

### Modify the database *in situ*

If you want to make some minor modifications to an existing database, perhaps
adding or removing a column, then this can easily be done using the command
`weectl database` with an appropriate action. We will cover the cases of
adding, removing, and renaming a type. See the documentation for [`weectl
database`](../utilities/weectl-database.md) for more details.

#### Adding a type {#add-archive-type}

Suppose you have an existing database, to which you want to add a type, such as
the type `electricity` from the example [*Adding a second data
source*](service-engine.md#add-data-source). This can be done in one easy
step using the action `weectl database add-column`:

``` shell
weectl database add-column electricity
```

The tool not only adds `electricity` to the main archive table, but also to the
daily summaries.

#### Removing a type {#remove-archive-type}

In a similar manner, the tool can remove any unneeded types from an existing
database. For example, suppose you are using the `schemas.wview` schema, but
you're pretty sure you're not going to need to store soil moisture. You can
drop the unnecessary types this way:

``` shell
weectl database drop-columns soilMoist1 soilMoist2 soilMoist3 soilMoist4 
```

Unlike the action `add-column`, the action `drop-columns` can take more than
one type. This is done in the interest of efficiency: adding new columns is
easy and fast with the SQLite database, but dropping columns requires copying
the whole database. By specifying more than one type, you can amortize the
cost over a single invocation of the utility.

!!! Warning
    Dropping types from a database means *you will lose any data
    associated with them!* The data cannot be recovered.

#### Renaming a type {#rename-archive-type}

Suppose you just want to rename a type? This can be done using the action
`rename-column`. Here's an example where you rename `soilMoist1` to
`soilMoistGarden`:

``` shell
weectl database rename-column soilMoist1 soilMoistGarden
```

Note how the action `rename-column` requires _two_ positional arguments:
the column being renamed, and its final name.

### Reconfigure database using a new schema {#reconfigure-using-new-schema}

If you are making major changes to your database, you may find it easier
to create a brand-new database using the schema you want, then transfer
all data from the old database into the new one. This approach is more
work, and takes more processing time than the *in situ* strategies
outlines above, but has the advantage that it leaves behind a record of
exactly the schema you are using.

Here is the general strategy to do this.

1.  Create a new schema that includes exactly the types that you want.

2.  Specify this schema as the starting schema for the database.

3.  Make sure you have the necessary permissions to create the new database.

4.  Use the action
    [`weectl database reconfigure`](../utilities/weectl-database.md/#reconfigure-a-database)
    to create the new database and populate it with data from the old
    database.

5.  Shuffle databases around so WeeWX will use the new database.

Here are the details:

1.  **Create a new schema.** First step is to create a new schema with
    exactly the types you want. See the instructions above [*Modify a
    starting schema*](#modify-starting-schema). As an example, suppose
    your new schema is called `user.myschema.schema`.

2.  **Set as starting schema.** Set your new schema as the starting
    schema with whatever database binding you are working with
    (generally, `wx_binding`). For example:

    ``` ini hl_lines="7"
    [DataBindings]

        [[wx_binding]]
            database = archive_sqlite
            table_name = archive
            manager = weewx.manager.DaySummaryManager
            schema = user.myschema.schema
    ```

3.  **Check permissions.** The transfer action will create a new
    database with the same name as the old, except with the suffix `_new`
    attached to the end. Make sure you have the necessary permissions to do 
    this. In particular, if you are using MySQL, you will need `CREATE`
    privileges.

4.  **Create and populate the new database.** Use the command
    `weectl database` with the `reconfigure` action.

    ``` shell
    weectl database reconfigure
    ```

    This will create a new database (nominally, `weewx.sdb_new` if you are
    using SQLite, `weewx_new` if you are using MySQL), using the schema found
    in `user.myschema.schema`, and populate it with data from the old database.

5.  **Shuffle the databases.** Now arrange things so WeeWX can find the
    new database.

    !!! Warning
        Make a backup of the data before doing any of the next steps!

    You can either shuffle the databases around so the new database has the
    same name as the old database, or edit `weewx.conf` to use the new
    database name.  To do the former:

    === "SQLite"

        ``` shell
        cd ~/weewx-data/archive
        mv weewx.sdb_new weewx.sdb
        ```

    === "MySQL"

        ``` shell
        mysql -u <username> --password=<mypassword>
        mysql> DROP DATABASE weewx;                             # Delete the old database
        mysql> CREATE DATABASE weewx;                           # Create a new one with the same name
        mysql> RENAME TABLE weewx_new.archive TO weewx.archive; # Rename to the nominal name
        ```

6.  It's worth noting that there's actually a hidden, last step:
    rebuilding the daily summaries inside the new database. This will be
    done automatically by `weewxd` at the next startup. Alternatively, it
    can be done manually using the
    [`weectl database rebuild-daily`](../utilities/weectl-database.md/) action:

    ``` shell
    weectl database rebuild-daily
    ```

## Changing the unit system in an existing database {#change-unit-system}

Normally, data are stored in the databases using US Customary units, and you
shouldn't care; it is an "implementation detail". Data can always be displayed
using any set of units you want &mdash; the section [*Changing unit
systems*](custom-reports.md#changing-unit-systems) explains how to change
the reporting units. Nevertheless, there may be special situations where you
wish to store the data in Metric units. For example, you may need to allow
direct programmatic access to the database from another piece of software that
expects metric units.

You should not change the database unit system midstream. That is, do
not start with one unit system then, some time later, switch to another.
WeeWX cannot handle databases with mixed unit systems &mdash; see the
section [`[StdConvert]`](../reference/weewx-options/stdconvert.md) in the
WeeWX User's Guide. However, you can reconfigure the database by
copying it to a new database, performing the unit conversion along the
way. You then use this new database.

The general strategy is identical to the strategy outlined above in the section
[*Reconfigure database using new schema*](#reconfigure-using-new-schema). The
only difference is that instead of specifying a new starting schema, you specify
a different database unit system. This means that instead of steps 1 and 2
above, you edit the configuration file and change option `target_unit` in
section [`[StdConvert]`](../reference/weewx-options/stdconvert.md) to reflect
your choice. For example, if you are switching to metric units, the option will
look like:

``` ini
[StdConvert]
    target_unit = METRICWX
```

After changing `target_unit`, you then go ahead with the rest of the steps.
That is run the action `weectl database reconfigure`, then shuffle the
databases.

## Rebuilding the daily summaries

The `weectl database` command can also be used to rebuild the daily
summaries:

``` shell
weectl database rebuild-daily
```

In most cases this will be sufficient; however, if anomalies remain in the
daily summaries the daily summary tables may be dropped first before
rebuilding:

``` shell
weectl database drop-daily
```

Then try again with `weectl database rebuild-daily`.
