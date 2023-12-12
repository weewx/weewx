# The configuration file weewx.conf

Application options are specified in a configuration file, nominally called
`weewx.conf`. This is a big text file, which holds the configuration
information about your installation of WeeWX. This includes things such as:

* The type of hardware you have.
* The name of your station.
* What kind of database to use and where is it located.
* How to recognize out-of-range observations, etc.

!!! note
    The location of the configuration file will depend on your installation
    method. For example, if you installed using pip, then the nominal location
    is `~/weewx-data/weewx.conf`. For other installation methods, the location
    depends on your operating system. See the section
    [*Where to find things*](../../usersguide/where.md).


!!! note
    There is another configuration file for presentation-specific options.
    This file is called `skin.conf`, and there is one for each skin. It is
    described in the reference guide 
    [*Skin options*](../skin-options/introduction.md).


The following sections are the definitive guide to the many configuration
options available. There are many more options than you are likely to need
&mdash; you can safely ignore most of them. The truly important ones, the
ones you are likely to have to customize for your station, are ==highlighted==.

Default values are provided for many options, meaning that if they are not
listed in the configuration file at all, WeeWX will pick sensible values. When
the documentation gives a "default value" this is what it means.


## Option hierarchy

In general, options closer to the "root" of weewx.conf are overridden by
options closer to the leaves. Here's an example:

```
log_success = false
...
[StdRESTful]
    log_success = true
    ...
    [[Wunderground]]
        log_success = false     # Wunderground will not be logged
        ...
    [[WOW]]
        log_success = true      # WOW will be logged
        ...
    [[CWOP]]
                                # CWOP will be logged (inherits from [StdRESTful])
        ...
```

In this example, at the top level, `log_success` is set to false. So, unless
set otherwise, successful operations will not be logged. However, for
`StdRESTful` operations, it is set to true, so for these services, successful
operations _will_ be logged, unless set otherwise by an individual service.
Looking at the individual services, successful operations for

* `Wunderground` will not be logged (set explicitly)
* `WOW` will be logged (set explicitly)
* `CWOP` will be logged (inherits from `StdRESTful`)

## Boolean values

The following will evaluate **True**: `true`, `True`, `yes`, `Yes`, `1`.

The following will evaluate **False**: `false`, `False`, `no`, `No`, `0`.

