# weewx.conf Configuration File

## Overview

The configuration file weewx.conf is a big text file that holds the configuration information about your installation of WeeWX. This includes things such as:

* The type of hardware you have.
* The name of your station.
* What kind of database to use and where is it located.
* How to recognize out-of-range observations, etc.

[application layout table]: /userguide/installing-weewx/#Where-to-find-things

!!! note
    The location of **weewx.conf** will depend on your installation method and operating system. For example, if you used the setup.py method, then the nominal location is /home/weewx, and so your configuration file will be **/home/weewx/weewx.conf**. For other configurations, consult the [Where to Find Things][application layout table] section in 'Installing WeeWX'.


!!! note
    There is another type of configuration file, skin.conf, for presentation-specific options. It is described in the [Customization Guide](https://weewx.com/docs/customizing.htm), under the section [Reference: report options](https://weewx.com/docs/customizing.htm#report_options).


The following sections are the definitive guide to the many configuration options available in **weewx.conf**. They contain many more options than you are likely to need! — you can safely ignore most of them. The truly important ones, the ones you are likely to have to customize for your station, are ==highlighted==.

Default values are provided for many options, meaning that if they are not listed in the configuration file at all, WeeWX will pick sensible values. When the documentation below gives a "default value" this is what it means.


## Option hierarchy
In general, options closer to the "root" of weewx.conf are overridden by options closer to the leaves. Here's an example:

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

In this example, at the top level, **log_success** is set to false. So, unless set otherwise, successful operations will not be logged. However, for **StdRESTful** operations, it is set to true, so for these services, successful operations _will_ be logged, unless set otherwise by an individual service. Looking at the individual services, successful operations for

* **Wunderground** will not be logged (set explicitly)
* **WOW** will be logged (set explicitly)
* **CWOP** will be logged (inherits from **[StdRESTful]**

What follows is organized by the different sections of the configuration file.
