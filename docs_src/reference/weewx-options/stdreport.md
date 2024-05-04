# [StdReport]

This section is for configuring the `StdReport` service, which controls what
reports are to be generated. While it can be highly customized for your
individual situation, this documentation describes the section as shipped in
the standard distribution.

Each report is represented by a subsection, marked with double brackets (e.g.,
`[[MyReport]]`). Any options for the report should be placed under it. The
standard report service will go through the subsections, running each report
in order.

WeeWX ships with the following subsections:

| subsection           | Description                                                                                                                                              |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| [[SeasonsReport]]    | A full-featured single-page skin. Statistics and plots are revealed by touch or button press.                                                            |
| [[SmartphoneReport]] | A skin formatted for smaller screens, with a look-and-feel reminiscent of first-generation Apple iPhone.                                                 |
| [[MobileReport]]     | A static skin formatted for very small screens, with a look-and-feel reminiscent of WindowsCE or PalmOS.                                                 |
| [[StandardReport]]   | The original skin that shipped for many years as the default report. It uses static HTML and images, and requires few resources to generate and display. |
| [[FTP]]              | No presentation elements. Uses the reporting machinery to transfer files to a remote server using FTP.                                                   |
| [[RSYNC]]            | No presentation elements. Uses the reporting machinery to transfer files to a remote server using rsync.                                                 |

Order matters. The reports that generate HTML and images, that is,
`SeasonsReport`, `SmartphoneReport`, `MobileReport`, and `StandardReport`,
are run _first_, then the reports that move them to a webserver, `FTP` and
`RSYNC`, are run. This insures that report generation is done before the
results are sent off.

Details for how to customize reports are in the section
[*Customizing reports*](../../custom/custom-reports.md), in the
*Customization Guide*.

#### SKIN_ROOT

The directory where the skins live.

If a relative path is specified, it is relative to
[`WEEWX_ROOT`](general.md#weewx_root).

#### HTML_ROOT

The target directory for the generated files. Generated files and images wil
l be put here.

If a relative path is specified, it is relative to
[`WEEWX_ROOT`](general.md#weewx_root).

#### log_success

If you set a value for `log_success` here, it will override the value set at
the [top-level](general.md#log_success) and will apply only to reporting.
In addition, `log_success` can be set for individual reports by putting them
under the appropriate subsection (*e.g.*, under `[[Seasons]]`).

#### log_failure

If you set a value for log_failure here, it will override the value set at
the [top-level](general.md#log_failure) and will apply only to reporting.
In addition, `log_failure` can be set for individual reports by putting them
under the appropriate subsection (*e.g.*, under `[[Seasons]]`).

#### data_binding

The data source to be used for the reports. It should match a binding given
in section [`[DataBindings]`](data-bindings.md). The binding can be
overridden in individual reports. Optional. Default is `wx_binding`.

#### report_timing

This parameter uses a cron-like syntax that determines when a report will be
run. The setting can be overridden in individual reports, so it is possible
to run each report with a different schedule. Refer to the separate document
[_Scheduling report generation_](../../custom/report-scheduling.md) for how
to control when reports are run. Optional. By default, a value is missing,
which causes each report to run on each archive interval.

## Standard WeeWX reports

These are the four reports that are included in the standard distribution of
WeeWX, and which actually generate HTML files and plots. They all use US
Customary units by default (but this can be changed by setting the option
`unit_system`).

#### [[SeasonsReport]]

#### [[SmartphoneReport]]

#### [[MobileReport]]

#### [[StandardReport]]

They all have the following options in common:

#### lang

Which language to use. The value can take one of three forms:

| Example      | Meaning                                                       |
|--------------|---------------------------------------------------------------|
| `en`         | English language                                              |
| `en_GB`      | English language, country Great Britain                       |
| `en_GB.utf8` | English language, country Great Britain, locale Great Britain | 

The language part of the code is as defined in [ISO
639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes). 

This option only works with skins that have been internationalized. All skins
that ship with WeeWX have been internationalized, but only a handful of
languages are included. To see which language a skin supports, look in the
subdirectory `lang` in the skin's directory. For example, if you see a file
`fr.conf`, then the skin can be localized in French.

See the section [_Changing
languages_](../../../custom/custom-reports/#changing-languages) for more
details.

#### unit_system

Which unit system to use with the skin. Choices are `US`, `METRIC`, or
`METRICWX`. See the reference section [*Units*](../units.md) for definitions of
these unit systems. Individual units can be overridden. See the section
[*Changing unit systems*](../../custom/custom-reports.md#changing-unit-systems)
in the *Customization Guide* for more details.

#### enable

Set to `true` to enable the processing of this skin. Set to `false` to
disable. If this option is missing, `true` is assumed.

#### skin

Where to find the skin. This should be a directory under `SKIN_ROOT`.
Inside the directory should be any templates used by the skin and a skin
configuration file, `skin.conf`.

#### HTML_ROOT

If you put a value for `HTML_ROOT` here, it will override the
[value](#html_root) directly under `[StdReport]`.


## [[FTP]]

While this "report" does not actually generate anything, it uses the report
machinery to upload files from directory `HTML_ROOT` to a remote webserver.
It does an incremental update, that is, it only FTPs any files that have
changed, saving the outgoing bandwidth of your Internet connection.

#### enable

Set to `true` (the default) to enable FTP. Set to `false` to disable.

#### user

Set to the username you use for your FTP connection to your web server.
Required. No default.

#### password

Set to the password you use for your FTP connection to your web server.
Required. No default.

#### server

Set to the name of your web server (*e.g.*, `www.acme.com`). Required.
No default

#### path

Set to the path where the weather data will be stored on your webserver
(*e.g.*, `/weather`). Required. No default.

!!! Note
    Some FTP servers require a leading slash ('`/`'), some do not.

#### secure_ftp

Set to `true` to use FTP (FTPS) over TLS. This is an extension to the FTP
protocol that uses a Secure Socket Layer (SSL) protocol, not to be confused
with SFTP, which uses a Secure Socket Shell protocol. Not all FTP servers
support this. In particular, the Microsoft FTP server seems to do a poor
job of it. Optional. Default is `false`

#### secure_data

If a secure session is requested (option `secure_ftp=true`), should we attempt
a secure data connection as well? This option is useful due to a bug in the
Python FTP client library. See WeeWx GitHub
[Issue #284](https://github.com/weewx/weewx/issues/284). Optional. Default
is `true`.

#### reuse_ssl

Some FTP servers (notably PureFTP) reuse ssl connections with FTPS.
Unfortunately, the Python library has a bug that prematurely closes such
connections. See [https://bit.ly/2Lrywla](https://bit.ly/2Lrywla). Symptom is an
exception *OSError: [Errno 0]*, or a 425 error ("*425 Unable to build data
connection: Operation not permitted*"). This option activates a workaround for
Python versions greater than 3.6. It won't work for earlier versions. Optional.
Default is `false`.

#### port

Set to the port ID of your FTP server. Default is `21`.

#### passive

Set to `1` if you wish to use the more modern, FTP passive mode, `0` if you
wish to use active mode. Passive mode generally works better through firewalls,
but not all FTP servers do a good job of supporting it. See [Active FTP vs.
Passive FTP, a Definitive Explanation](https://slacksite.com/other/ftp.html)
for a good explanation of the difference. Default is `1` (passive mode).

#### max_tries

WeeWX will try up to this many times to FTP a file up to your server before
giving up. Default is `3`.

#### ftp_encoding

The vast majority of FTP servers send their responses back using UTF-8
encoding. However, there are a few oddballs that respond using Latin-1. This
option allows you to specify an alternative encoding.

#### ciphers

Some clients require a higher cipher level than the FTP server is capable of
delivering. The symptom is an error something like:

    ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh key too small (_ssl.c:997)`

This option allows you to specify a custom level. For example, in this case,
you might want to specify:

``` ini
ciphers='DEFAULT@SECLEVEL=1'
```

However, if possible, you are always better off upgrading the FTP server.


## [[RSYNC]]

While this "report" does not actually generate anything, it uses the report
machinery to upload files from directory `HTML_ROOT` to a remote webserver
using [rsync](https://rsync.samba.org/). Fast, efficient, and secure, it does
an incremental update, that is, it only synchronizes those parts of a file
that have changed, saving the outgoing bandwidth of your Internet connection.

If you wish to use rsync, you must configure passwordless ssh using
public/private key authentication from the user account that WeeWX runs, to
the user account on the remote machine where the files will be copied.

#### enable

Set to `true` (the default) to enable rsync. Set to `false` to disable.

#### server

Set to the name of your server. This name should appear in your `.ssh/config`
file. Required. No default

#### user

Set to the ssh username you use for your rsync connection to your web server.
The local user that WeeWX runs as must have [passwordless ssh](https://www.tecmint.com/ssh-passwordless-login-using-ssh-keygen-in-5-easy-steps/)
configured for _user@server_. Required. No default.

#### path

Set to the path where the weather data will be stored on your webserver
(_e.g._, `/var/www/html/weather`). Make sure `user` has write privileges in
this directory. Required. No default.

#### port

The port to use for the ssh connection. Default is to use the default port for
the `ssh` command (generally 22).

#### delete

Files that don't exist in the local report are removed from the remote
location. 

!!! warning
    USE WITH CAUTION! If you make a mistake in setting the path, this can
    cause unexpected files to be deleted on the remote server. 
    
Valid values are `1` to enable and `0` to disable. Required. Default is `0`.

#### rsync_options

Use this option to pass on any additional command line options to `rsync`. It
should be a comma separated list.  For example

```ini
    rsync_options = --exclude=*.ts, --ipv6
```

This would exclude any Typescript files from the transfer, and indicate that you
would prefer to use IPv6.


## [[Defaults]]

This section defines default values for all reports. You can set:

* The unit system to be used
* Overrides for individual units
* Which language to be used
* Number and time formats
* Labels to be used
* Calculation options for some derived values.

See the section [*Processing order*](../../custom/custom-reports.md#processing-order) in the *Customization Guide* for more details.
