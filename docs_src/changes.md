WeeWX change history
--------------------

### 5.1.X MM/DD/YYYY

Fix typo that causes phantom values of `soilMoist3` to appear with VantageVue
stations.

Fix bug that prevented relative paths to the config file from working.

Allow simple Python objects to be used as an argument to `$jsonize()`.

Adjust exclusion of top-level files in wheel creation to meet poetry
norms and to be consistent across poetry-core versions.  Fixes issue
[#993](https://github.com/weewx/weewx/issues/993), in part.

Fix problem that prevented cached values of first and last timestamp from
being set. [PR #999](https://github.com/weewx/weewx/pull/999). Thanks to user
Rich Bell!

Fix problem in `Standard` skin if `Select Month` was literally selected in drop
down list. [PR #1002](https://github.com/weewx/weewx/pull/1002). Thanks to user
Ben Cotton!

In the Cumulus import code, the prefix `cur_` is used to signify a current value
for most observation types. However, there was one exception: `curr_in_temp`.
The utility and documentation have been changed to use `cur_in_temp` (one
'`r`'), making all types consistent. Fixes [Issue
#1006](https://github.com/weewx/weewx/issues/1006).


### 5.1.0 07/04/2024

If option `lang` is a valid locale, then it will be used to change locale as
well as language. If it is not a valid locale, then the user's default locale
will be used. For example, if `lang=de_DE.utf8`, then the German locale will be
used. This allows locales to be set on a report-by-report basis. Addresses
issue [#867](https://github.com/weewx/weewx/issues/867).

Allow country codes to be used in addition to a language code. For example,
`zh_CN` would specify Chinese language, mainland China (Simplified Chinese),
while `zh_TW` would specify Chinese language, Taiwan (Traditional Chinese).

Added translation file for Simplified Chinese (`zh_CN.conf`). Thanks to user
Kranz!

Allow the utility `weectl import` to update old records in addition to
importing new records. PR [#930](https://github.com/weewx/weewx/issues/930).

Include the effective user and group to the log. PR
[#934](https://github.com/weewx/weewx/issues/934).

Allow extra command line options to be passed on to `rsync`. Fixes issue
[#951](https://github.com/weewx/weewx/issues/951).

Return `False` from XTypes function `has_data()` if the type cannot be
calculated. Thanks to Rich Bell! PR
[#929](https://github.com/weewx/weewx/issues/929).

Allow calculation of xtype aggregate with missing constituents.
Related to PR [#929](https://github.com/weewx/weewx/issues/929).

Fix bug in tag `$tag.obstype` where `obstype` is an XType that cannot be
calculated. Related to PR [#929](https://github.com/weewx/weewx/issues/929).

Fix bug that caused the `loop_on_init` setting in `weewx.conf` to be ignored.
PR [#935](https://github.com/weewx/weewx/issues/935).

Reinstate file `weeutil/timediff.py`. It's not used in WeeWX, but it is used
by some extensions.

Fixed bug in station config where `config_units()` would fail if there was no
`[[Defaults]]` section specified in `[StdReport]`.

Use lower-case for the product and vendor codes in udev rules. Fixes issue 
[#949](https://github.com/weewx/weewx/issues/949).

Do not make group changes if identity of user doing the install cannot be
determined. PR [#952](https://github.com/weewx/weewx/issues/952).

For deb/rpm installs, set permissions on the configuration file to be not
world-readable. PR [#948](https://github.com/weewx/weewx/issues/948).


### 5.0.2 02/10/2024

Add target `network-online.target` to the weewx systemd unit file. This
prevents `weewxd` from starting until the network is ready.


### 5.0.1 02/04/2024

Include backwards compatible reference to `weewx.UnknownType`.

Fix problem with installing extensions into installations that used V4 config
files that were installed by a package installer.

Fix problem with `weectl device` when using drivers that were installed 
using the extension installer. Fixes issue [#918](https://github.com/weewx/weewx/issues/918).

Fix problem that prevented daily summaries from being rebuilt if they had been
modified by using `weectl database drop-columns`.

Allow the use of the tilde (`~`) prefix with `--config` options.

Fix problem that prevented debug statements from being logged.

Minor corrections to the Norwegian translations. Thanks to user Aslak!
PR #919.

Change Chinese language code to `zh`. Fixes issue
[#912](https://github.com/weewx/weewx/issues/).

Fix bug in redhat/suse scriptlet that incorrectly substituted `{weewx}`
instead of `weewx` in the udev rules file.

In the redhat/suse installers, use `/var/lib/weewx` as `HOME` for user `weewx`.


### 5.0.0 01/14/2024

Python 2.7 is no longer supported. You must have Python 3.6 (introduced
December 2016) or greater.  WeeWX 5 uses the module `importlib.resources`,
which was introduced in Python 3.7. So those using Python 3.6 must install
the backport, either using the system's package manager, or pip.

WeeWX can now be installed using [pip](https://pip.pypa.io).

With pip installs, station data is stored in `~/weewx-data` by default, 
instead of `/home/weewx`. This allows pip installs to be done without
root privileges. However, `/home/weewx` can still be used.

The new utility [`weectl`](utilities/weectl-about.md) replaces `wee_database`,
`wee_debug`, `wee_device`, `wee_extension`, `wee_import`, `wee_reports`, 
and `wee_config`. Try `weectl --help` to see how to use it.

Individual reports can now be run using `weectl report run`. For example,
`weectl report run MobileReport`.

The extension installer can now install from an `http` address, not just a
file or directory.

When using `weectl database` with action `calc-missing`, the tranche size can
now be set.

Documentation now uses [MkDocs](https://www.mkdocs.org/). It is no longer
included in the distribution, but can always be accessed online at
https://weewx.com/docs.

Package installs now use `systemd` instead of the old System V `/etc/init.d`.

Allow `StdCalibrate` to operate only on LOOP packets, or only on archive
records. Addresses issue [#895](https://github.com/weewx/weewx/issues/895).

Removed all references to the deprecated package `distutils`, which is due to
be removed in Python v3.12.

Removed the utility `wunderfixer`. The Weather Underground no longer
allows posting past-dated records.

Method `ImageDraw.textsize()` and constants `ImageFont.LAYOUT_BASIC`, and
`Image.ANTIALIAS` were deprecated in Pillow 9.2 (1-Jul-2022), then removed in
Pillow 10.0 (1-Jul-2023). V5.0 replaces them with alternatives. Fixes
issue [#884](https://github.com/weewx/weewx/issues/884).

Fix bug when using Pillow v9.5.0. Fixes issue 
[#862](https://github.com/weewx/weewx/issues/862).

The *Standard* skin now uses the font `DejaVuSansMono-Bold` and includes a
copy. Before, it had to rely on hardwired font paths, which were less reliable.

If the uploaders get a response code of 429 ("TOO MANY REQUESTS"), they no
longer bother trying again.

Limit station registration to once a day, max.

Station registration now uses HTTP POST, instead of HTTP GET.

Station registration is delayed by a random length of time to avoid everyone
hitting the server at the same time.

Fix problem where aggregation of null wind directions returns 90° instead of
null. Fixes issue [#849](https://github.com/weewx/weewx/issues/849).

Fix wrong station type for Vantage `weectl device --info` query.

Add retransmit information for Vantage `weectl device --info` query.

Fix problem when setting Vantage repeater. Fixes issue 
[#863](https://github.com/weewx/weewx/issues/863).

Detect "dash" values for rain-related measurements on Vantage stations.

Change aggregations `minsumtime` and `maxsumtime` to return start-of-day, 
rather than the time of max rainfall during the day.

Relax requirement that column `dateTime` be the first column in the database.
Fixes issue [#855](https://github.com/weewx/weewx/issues/855).

Allow aggregation of xtypes that are not in the database schema.
Fixes issue [#864](https://github.com/weewx/weewx/issues/864).

Tag suffix `has_data()` now works for xtypes. Fixes issue 
[#877](https://github.com/weewx/weewx/issues/877).

Additional shorthand notations for aggregation and trend intervals. For
example, `3h` for three hours.

Accumulator `firstlast` no longer coerces values to a string. Thanks to user
"Karen" for spotting this!

Fix problem that caused crashes with `firstlast` accumulator type.
Fixes issue [#876](https://github.com/weewx/weewx/issues/876).

Fixed problem that prevented the astrometric heliocentric longitude of a body
from being calculated properly.

Default format for azimuth properties (such as wind direction) is now zero
padded 3 digits. E.g., `005°` instead of `5°`. 

Most almanac properties are now returned as `ValueHelpers`, so they will
obey local formatting conventions (in particular, decimal separators). To
avoid breaking old skins, these properties now have new names. For example,
use `$almanac.venus.altitude` instead of `$almanac.venus.alt`. 

Fix problem that prevented database from getting hit when calculating 
`pressure`. Fixes issue [#875](https://github.com/weewx/weewx/issues/875).

Fix problem that prevented option
[`stale_age`](reference/skin-options/imagegenerator.md#stale_age) from being
honored in image generation. Thanks to user Ian for
PR [#879](https://github.com/weewx/weewx/pull/879)!

Fix problem that prevented complex aggregates such as `max_ge` from being used
in plots. Fixes issue [#881](https://github.com/weewx/weewx/issues/881).

Updated humidex formula and reference. Fixes issue 
[#883](https://github.com/weewx/weewx/issues/883).

Fix bugs in the "basic" skin example.

Fix bug that prevented calculating `$trend` when one of the two records is
missing.

Fix bug that caused the extension installer to crash if one of the service
groups was missing in the configuration file. Fixes issue 
[#886](https://github.com/weewx/weewx/issues/886).

New option [`retry_wait`](reference/weewx-options/general.md#retry_wait). If
`weewxd` encounters a critical error, it will sleep this long before doing a
restart.

Change from old Google Analytics UA code to the GA4 tag system in the Standard
and Seasons skins. Fixes issue [#892](https://github.com/weewx/weewx/issues/892).

All `weectl import` sources now include support for a field map meaning any 
source field can be imported to any WeeWX archive field.

Units for `weectl import` sources that require user specified source data 
units are now specified in the `[[FieldMap]]` stanza. 

Fixed problem when plotting wind vectors from a database that does not include
daily summaries.

Fixed a long-standing bug in the log message format that made 'python' or
'journal' appear as the process name instead of 'weewx'.

The process name for weewxd is now 'weewxd'.  In V4 it was 'weewx'.

The rc script and configuration for FreeBSD/OpenBSD has been updated and now
uses standard BSD conventions.

The DEB/RPM packaging now detect whether systemd is running, so on systems that
use SysV, the rc scripts will be installed, and on systems such as docker that
do not use systemd, no systemd dependencies will be introduced.


### 4.10.2 02/22/2023

Removed errant "f-string" in `imagegenerator.py`.

Added missing `.long_form` to `celestial.inc` that would cause total daylight
to be given in seconds, instead of long form.

Fix problem that a `None` value in `long_form()` would raise an exception.
PR #843. Thanks to user Karen!

The module `user.extensions` is now imported into `wee_reports`. Thanks to
user jocelynj! PR #842.

Fix problem that prevented `wee_device --set-retransmit` from working on
Vantage stations.

Using a bad data binding with an aggregation tag no longer results in an
exception. Instead, it shows the tag in the results. Related to PR #817.


### 4.10.1 01/30/2023

Logging handler `rotate` has been removed. Its need to access privileged
location `/var/log/weewx.log` on start up would cause crashes, even if it was
never used.


### 4.10.0 01/29/2023

Don't inject `txBatteryStatus` and `consBatteryVoltage` into records in the 
Vantage driver. Let the accumulators do it. Fixes issue #802.

Different wake-up strategy for the Vantage console.

Do not write `config_path` and `entry_path` to updated configuration dictionary.
Fixes issue #806.

Allow more flexible formatting for delta times. This can break old skins.
See Upgrade Guide. PR #807.

Fix bug that prevents `group_deltatime` from being used by timespans. Users
who used custom formatting for delta times will be affected. See the Upgrade
Guide. Fixes issue #808.

Add suffix `.length` to class TimespanBinder. This allows expressions such as
$month.length. PR #809. Thanks to user Karen!

Added new unit `hertz`. PR #812. Again, thanks to user Karen!

Calculate `*.wind.maxtime` out of `windGust` like `*.wind.max`
Fixes issue #833

Fix bug that prevents `group_deltatime` from being used by timespans. Users
Add suffix `.length` to class TimespanBinder. This allows expressions such as

Option `line_gap_fraction` can now be used with bar plots. Fixes issue #818.


### 4.9.1 10/25/2022

Fix problem with `wind` for older versions of sqlite.


### 4.9.0 10/24/2022

Fix problem that create 'ghost' values for VantageVue stations.
Fix problem that causes `leafWet3` and `leafWet4` to be emitted in VP2
stations that do not have the necessary sensors.
Fixes issue #771.

Try waking the Vantage console before giving up on LOOP errors.
Better Vantage diagnostics.
Fixes issue #772.

Add missing 30-day barometer graph to Smartphone skin.
Fixes issue #774.

Fix check for `reuse_ssl` for Python versions greater than 3.10.
Fixes issue #775.

The utility `wee_reports` can now be invoked by specifying a `--date` 
and `--time`.
Fixes issue #776.

Allow timestamps that are not integers.
Fixes issue #779.

Add localization file for Traditional Chinese. Thanks to user lyuxingliu!
PR #777.

Don't swallow syntax errors when `wee_config` is looking for drivers.

Include `wind` in daily summary if `windSpeed` is present.

Refine translations for French skin. Thanks to user Pascal!

Allow a custom cipher to be specified for FTP uploads. See option `cipher`
under `[[FTP]]`.

Ensure that `rundir` exists and has correct permissions in weewx-multi

Allow auto-provisioning feature of Seasons to work when using a SQL expression
for option `data_type` in the ImageGenerator. Fixes issue #782.

Allow constants `albedo`, `cn`, and `cd` to be specified when calculating ET.
See the User's Guide. Resolves issue #730.

Fix problem that prevented `wee_reports` from using a default location
for `weewx.conf`.

Post location of the configuration file and the top-level module to the station
registry. Thanks to Vince! PR #705.

Fix minor install warning under Python 3.10. Fixes issue #799.

Fix problem where `xtypes.ArchiveTable.get_series()` does not pass `option_dict`
on to `get_aggregate()`. Fixes issue #797

Added `copytruncate` option to default log rotation configuration.  Thanks to
user sastorsl.  Addresses PR #791.

Update the default and example rules in rsyslog configuration.  The output
from the weewx daemon goes to `weewxd.log` whereas the output from wee_xxx
utilities goes to `weewx.log`.  Also added examples of how to deal with
systemd/journald messing with log output.  Addresses PR #788 and PR #790.
Thanks to user sastorsl.

Allow additional aggregation intervals for observation type `$wind`. In
particular, `vecdir` and `vecavg` can be done for aggregation intervals other
than multiples of a day.
Fixes issue #800.


### 4.8.0 04/21/2022

Allow unit to be overridden for a specific plot by using new option `unit`.
Fixes issue #729.

Fix problem that prevented wind from appearing in NOAA yearly summaries.

Fix honoring global values for `log_success` and `log_failure`. Fix issue #757.

wee_import CSV imports now allow import of text fields. Addresses issue #732.

Explain in the Customization Guide how to include arbitrary SQL expressions
in a plot.

Reorder font download order, for slightly faster downloads.
Fix issue #760.

Add observation types `highOutTemp` and `lowOutTemp` to group_temperature.

Add unit groups for sunshine and rain duration, cloudcover, and pop.
PR #765

Do not allow HUP signals (reload is not allowed as of V4.6).
PR #766.

Do not fork if using systemd.
PR #767.

Fix problem that prevented `wee_config --reconfigure` from working when
using Python 2.7, if the configuration file contained UTF-8 characters.


### 4.7.0 03/01/2022

Introduced new option `generate_once`. If `True`, templates will be generated
only on the first run of the reporting engine. Thanks to user Rich! PR #748.

Added option `wee_device --current` for Vantage.

Fixed two typos in the Standard skin.

Fixed spelling mistakes in the Norwegian translations.  Thanks to Aslak! PR#746

Supply a sensible default context for `group_deltatime` when no context has been
specified.

If `windGustDir` is missing, extract a value from the accumulators.

Fixed typo that shows itself if no `[Labels]/[[Generic]]` section is supplied.
Fixes issue #752.

Fixed calculation of field `bar_reduction` for Vantage type 2 LOOP packets.

Fix problem that prevents `windSpeed` and `windDir` from being displayed in
the RSS feed. Fixes issue #755.


### 4.6.2 02/10/2022

Removed diagnostic code that was inadverently left in the `titlebar.inc` file
in Seasons skin.


### 4.6.1 02/10/2022

Make the `show_rss` and `show_reports` flags work properly.  Fixes issue #739.

Added `$to_list()` utility for use in Cheetah templates.

Fixed a few more untranslated fields in Seasons skin.

Observation types that use the `sum` extractor are set to `None` if no LOOP
packets contributed to the accumulator. Fixes issue #737.

Added `ppm` as default `group_fraction`.  Added default label string for `ppm`.

Added Norwegian translations. Thanks to user Aslak! PR #742.

Fixed problem that caused `wee_database --check-strings` / `--fix-strings`
to fail on TEXT fields. Fixes issue #738.


### 4.6.0 02/04/2022

Easy localization of all skins that come with WeeWX. Big thanks to user Karen,
who drove the effort! PR #665.

Allow options `--date`, `--from`, and `--to` to be used with 
`wee_database --reweight`. PR #659. Thanks to user edi-x!

Added Cheetah helper functions `$jsonize()`, `$rnd()`, and `$to_int()`.

The tag `$alltime`, formerly available as an example, is now a part of WeeWX
core.

New SLE example `$colorize()`. New document on how to write SLEs.

Added conversions for `unix_epoch_ms` and `unix_epoch_ns`. Calculations in
`celestial.inc` now explicitly use `unix_epoch`.

Added almanac attribute `visible` and `visible_change`. For example,
`$almanac.sun.visible` returns the amount of daylight,
`$almanac.sun.visible_change` the difference since yesterday.

Fixed problem that could cause weather xtypes services not to shut down
properly. PR #672. Thanks again to user edi-x!

Added Cheetah tag `$filename`, the relative path of the generated file. Useful
for setting canonical URLs. PR #671. Thanks again to user Karen!

XType `get_scalar()` and `get_series()` calls can now take extra keyword
arguments. PR #673.

Fixed problem where a bad clock packet could crash the WMR100 driver.

Davis documentation for LOOP2 10-minute wind gusts is wrong. The Vantage
actually emits mph, not tenths of mph. Changed driver so it now decodes the
field correctly. Fixes issue #686.

Sending a HUP signal to `weewxd` no longer causes the configuration file to be
reread.

Logging is not done until after the configuration file has been read. This
allows customized logging to start from the very beginning. Fixes issue #699.

Simplified the logging of Cheetah exceptions to show only what's relevant.
Fixes issue #700.

Include a `requirements.txt` file, for installing using pip. Thanks to user
Clément! PR #691.

Fixed problem where `ConfigObj` interpolation would interfere with setting
logging formats.

Added option `--batch-size` to the Vantage version of `wee_device`. See PR #693.

Slightly faster evaluation of the tag suffix `has_data`.
New aggregation type `not_null`.

A string in the database no longer raises an error. Fixes issue #695.

Added plot option `skip_if_empty`. If set to `True`, and there is no non-null
data in the plot, then the plot will not be generated at all. If set to
a time domain (such as `year`), then it will do the check over that domain.
See PR #702.

Parameterized the Seasons skin, making it considerably smaller, while requiring
less configuration. It now includes all types found in the wview-extended
schema. See PR #702.

New FTP option `ftp_encoding` for oddball FTP servers that send their responses
back in something other than UTF-8.

Availability of the pyephem module and extended almanac data is now logged
during startup.

Added column for `last contact` in the sensor status table in the Season skin
to help diagnose missing/flaky sensors.

Fix the weewx.debian and weewx-multi init scripts to work with non-root user.

Added sample tmpfiles configuration to ensure run directory on modern systems
when running weewx as non-root user.

Fixed bug that prevented the ssh port from being specified when using rsync.
Fixes issue #725.

Improved alphanumeric sorting of loop packet/archive record fields displayed
when WeeWX is run directly.

Added sample weewxd init file for 'service' based init on freebsd.  Thanks to
user ryan.

Added i18n-report utility to help check skins for translated strings.


### 4.5.1 04/02/2021

Reverted the wview schema back to the V3 style.

Fixed problem where setup.py would fail if the station description used UTF-8
characters.

Fixed problem where unit labels would not render correctly under Python 2.7 if
they were set by a 3rd party extension. Fixes issue #662.

Added TCP support to the WS1 driver. Thanks to user Mike Juniper!
Fixes issue #664.


### 4.5.0 04/02/2021

The utility `wee_database` has new options `--add-column`, `--rename-column`,
and `--drop-columns` for adding, renaming, and deleting columns in the database.

New optional tag `.series()`, for creating and formatting series in templates.
See the document [Tabs for
series](https://github.com/weewx/weewx/wiki/Tags-for-series) in the wiki. This
is still experimental and subject to change! Addresses issue #341.

New optional tag `.json()` for formatting results as JSON.

New optional tag `.round()`. Useful for rounding results of `.raw` and `.json`
options.

Improved performance when calculating series using aggregation periods that are
multiples of a day.

Changed NOAA reports to use the `normalized_ascii` encoding instead of `utf8`
(which did not display correctly for most browsers). Fixes issue #646.

Plots longer than 2 years use a 6 month time increment.

Uploads to PWSWeather and WOW now use HTTPS. Fixes issue #650.

Fixed bug that prevented the Vantage driver from waiting before a wakeup retry.
Thanks to user Les Niles!

Changed the way of expressing the old "wview" schema to the new V4 way.
Hopefully, this will lead to fewer support issues. Fixes issue #651.

Fixed problem where iterating over a time period without an aggregation would
wrongly include the record on the left.

Fixed bug that caused the incorrect label to be applied to plots where the
aggregation type changes the unit. Fixes issue #654.

Plots now locate the x-coordinate in the middle of the aggregation interval for
all aggregation types (not just min, max, avg). Revisits PR #232.

Added new time units `unix_epoch_ms` and `unix_epoch_ns`, which are unix epoch
time in milliseconds and nanoseconds, respectively.

The FTP uploader now calculates and saves a hash value for each uploaded file.
If it does not change, the file is not uploaded, resulting in significant
time savings. PR #655. Thanks to user Karen!

Updated the version of `six.py` included with WeeWX to 1.15.0. Fixes issue #657.

Option aggregate_interval can now be specified by using one of the "shortcuts",
that is, `hour`, `day`, `week`, `month`, or `year`.

Options `log_success` and `log_failure` are now honored by the `StdArchive` and
`StdQC` services. Fixes issue #727.


### 4.4.0 01/30/2021

`StdWXCalculate` can now do calculations for only LOOP packets, only archive
records, or both. PR #630. Thanks to user g-eddy!

Introduced aggregate types `avg_ge` and `avg_le`. PR #631. Thanks to user
edi-x!

NOAA reports now use a `utf8` encoding instead of `strict_ascii`. This will
only affect new installations. Fixes issue #644.

Introduced new encoding type `normalized_ascii`, which replaces characters that
have accented marks with analogous ascii characters. For example, ö gets
replaced with o.

Patching process is more forgiving about records with interval less than or
equal to zero.

Fixed problem where invalid `mintime` or `maxtime` was returned for days with no
data. Fixes issue #635.

Syntax errors in `weewx.conf` are now logged. PR #637. Thanks to user Rich Bell!

Fixed problem where plots could fail if the data range was outside of a
specified axes range. Fixes issue #638.

Fixed problem that could cause reporting to fail under Python2.7 if the
configuration dictionary contained a comment with a UTF-8 character. Fixes
issue #639.

Fixed problem that could cause program to crash if asking for deltas of a non-
existent key.

The version 4.3.0 patch to fix the incorrect calculation of sums in the daily
summary tables itself contained a bug. This version includes a patch to fix the
problem. It runs once at startup. Fixes issue #642.


### 4.3.0 01/04/2020

Version 4.2.0 had a bug, which caused the sums in the daily summary to be
incorrectly calculated. This version includes a patch to fix the problem. It
runs once at startup. Fixes issue #623.

The WMR200 driver is no longer supported. An unsupported version can be found
at https://github.com/weewx/weewx-wmr200. Support for LaCrosse WS23xx and
Oregon WMR300 will continue.

Service `weewx.wxxtypes.StdDelta` was inadvertently left out of the list of
services to be run. Fortunately, it is not used. Yet. Added it back in.

Added the "old" NWS algorithm as an option for calculating heat index.

Changed how various undocumented parameters in `[StdWXCalculate]` are specified.
The only one people are likely to have used is `ignore_zero_wind`. Its name has
changed to `force_null`, and it has been moved. See the *Upgrading Guide*.

Documented the various `[StdWXCalculate]` options.

Fixed corner case for `windDir` when using software record generation,
`ignore_zero_wind=True`, and `windSpeed=0` for entire record interval. Now emits
last `windDir` value.

Fixed problem when looking up stars with more than one word in their name.
Fixes issue #620.

Fixed problem where wind gust direction is not available when using software
record generation.

Added `--no-prompt` action to `wee_import`, allowing wee_import to be run
unattended.

Fixed problem that prevented option `observations` from being used in the
simulator. Thanks to user Graham!

Fixed problem where wind chill was calculated incorrectly for `METRICWX`
databases. PR #627. Thanks to user edi-x!

Allow wind vectors to be converted to unit of beaufort. Fixes issue #629.

Option `log_failure` under `[StdReport]` is set to `True` by the upgrade 
process. See the *Upgrading Guide*.


### 4.2.0 10/26/2020

CHANGES COMING! This is the last release that will support the LaCrosse WS23xx,
Oregon WMR200 and WMR300 stations. In the future, they will be published as
unsupported extensions.

Made it easier to add new, derived types via `StdWXCalculate`. Fixes issue #491.

Changed the tag system slightly in order to make it possible for the XTypes
system to add new aggregations that take an argument.

Added the new data types in the `extended_wview` schema to the WeeWX types
system. Fixes issue #613.

Added ability to label left, right or both y-axes of graphs.  PR #610.
Fixes issue #609. Thanks to user Brent Fraser!

Added units and labels for the lightning data types.

Fixed problem where threads attempt to access non-existent database. Fixes
issue #579.

Fixed problem that caused reporting units to revert to `US` if they were in a
mixed unit system. Fixes issue #576.

Fixed problem that could cause the station registry to fail if given a location
with a non-ASCII location name.

Changed TE923 bucket size from 0.02589 inches to 1/36 of an inch
(0.02777778 in). PR #575. Fixes issue #574. Thanks to user Timothy!

Undocumented option `retry_certificate` has been renamed to `retry_ssl`, and now
covers all SSL errors (not just certificate errors). Fixes issue #569. Thanks
to user Eric!

Fixed problem caused by specifying a `[Logging]/[[formatters]]` section in
`weewx.conf` that uses interpolated variables.

Fixed problem in the Vantage driver that resulted in incorrect `sunrise`
/ `sunset` being included in loop packets when run under Python 3. Thanks to 
users Constantine and Jacques!

Improved auto-scaling of plot axes.

Fixed problem where aggregates of `windvec` and `windgustvec` returned the
aggregate since start of day, not the start of the aggregation period.
Fixes issue #590.

New unit `beaufort`, included in `group_speed`. Treating beaufort as a separate
type has been deprecated. Fixes issue #591.

New unit `kPa`, included in `group_pressure`. Fixes issue #596.

Fixed bug in the simulator. Made it easier to subclass class `Simulator`.

Expressions in `StdCalibration` are now ordered. Later corrections can depend on
earlier corrections.

Fixed problem under Python 2, where option `none` could cause exception.
PR #597. Thanks to user Clément!

Fixed problem with ws23xx driver under Python 3 that caused it to crash.

Use a more modern formula for heat index. Fixes issue #601. Thanks to
user Peter Q!

Allow overriding the data binding when using iterators. Fixes issue #580.

Fixed problem where old daily summaries may not have a version number.

Fixed problem in WMR200 driver where missing UV reports as index 255.

Added option `force_direction` for working around a WU bug. Fixes issue #614.

Fixed problem where null bytes in an import data file would cause `wee_import`
to fail.


### 4.1.1 06/01/2020

Fixed problem that caused wind speed to be reported to AWEKAS in m/s instead
of km/h.

Fixed problem that caused FTP attempts not to be retried.

Fixed problem that caused monthly and yearly summaries to appear only
sporadically.

Fixed problem when using the ultimeter driver under Python 2.

Fixed problem when using the ws1 driver under Python 2.

Fixed problem that prevented remote directories from being created by FTP.

New strategy for calculating system uptime under Python 3. Revisits
issue #428. Alternative to PR #561.


### 4.1.0 05/25/2020

Archive records emitted by the Vantage driver now include the number of wind
samples per archive interval in field wind_samples.

wee_import can now import WeatherCat monthly .cat files.

Changed the logging configuration dictionary to match the Python documents.
Thanks to user Graham for figuring this out!

Fixed problem that prevented ws1 driver from working under Python 3. PR #556.

Eliminate use of logging in wee_config, allowing it to be used for installs
without syslog.

Allow expressions to be used as a datatype when plotting.

Added option 'reuse_ssl' to FTP. This activates a workaround for a bug in the
Python ftp library that causes long-lived connections to get closed
prematurely. Works only with Python 3.6 and greater.

The cc3000 driver will automatically reboot the hardware if it stops sending
observations. PR #549.

Install using setup.py forgot to set WEEWX_ROOT when installing in non-standard
places. Fixes issue #546.

Fixed bug in ws28xx driver that prevented it from running under Python 3.
Fixes issue #543.

Changed query strategy for calculating min and max wind vectors, which
should result in much faster plot generation.

Fixed bug in wmr9x8 driver that prevented it from running under Python 3.

Fixed several bugs in the te923 driver that prevented it from running under
Python 3.

Added a logging handler for rotating files. See https://bit.ly/2StYSHb for how
to use it. It is the default for macOS.

More information if an exception is raised while querying for vantage hardware
type.

wunderfixer: fixed problem under Python 3 where response was not converted to
str before attempting to parse the JSON. Option --simulate now requires api_key
and password, so it can hit the WU.

Fixed problem in te923 driver under Python 3 that caused it to crash.


### 4.0.0 04/30/2020

Ported to Python 3. WeeWX should now run under Python 3.5 and greater, as well
as Python 2.7. Support for Python 2.5 and 2.6 has been dropped.

New facility for creating new user-defined derived types. See the Wiki article
https://github.com/weewx/weewx/wiki/WeeWX-V4-user-defined-types

WeeWX now uses the Python 'logging' facility. This means log, formats, and
other things can now be customized. Fixes issue #353.

Strings appearing in the data stream no longer cause a TypeError if they can be
converted to a number.

Strings can now be accumulated and extracted in the accumulators, making it
possible to include them in the database schemas.

The utility wee_reports now loads services, allowing it to use user-supplied
extensions. Fixes issue #95.

New default schema ("wview_extended") that offers many new types. The old
schema is still supported. Fixes issue #115.

Optional, more flexible, way of specifying schemas for the daily summaries. The
old way is still supported.

The install process now offers to register a user's station with weewx.com.

The package MySQL-python, which we used previously, is not always available on
Python 3. Ported the MySQL code to use the package mysqlclient as an
alternative.

The default for WOW no longer throttles posting frequency (the default used to
be no more than once every 15 minutes).

Added new aggregate types minsum, minsumtime, sum_le. PR #382.

Unit group group_distance is now a first-class group.

Added new tag $python_version.

Ported to Python2-PyMySQL package on OpenSUSE.

Added new aggregation types 'first' (similar to 'last'), 'diff' (the difference
between last and first value in the aggregation interval), and 'tderiv' (the
difference divided by the time difference).

Created new unit group 'group_energy2', defined as watt-seconds. Useful for
high resolution energy monitors.

An observation type known to the system, but not in a record, will now return a
proper ValueTuple, rather than UnknownType.

Type "stormStart" was added to the unit system. Fixes issue #380.

Added new aggregation type 'growdeg'. Similar to 'heatdeg', or 'cooldeg', it
measures growing degree-days. Basically, cooldeg, but with a different base.
Fixes issue #367. Thanks to user Clay Jackson for guidance!

Ported OS uptime to OpenBSD. Fixes issue #428. Thanks to user Jeff Ross!

Catch SSL certificate errors in uploaders. Retry after an hour. Fixes issue #413.

Wunderfixer has been ported to the new WU API. This API requires an API key,
which you can get from WU. Put it in weewx.conf. Added option --upload-only.
Thanks to user Leon Shaner! Fixes issues #414 and #445.

Wee_import can now import Weather Display monthly log files.

Fixed problem where sub-sections DegreeDays and Trend were located under the
wrong weewx.conf section. Fixes issue #432. Thanks to user mph for spotting
this!

Added new parameters to the Weather Underground uploader. Fixes issue #435.

Added new air quality types pm1_0, pm2_5, and pm10_0 to the unit system. Added
new unit microgram_per_meter_cubed. Added new unit group, group_concentration.

Plist for the Mac launcher now includes a log file for stderr.

Night-day transition in plots now uses shortest travel distance around color
wheel to minimize extra colors. Fixes issue #457. Thanks to user Alex Edwards!

Fixed bug that causes plots to fail when both min and max are zero. Fixes issue #463.

Fixed problem with sqlite driver that can lead to memory growth. See PR #467.
Thanks to user Rich Bell!

Fixed bug that caused windrun to be calculated wrongly under METRICWX unit
system. Fixes issue #452.

If a bad value of 'interval' is encountered in a record, the program will
simply ignore it, rather than stopping. Address issue #375.

Change in how the archive timespan is calculated in the engine. This allows
oddball archive intervals. Fixes issue #469.

NOAA reports are now more tolerant of missing data. Fixes issue #300.

Use of strftime() date and time format codes in template file names is now
supported as an alternative to the legacy 'YYYY', 'MM' and 'DD'. The legacy
codes continue to be supported for backwards compatibility. Fixes issue #415.

New --calc-missing action added to wee_database to calculate and store derived
observations.

wee_import now calculates missing derived observations once all imported data
has been saved to archive. Fixes issue #443.

wee_import now tolerates periods that contain no source data. Fixes issue #499.

wee_import now accepts strings representing cardinal, intercardinal and
secondary intercardinal directions in CSV imports. Partially fixes issue #238.

The field delimiter character may now be defined for wee_import CSV imports.

Ignore historical records if the timestamp is in the future.

Can now recover from MariaDB-specific database connection error 1927.

Changed the name of the unit "litre" to "liter", making its spelling more
consistent with "meter". The spelling "litre" is still accepted.

Systemd type changed from "simple" to "forking". Thanks to user Jaap de Munck
for figuring this one out!

The configuration file is now an optional argument. This means most users will
be able to use the simple command line 'sudo weewxd'.

Use correct log path for netbsd and openbsd in logger setup.

StdWXCalculate no longer calculates anything by default. Instead, types to be
calculated must be listed in weewx.conf. See the Upgrade Guide.

setup.py install no longer saves the old 'bin' subdirectory. Instead, it simply
overwrites it.

Support for the vantage LOOP2 packet format. Fixes issue #374.

The vantage driver now allows 3 retries per read, rather than per
archive interval.


### 3.9.2 07/14/2019

StdPrint now explicitly converts loop and archive fields to UTF-8 before
printing. This means unicode strings can now be included in loop and archive
fields.

Fix WMR300 driver so that it will reject (corrupt) logger records if they
have negative interval (similar to issue #375).

Added 'rain_warning' option in WMR300 driver to remind station owners to reset
the rain counter when the rain counter exceeds a threshold (default is 90%).
Thanks to weewx user Leon!

Added several other debug tools to the WMR300 driver. PR #402.

Wunderfixer now keeps going if a post does not satisfy [[Essentials]].
Fixes issue #329 (again).

Fixed problem that prevented the wee_device --history option from
working with the CC3000 driver.

Fix incorrect `log_success` operation in ftp, rsync, copy
and image generators. PR #373. Partial fix of issue #370.

Fixed problem that could cause the WMR200 to crash WeeWX if the
record interval is zero. Fixes issue #375.

Posts to the Weather Underground now use https, instead of http.
Thanks to user mljenkins! PR #378.

Fixed problem with handling CWOP connection errors. Commit 0a21a72

Fixed problem that prevented to CopyGenerator from handling nested
directories. Fixes issue #379.

Fixed problem that prevented humidity calibration from being set
on Vantage stations.

Improved accuracy of the calculation of Moon phases.
Revisits issue #342.

When the AWEKAS code augments the record for rainRate, it now
checks for a bad timestamp.

The ts1 driver now returns 'barometer' instead of 'pressure'.
Thanks to user 'windcrusader'! Fixes issue #393.

Fixed problem when calculating vector averages. Thanks to user
timtsm! PR #396.

windrun is now calculated on a per-archive period basis, instead
of for the whole day. Thanks to user 'windcrusader'!
PR #399. Fixes issue #250.

Wunderfixer has new option to set socket timeout. This is to compensate
for WU "capacity issues". Thanks to user Leon! See PR #403.

Fixed bug in WS1 driver that caused crash if rain_total was None.

If a file user/schemas.py still exists (a relic from V2.7 and earlier), it
is renamed to user/schemas.py.old. Fixes issue #54.

V3.x test suites now use same data set as V4.x, minimizing the chance of
a false negative when switching versions.

Fixed fine offset driver to warn about (and skip) historical data that have
zero for interval.

Correct rounding problems for rain and other types when posting to CWOP.
Fixes issue #431. Thanks to user ls4096!

Fixed problem that can cause an exception with restx services that do not use
the database manager. See commit 459ccb1.

Sending a SIGTERM signal to weewxd now causes it to exit with status
128 + signal#. PR #442. Thanks to user sshambar!

Fixed bug that could cause WMR200 packets with a timestamp between startup
and the minimum interval to have an interval length of zero. Fixes
issue #375 (again!).


### 3.9.1 02/06/2019

In genplot, do not attempt to normalize unspecified paths.

Introduced option no_catchup. If set to true, a catchup will not be
attempted. Fixes issue #368.


### 3.9.0 02/05/2019

New skin called Seasons. For new users, it will be installed and enabled.
For old users, it will be installed, but not enabled. Fixes issue #75.

There are also two new skins for mobile phones: Mobile and Smartphone.
These are installed, but not enabled, for all users.

Reworked how options get applied for reports. Backstop default values
are supplied by a new file weewx/defaults.py. These can get overridden
by skin.conf, or in a new section [StdReports] / [[Defaults]] in weewx.conf.
See the Customization Guide, section "How options work", for details.
Fixes issue #248.

The skin.conf is optional.  It is possible to specify the entire skin
configuration in the configuration file weewx.conf.

Dropped support of Python 2.5. You must now use either Python 2.6 or 2.7. This
is in anticipation of porting to Python 3.

The image generator now supports the use of a 'stale_age' option. Thanks to
user John Smith. Fixes issue #290.

Rose line width can now be specified with option rose_line_width.

The Felsius unit of temperature (see https://xkcd.com/1923/) is now supported.

New tag $almanac.sidereal_time for calculating current sidereal time

New tag $almanac.separation() for calculating planet separations.

Can now use ephem.readdb() to load arbitrary bodies into the almanac.

StdQC now includes an entry for rain again (inexplicably removed in v3.1.0).

If software record generation is used, the archive interval is now what is
specified in weewx.conf, even if the station supports hardware generation.

Fixed problem where records were downloaded on startup, even if software
record generation was specified.

The tag formatting taxonomy has been simplified. Just use suffix ".format()"
now. Documentation updated to reflect changes. Backwards compatibility with old
suffixes is supported. Fixes issue #328.

Can now set Rapidfire parameter rtfreq. Thanks to user 'whorfin'. PR #304.

Template names can now include the week number. Thanks to user 'stimpy23'.
PR #319.

New aggregation type for plots: 'cumulative'. Thanks to user 'henrikost'.
PR #302.

Fixed problem where MySQL error 2013 could crash WeeWX. Fixes issue #327.

Posts to the Weather Underground will be skipped if an observation type that
is listed in the [[[Essentials]]] subsection is missing. Fixes issue #329.

Upgrade process now explicity upgrades version-to-version, instead of
doing a merge to the new config file. Fixes issue #217.

Example xstats now includes tags for last_year and last_year_todate.
Thanks to user evilbunny2008. PR #325.

Guard against a negative value for 'interval' in WMR200 stations.

Check for missing or negative values for the record field 'interval'.

Changed the formula used to calculate percentage illumination of the moon to
something more accurate around 2018. This formula is only used if pyephem is
not installed. Fixes issue #342.

Fixed bug that caused older, "type A" Vantage Pro2, to crash. Fixes issue #343.

Fixed a bug that caused a divide-by-zero error if a plot range was the same as
a specified min or max scale. Fixes issue #344.

Fixed bug that prevented an optional data_binding from being used in tags
when iterating over records. Fixes issue #345.

Examples lowBattery and alarm now try SMTP_SSL connections, then degrade if
that's not available. Fixes issue #351.

Fixed problem with Brazilian locations at the start of DST. It manifested
itself with the error "NoColumnError: no such column: wind". Fixes issue #356.

Fixed problem that caused sunrise/sunset to be calculated improperly in Sun.py.

Improved coverage of test suites. Fixes issue #337.

wee_device, when used with the Vantage series, now honors the "no prompt" (-y)
option. Fixes issue #361.

Log watch now correctly logs garbage collection events. Thanks to user
buster-one. PR #340.


### 3.8.2 08/15/2018

Added flag to weewx-multi init script to prevent systemd from breaking it.
Thanks to users Timo, Glenn McKechnie, and Paul Oversmith.

Fixed problem that caused wind direction in archive records to always be
calculated in software, even with stations that provide it in hardware.
Fixes issue #336.

### 3.8.1 06/27/2018

Map cc3000 backup battery to consBatteryVoltage and station battery to
supplyVoltage to more accurately reflect the battery functions.

Update the syntax in the rsyslog configuration sample

Significant overhaul to the WMR300 driver.  The driver should now work reliably
on any version of pyusb and libusb.  The driver will now delete history records
from the logger before the logger fills up (the WMR300 logger is not a circular
buffer).  Thanks to users Markus Biewer and Cameron.  Fixes issue #288.

Added automatic clearing of logger for CC3000 driver to prevent logger
overflow (the CC3000 logger is not a circular buffer).  The default is to
not clear the history, but it is highly recommended that you add a logging
threshold once you are confident that all logger data have been captured to
the weewx database.

Improved the robustness of reading from the CC3000 logger.

Better CRC error message in Vantage driver.

Parameterize the configuration directory in weewx-multi init script.

In StdWXCalculate, use None for an observation only if the variables on which
the derived depends are available and None.  Fixes issue #291.

Fixed bug that prevented specifying an explicit alamanac time from working.

Fixed bug that prevented historical records from being downloaded from ws23xx
stations. Thanks to user Matt Brown! Fixes issue #295

Fixed bug that crashed program if a sqlite permission error occurred.

If wind speed is zero, accumulators now return last known wind direction
(instead of None). Thanks to user DigitalDan05. PR #303.

Windrun calculations now include the "current" record. Fixes issue #294.

Fixed bug involving stations that report windGust, but not windGustDir, in
their LOOP data (e.g., Fine Offset), which prevented the direction of max
wind from appearing in statistics. Fixes issue #320.

The engine now waits until the system time is greater than the creation time
of the weewx.conf file before starting up. Fixes issue #330.


### 3.8.0 11/22/2017

The `stats.py` example now works with heating and cooling degree days.
Fixes issue #224.

The ordinal increment between x- and y-axis labels can now be chosen.
The increment between x-axis tick marks can now be chosen. Thanks
to user paolobenve! PR #226.

Bar chart fill colors can now be specified for individual observation
types. Fixes issue #227.

For aggregation types of `avg`, `min` and `max`, plots now locate the x-
coordinate in the middle of the aggregation interval (instead of the end).
Thanks again to user paolobenve! PR #232.

The nominal number of ticks on the y-axis can now be specified using
option `y_nticks`.

Fixed bug that could cause tick crowding when hardwiring y-axis min and
max values.

The uploader framework in restx.py now allows POSTS with a JSON payload,
and allows additional headers to be added to the HTTP request object.

MySQL error 2006 ("MySQL server has gone away") now gets mapped to
`weedb.CannotConnectError`. PR #246

Whether to use an FTP secure data connection is now set separately
from whether to authenticate using TLS. Fixes issue #284.

Corrected formatting used to report indoor temp and humidity to the
Weather Underground.

Added inDewpoint to the observation group dictionary.

Added missing aggregation type 'min_ge'. Thanks to user Christopher McAvaney!

Plots can now use an `aggregate_type` of `last`. Fixes issue #261.

When extracting observation type stormRain (Davis Vantage only), the
accumulators now extract the last (instead of average) value.

Added additional accumulator extractors.

Allow reports to be run against a binding other than `wx_binding`.

Do chdir at start of ImageGenerator so that skin.conf paths are treated the
same as those of other generators.

Changed default value of `stale` for CWOP from 60 to 600 seconds. PR #277.

Vantage driver:
Allow user to specify the Vantage Pro model type in weewx.conf. 
Repeater support added to '-—set-transmitter-type' command.
New commands: '—-set-retransmit',
              '--set-latitude', '--set-longitude'
              '--set-wind-cup',
              '--set-temperature-logging'
Details explained in hardware.htm. Thanks to user dl1rf! PR #270, #272.

Using the `set-altitude` command in `wee_device` no longer changes the
barometer calibration constant in Vantage devices. See PR #263.
Thanks to user dl1rf!

Fixed bug in wmr200 driver that resulted in archive records with no
interval field and 'NOT NULL constraint failed: archive.interval' errors.

Fixed bug in wmr200 driver that caused `windDir` to always be `None` when 
`windSpeed` is zero.

Include rain count in cc3000 status.

In the restx posting, catch all types of httplib.HTTPException, not just
BadStatusLine and IncompleteRead.


### 3.7.1 03/22/2017

Fixed log syntax in wmr100 and wmr9x8 drivers.

Emit Rapidfire cache info only when debug is level 3 or higher.  Thanks to
user Darryn Capes-Davis.

Fixed problem that prevented Rapidfire from being used with databases in
metric units. Fixes issue #230.

Set WOW `post_interval` in config dict instead of thread arguments so that
overrides are possible.  Thanks to user Kenneth Baker.

Distribute example code and example extensions in a single examples directory.
Ensure that the examples directory is included in the rpm and deb packages.

Fixed issue that prevented a port from being specified for MySQL installations.

MySQL error 2003 ("Can't connect to MySQL server...") now gets mapped to
`weedb.CannotConnectError`. PR #234.

By default, autocommit is now enabled for the MySQL driver. Fixes issue #237.

Highs and lows from LOOP packets were not being used in preference to archive
records in daily summaries. Fixed issue #239.


### 3.7.0 03/11/2017

The tag `$current` now uses the record included in the event `NEW_ARCHIVE_RECORD`,
rather than retrieve the last record from the database. This means you can
use the tag `$current` for observation types that are in the record, but not
necessarily in the database. Fixes issue #13.

Most aggregation periods now allow you to go farther in the past. For
example, the tag `$week($weeks_ago=1)` would give you last week. You
can also now specify the start and end of an aggregation period, such
as `$week.start` and `$week.end`.

Can now do `SummaryByDay` (as well as `SummaryByMonth` and `SummaryByYear`).
NB: This can generate *lots* of files --- one for every day in your database!
Leaving this undocumented for now. Fixes issue #185.

When doing hardware record generation, the engine now augments the record with
any additional observation types it can extract out of the accumulators.
Fixes issue #15.

It's now possible to iterate over every record within a timespan.
Fixes issue #182.

Use schema_name = hardware_name pattern in sensor map for drivers that support
extensible sensor suites, including the drivers for cc3000, te923, wmr300,
wmr100, wmr200, wmr9x8

Simplified sensor mapping implementation for wmr100 and wmr200 drivers.  For
recent weewx releases, these are the default mappings for wmr200:

  - 3.6.0: in:0, out:1, e2:2, e3:3, ..., e8:8   hard-coded
  - 3.6.1: in:0, out:1, e1:2, e2:3, ..., e7:8   hard-coded
  - 3.7.0: in:0, out:1, e1:2, e2:3, ..., e7:8   sensor_map

and these are default mappings for wmr100:

  - 3.6.2: in:0, out:1, e1:2, e2:3, ..., e7:8   hard-coded
  - 3.7.0: in:0, out:1, e1:2, e2:3, ..., e7:8   sensor_map

Enabled battery status for every remote T/H and T sensor in wmr100 driver.

Enabled heatindex for each remote T/H sensor in wmr200 driver.

Fixed inverted battery status indicator in wmr200 driver.

Fixed 'Calculatios' typo in wmr100, wmr200, wmr9x8, and wmr300 drivers.

Fixed usb initialization issues in the wmr300 driver.

Added warning in wmr300 driver when rain counter reaches maximum value.

Decode `heatindex` and `windchill` from wmr300 sensor outputs.

Report the firmware version when initializing the cc3000 driver.

Fixed bug in vantage driver that would prevent console wake up during
retries when fetching EEPROM vales. Thanks to user Dan Begallie!

The vantage driver no longer emits values for non-existent sensors.
As a result, LOOP and archive packets are now much smaller. If this works
out, other drivers will follow suit. Partial fix of issue #175.

The vantage driver now emits the barometer trend in LOOP packets as
field `trendIcon`.

The engine now logs locale. Additional information if a TERM signal is
received.

Removed the site-specific "Pond" extensions from the Standard skin.

The Standard skin now includes plots of outside humidity. Fixes 
issue #181.

Fixed reference to `index.html.tmpl` in the xstats example.

Changed algorithm for calculating ET to something more appropriate for
hourly values (former algorithm assumed daily values). Fixes issue #160.

Fixed bug in Celsius to Fahrenheit conversion that affected pressure
conversions in `uwxutils.py`, none of which were actually used.

Fixed bug that was introduced in v3.6.0, which prevented `wee_reports` from
working for anything other than the current time.

Documented the experimental anti-alias feature, which has been in weewx
since v3.1.0. Fixes issue #6.

Fixed problem where multiple subsections under `[SummaryBy...]` stanzas could
cause multiple copies of their target date to be included in the Cheetah
variable `$SummaryByYear` and `$SummaryByMonth`. Fixes issue #187.

Moved examples out of `bin` directory.  Eliminated experimental directory.
Reinforce the use of `user` directory, eliminate use of `examples` directory.
Renamed `xsearch.py` to `stats.py`.

OS uptime now works for freeBSD. Thanks to user Bill Richter!
PR #188.

Broke out developer's notes into a separate document.

Added `@media` CSS for docs to improve printed/PDF formatting.  Thanks to user
Tiouck!

Added a 0.01 second delay after each `read_byte` in ws23xx driver to reduce
chance of data spikes caused by RS232 line contention.  Thanks lionel.sylvie!

The observation `windGustDir` has been removed from wmr100, wmr200, te923, and
fousb drivers.  These drivers were simply assigning `windGustDir` to `windDir`,
since none of the hardware reports an actual wind gust.

Calculation of aggregates over a period of one day or longer can now respect any
change in archive interval. To take advantage of this feature, you will have to
apply an update to your daily summaries. This can be done using the tool
`wee_database`, option `--update`. Refer to the _Changes to daily summaries_
section in the Upgrade Guide to determine whether you should update or not.
Fixes issue #61.

Max value of `windSpeed` for the day is now the max archive value of
`windSpeed`. Formerly, it was the max LOOP value. If you wish to patch your
older daily summaries to interpret max windSpeed this way, use the tool
`wee_database` with option `--update`. Fixes issue #195.

The types of accumulators, and the strategies to put and extract records 
out of them, can now be specified by config stanzas. This will be of
interest to extension writers. See issue #115.

Fixed battery status label in acurite driver: changed from `txTempBatteryStatus`
to `outTempBatteryStatus`.  Thanks to user manos!

Made the lowBattery example more robust - it now checks for any known low
battery status, not just `txBatteryStatus`.  Thanks to user manos!

Added info-level log message to `calculate_rain` so that any rain counter reset
will be logged.

Added better logging for cc3000 when the cc3000 loses contact with sensors
for extended periods of time.

How long to wait before retrying after a bad uploader login is now settable
with option `retry_login`. Fixes issue #212. 

The test suites now use dedicated users `weewx1` and `weewx2`. A shell script
has been included to setup these users.

A more formal exception hierarchy has been adopted for the internal
database library `weedb`. See `weedb/NOTES.md`.

The weedb Connection and Cursor objects can now be used in a "with" clause.

Slightly more robust mechanism for decoding last time a file was FTP'd.


### 3.6.2 11/08/2016

Fixed incorrect WU daily rain field name

Fixed bug that crashed Cheetah if the `weewx.conf` configuration file included
a BOM. Fixes issue #172.


### 3.6.1 10/13/2016

Fixed bug in wunderfixer.

Fixed handling of `StdWXCalculate.Calculations` in `modify_config` in the
wmr100, wmr200, wmr300, and wmr9x8 drivers.

Eliminate the apache2, ftp, and rsync suggested dependencies from the deb
package.  This keeps the weewx dependencies to a bare minimum.

Added retries to usb read in wmr300 driver.

Remapped sensor identifiers in wmr200 driver so that `extraTemp1` and
`extraHumid1` are usable.

Standardized format to be used for times to `YYYY-mm-ddTHH:MM`.


### 3.6.0 10/07/2016

Added the ability to run reports using a cron-like notation, instead of with
every report cycle. See User's Guide for details. Thanks to user Gary Roderick.
PR #122. Fixes issue #17.

Added the ability to easily import CSV, Weather Underground, and Cumulus
data using a new utility, wee_import. Thanks again to über-user Gary Roderick.
PR #148. Fixes issue #97.

Refactored documentation so that executable utilities are now in their own
document, utilities.htm.

Fixed rpm package so that it will retain any changes to the user directory.
Thanks to user Pat OBrien.

No ET when beyond the reach of the sun.

Software calculated ET now returns the amount of evapotranspiration that
occurred during the archive interval. Fixes issue #160

Fixed wee_config to handle config files that have no FTP or RSYNC.

Fixed bug in StdWXCalculate that ignored setting of 'None' (#110).

Which derived variables are to be calculated are now in a separate 
subsection of [StdWXCalculate] called [[Calculations]]. 
Upgrade process takes care of upgrading your config file.

Reset weewx launchtime when waiting for sane system clock (thanks to user
James Taylor).

Fixed anti-alias bug in genplot.  Issue #111.

Corrected the conversion factor between inHg and mbar. Thanks to user Olivier.

Consolidated unit conversions into module weewx.units.

Plots longer than two years now use an x-axis increment of one year. Thanks to
user Olivier!

The WS1 driver now retries connection if it fails. Thanks to user 
Kevin Caccamo! PR #112.

Major update to the CC3000 driver:
 - reading historical records is more robust
 - added better error handling and reporting
 - fixed to handle random NULL characters in historical records
 - fixed rain units
 - added ability to get data from logger as fast as it will send it
 - added support for additional temperature sensors T1 and T2
 - added transmitter channel in station diagnostics
 - added option to set/get channel, baro offset
 - added option to reset rain counter

Fixed brittle reference to USBError.args[0] in wmr200, wmr300, and te923
drivers.

Fixed typo in default te923 sensor mapping for h_3.  Thanks to user ngulden.

Added flag for reports so that reports can be disabled by setting enable=False
instead of deleting or commenting entire report sections in weewx.conf.

The vantage and ws23xx drivers now include the fix for the policy of
"wind direction is undefined when no wind speed".  This was applied to other
drivers in weewx 3.3.0.

Fixed te923 driver behavior when reading from logger, especially on stations
with large memory configuration.  Thanks to users Joep and Nico.

Fixed rain counter problems in wmr300 driver.  The driver no longer attempts
to cache partial packets.  Do no process packets with non-loop data when
reading loop data.  Thanks to user EricG.

Made wmr300 driver more robust against empty usb data buffers.

Fixed pressure/barometer in wmr300 driver when reading historical records.

Fixed problem with the Vantage driver where program could crash if a
serial I/O error happens during write. Fixes issue #134.

Changed name of command to clear the Vantage memory from --clear to
--clear-memory to make it more consistent with other devices.

Fixed problem that prevented channel 8 from being set by the Vantage driver.

Added solaris .smf configuration.  Thanks to user whorfin.

Added option post_indoor_observations for weather underground.

Added maximum value to radiation and UV plots.

In the .deb package, put weewx reports in /var/www/html/weewx instead of
/var/www/weewx to match the change of DocumentRoot in debian 8 and later.


### 3.5.0 03/13/2016

Fixed bug that prevented rsync uploader from working.

Fixed bug in wmr300 driver when receiving empty buffers from the station.

The type of MySQL database engine can now be specified. Default is 'INNODB'.

Updated userguide with capabilities of the TE923 driver added in 3.4.0.

Added aggregation type min_ge(val).

Provide better feedback when a driver does not implement a configurator.

Added humidex and appTemp to group_temperature. Fixed issue #96.

Backfill of the daily summary is now done in "tranches," reducing the memory
requirements of MySQL. Thanks to über-user Gary Roderick! Fixes issue #83.

Made some changes in the Vantage driver to improve performance, particularly
with the IP version of the logger. Thanks to user Luc Heijst for nagging
me that the driver could be improved, and for figuring out how.

Plotting routines now use Unicode internally, but convert to UTF-8 if a font
does not support it. Fixes issue #101.

Improved readability of documents on mobile devices. Thank you Chris
Davies-Barnard!

The loop_on_init option can now be specified in weewx.conf

When uploading data to CWOP, skip records older than 60 seconds.  Fixes
issue #106.

Added modify_config method to the driver's configuration editor so that drivers
can modify the configuration during installation, if necessary.

The fousb and ws23xx drivers use modify_config to set record_generation to
software.  This addresses issue #84.

The wmr100, wmr200, wmr9x8, and wmr300 drivers use modify_config to set
rainRate, heatindex, windchill, and dewpoint calculations to hardware instead
of prefer_hardware since each of these stations has partial packets.  This
addresses issue #7 (SF #46).


### 3.4.0 01/16/2016

The tag $hour has now been added. It's now possible to iterate over hours.
Thanks to user Julen!

Complete overhaul of the te923 driver.  Thanks to user Andrew Miles.  The
driver now supports the data logger and automatically detects small or large
memory models.  Added ability to set/get the altitude, lat/lon, and other
station parameters.  Significant speedup to reading station memory, from 531s
to 91s, which is much closer to the 53s for the te923tool written in C (all for
a station with the small memory model).

The wee_debug utility is now properly installed, not just distributed.

Fixed bug in almanac code that caused an incorrect sunrise or sunset to be
calculated if it followed a calculation with an explicit horizon value.

Localization of tags is now optional. Use function toString() with
argument localize set to False. Example: 
$current.outTemp.toString($localize=False)
Fixes issue #88.

In the acurite driver, default to use_constants=True.

Fixed bug in the rhel and suse rpm packaging that resulted in a configuration
file with html, database, and web pages in the setup.py locations instead of
the rpm locations.

The extension utility wee_extension now recognizes zip archives as well as
tar and compressed tar archives.

Check for a sane system time when starting up.  If time is not reasonable,
wait for it.  Log the time status while waiting.

Added log_success option to cheetah, copy, image, rsync, and ftp generators.

Older versions of MySQL (v5.0 and later) are now supported.


### 3.3.1 12/06/2015

Fixed bug when posting to WOW.

Fixed bug where the subsection for a custom report gets moved to the very
end of the [StdReport] section of a configuration file on upgrade. 
Fixes issue #81.


### 3.3.0 12/05/2015

Now really includes wunderfixer. It was inadvertently left out of the install
script.

Rewrote the almanac so it now supports star ephemeris. For example,
$almanac.rigel.next_rising. Fixes issue #79.

Uninstalling an extension with a skin now deletes all empty directories. This
fixes issue #43.

Fixed bug in WMR200 driver that caused it to emit dayRain, when what it was
really emitting was the "rain in the last 24h, excluding current hour."
Fixes issue #62.

Fixed bug in WMR200 driver that caused it to emit gauge pressure for altimeter
pressure. Thanks to user Mark Jenks for nagging me that something was wrong.

Fixed bug that caused wind direction to be calculated incorrectly, depending
on the ordering of a dictionary. Thanks to user Chris Matteri for not only
spotting this subtle bug, but offering a solution. 

StdPrint now prints packets and records in (case-insensitive) alphabetical
order.

Fixed wind speed decoding in the acurite driver.  Thanks to aweatherguy.

The StdRESTful service now supports POSTs, as well as GETs.

The FTP utility now catches PickleError exceptions, then does a retry.

Added unit 'minute' to the conversion dictionary.

The vertical position of the bottom label in the plots can now be
set in skin.conf with option bottom_label_offset.

An optional port number can now be specified with the MySQL database.

Added option use_constants in the Acurite driver.  Default is false; the
calibration constants are ignored, and a linear approximation is used for
all types of consoles.  Specify use_constants for 01035/01036 consoles to
calculate using the constants.  The 02032/02064 consoles always use the
linear approximation.

Fixed test for basic sensor connectivity in the Acurite driver.

The policy of "wind direction is undefined when no wind speed" is enforced
by the StdWXCalculate service.  There were a few drivers that were still
applying the policy: acurite, cc3000, fousb, ws1, wmr100, wmr200, ultimeter.
These have been fixed.

Changed logic that decides whether the configuration file includes a custom
schema, or the name of an existing schema.

Added new command-line utility wee_debug, for generating a troubleshooting 
information report.

Added option --log-label to specify the label that appears in syslog entries.
This makes it possible to organize output from multiple weewx instances
running on a single system.

Fixed problem with the Vantage driver that caused it to decode the console
display units incorrectly. Thanks to Luc Heijst!

The WMR300 driver is now part of the weewx distribution.


### 3.2.1 07/18/15

Fixed problem when using setup.py to install into a non-standard location.
Weewx would start a new database in the "standard" location, ignoring the
old one in the non-standard location.


### 3.2.0 07/15/15

There are now five command-line utilities, some new, some old

 - `wee_config`:    (New) For configuring weewx.conf, in particular, 
                    selecting a new device driver.
 - `wee_extension`: (New) For adding and removing extensions.
 - `wee_database`:  (Formerly called wee_config_database)
 - `wee_device`:    (Formerly called wee_config_device)
 - `wee_reports`:   No changes.
 
The script setup.py is no longer used to install or uninstall extensions.
Instead, use the new utility wee_extension.

Wunderfixer is now included with weewx --- no need to download it separately. 
It now works with MySQL, as well as sqlite, databases. It also supports
metric databases. Thanks to user Gary Roderick!

Fixed bug in 12-hour temperature lookup for calculating station pressure from
sea level pressure when database units are other than US unit system.

Added guards for bogus values in various wxformula functions.

Added windrun, evapotranspiration, humidex, apparent temperature, maximum
theoretical solar radiation, beaufort, and cloudbase to StdWXCalculate.

If StdWXCalculate cannot calculate a derived variable when asked to, it now
sets the value to null. Fixes issue #10.

Added option to specify algorithm in StdWXCalculate.  So far this applies
only to the altimeter calculation.

Added option max_delta_12h in StdWXCalculate, a window in which a record will 
be accepted as being "12 hours ago." Default is 1800 seconds.

Fixed bug in debian install script - 'Acurite' was not in the list of stations.

$almanac.sunrise and $almanac.sunset now return ValueHelpers. Fixes issue #26.

Added group_distance with units mile and km.

Added group_length with units inch and cm.

Failure to launch a report thread no longer crashes program.

The WU uploader now publishes soil temperature and moisture, as well as
leaf wetness.

Increased precision of wind and wind gust posts to WU from 0 to 1 
decimal point.

Increased precision of barometer posts to WOW from 1 to 3 decimal points.

A bad CWOP server address no longer crashes the CWOP thread.

The "alarm" example now includes a try block to catch a NameError exception
should the alarm expression include a variable not in the archive record.

Fixed bug that shows itself if marker_size is not specified in skin.conf

Show URLs in the log for restful uploaders when debug=2 or greater.

Fixed problem that could cause an exception in the WMR200 driver when
formatting an error string.

Added better recovery from USB failures in the ws28xx driver.

Added data_format option to FineOffset driver.  Thanks to Darryl Dixon.

Decoding of data is now more robust in the WS1 driver.  Get data from the
station as fast as the station can spit it out.  Thanks to Michael Walker.

Changes to the WS23xx driver include:
  - Fixed wind speed values when reading from logger.  Values were too
    high by a factor of 10.
  - wrapped non-fatal errors in WeeWXIO exceptions to improve error
    handling and failure recovery

Changes to the AcuRite driver include:
 - The AcuRite driver now reports partial packets as soon as it gets them
     instead of retaining data until it can report a complete packet
 - Improved timing algorithm for AcuRite data.  Thanks to Brett Warden.
 - Added acurite log entries to logwatch script.  Thanks to Andy.
 - Prevent negative rainfall amounts in acurite driver by detecting
     counter wraparound
 - Use 13 bits for rain counter instead of 12 bits
 - Use only 12 bits for inside temperature in acurite driver when decoding
     for 02032 stations

Changes to the TE923 driver include:
 - consolidated retries
 - improved error handling and reporting

Changes to the WMR9x8 driver include:
 - Correct bug that caused yesterday's rain to be decoded as dayRain
 - LOOP packet type 'battery' is now an int, instead of a bool
 - The driver can now be run standalone for debugging purposes.
 
The Vantage driver now catches undocumented termios exceptions and converts
them to weewx exceptions. This allows retries if flushing input or output
buffers fail. Fixes issue #34.

Default values for databases are now defined in a new section [DatabaseTypes]. 
New option "database_type" links databases to database type. Installer will
automatically update old weewx.conf files.

The RESTful services that come with weewx are now turned on and off by
option "enable". Installer will automatically update old weewx.conf files. 
Other RESTful services that don't use this method will continue to work.

Option bar_gap_fraction is now ignored. Bar plot widths are rendered explicitly
since V3.0, making the option unnecessary. Fixes issue #25.

Added additional debug logging to main engine loop.

FTP uploader now retries several times to connect to a server, instead of 
giving up after one try. Thanks to user Craig Hunter!


### 3.1.0 02/05/15

Fixed setup.py bug that caused list-drivers to fail on deb and rpm installs.

Added a wait-and-check to the stop option in the weewx.debian rc script.

Fixed bug in the Vantage driver that causes below sea-level altitudes 
to be read as a large positive number. Also, fixed problem with altitude
units when doing --info (ticket #42).

Fixed bug in wmr100 driver that causes gust wind direction to be null.

Fixed bug in wmr200 driver that causes gust wind direction to be null.

Fixed ultimeter driver to ensure wind direction is None when no wind speed
Thanks to user Steve Sykes.

Fixed bug in calculation of inDewpoint.  Thanks to user Howard Walter.

Assign default units for extraHumid3,4,5,6,7, extraTemp4,5,6,7, leafTemp3,4,
and leafWet1,2.

Use StdWXCalculate to ensure that wind direction is None if no wind speed.

Fixed sign bug in ultimeter driver.  Thanks to user Garrett Power.

Use a sliding window with default period of 15 minutes to calculate the
rainRate for stations that do not provide it.

Added support for AcuRite weather stations.  Thanks to users Rich of Modern
Toil, George Nincehelser, Brett Warden, Preston Moulton, and Andy.

The ultimeter driver now reads data as fast as the station can produce it.
Typically this results in LOOP data 2 or 3 times per second, instead of
once per second.  Thanks to user Chris Thompstone.

The daily summary for wind now uses type INTEGER for column sumtime,
like the other observation types.

Utility wee_reports no longer chokes if the optionally-specified timestamp
is not in the database. Can also use "nearest time" if option 'max_delta'
is specified in [CheetahGenerator].

Utility wee_config_device can now dump Vantage loggers to metric databases.
Fixes ticket #40.

Fixed problem where dumping to database could cause stats to get added to
the daily summaries twice.

FTP over TLS (FTPS) sessions are now possible, but don't work very well with
Microsoft FTP servers. Requires Python v2.7. Will not work with older
versions of Python. Fixes ticket #37.

WeatherUnderground passwords are now quoted, allowing special characters
to be used. Fixes ticket #35.

New tag $obs, allowing access to the contents of the skin configuration
section [Labels][[Generic]]. Fixes ticket #33.

Better error message if there's a parse error in the configuration file.

Added wxformulas for evapotranspiration, humidex, apparent temperature, and
other calculations.

Added --loop-on-init option for weewxd. If set, the engine will keep retrying
if the device cannot be loaded. Otherwise, it will exit.

Changed the weedb exception model to bring it closer to the MySQL exception
model. This will only affect those programming directly to the weedb API.


### 3.0.1 12/07/14

Fixed bug in setup.py that would forget to insert device-specific options
in weewx.conf during new installations.


### 3.0.0 12/04/14

Big update with lots of changes and lots of new features. The overall
goal was to make it easier to write and install extensions. Adding
custom databases, units, accumulators and many other little things
have been made easier.

Skins and skin.conf continue to be 100% backwards compatible (since
V1.5!).  However, search-list extensions will have to be rewritten.
Details in the Upgrading Guide.

Previously, configuration options for all possible devices were
included in the configuration file, weewx.conf. Now, for new installs,
it has been slimmed down to the minimum and, instead, configuration
options are added on an "as needed" basis, using a new setup.py option
"configure".

Your configuration file, weewx.conf should be automatically updated to
V3 by the upgrade process, using your previously chosen hardware. But,
check it over. Not sure we got everything correct. See the Upgrading
Guide.

Specific changes follow.

There is no longer a separate "stats" database. Instead, statistics
are included in the regular database (e.g., 'weewx.sdb') as separate
tables, one for each observation type.

Total rewrite of how data gets bound to a database. You now specify a
"data binding" to indicate where data should be going, and where it is
coming from. The default binding is "wx_binding," the weather binding,
so most users will not have to change a thing.
 
Other database bindings can be used in tags. Example:
  $current($data_binding=$alt_binding).outTemp
Alternate times can also be specified:
  $current($timestamp=$othertime).outTemp

Explicit time differences for trends can now be specified:
  $trend($time_delta=3600).barometer

Introduced a new tag $latest, which uses the last available timestamp
in a data binding (which may or may not be the same as the "current"
timestamp).

Introduced a new tag $hours_ago, which returns the stats for X hours
ago.  So, the max temperature last hour would be
$hours_ago($hours_ago=1).outTemp.max.

Introduced a shortcut $hour, which returns the stats for this hour.
So, the high temperature for this hour would be $hour.outTemp.max

Introduced a new tag $days_ago, which returns the stats for X days
ago.  So, the max temperature the day before yesterday would be
$days_ago($days_ago=2).outTemp.max.

Included a shortcut $yesterday: The tag $yesterday.outTemp.max would
be yesterday's max temperature.

Introduced a new aggregation type ".last", which returns the last
value in an aggregation interval. E.g., $week.outTemp.last would
return the last temperature seen in the week.

Introduced a new aggregation type ".lasttime" which returns the time
of the above.

Can now differentiate between the max speed seen in the archive
records (e.g., $day.windSpeed.max) and the max gust seen
($day.wind.max or $day.windGust.max).

Allow other data bindings to be used in images.

Made it easier to add new unit types and unit groups.

The archive interval can now change within a database without
consequences.

Total rewrite of how devices are configured. A single utility
wee_config_device replaces each of the device-specific configuration
utilities.

The Customization Guide was extended with additional examples and option
documentation.

Removed the no longer needed serviced StdRESTful, obsolete since V2.6

Fixed bug in querying for schemas that prevented older versions of
MySQL (V4.X) from working.

Improved error handling and retries for ws1, ultimeter, and cc3000
drivers.

Fixed missing dew initializations in wmr9x8 driver.  Fixed
model/_model initialization in wmr9x8 driver.

Fixed uninitialized usb interface in wmr200 driver.

Fixed wakup/wakeup typo in _getEEPROM_value in vantage driver.

Made the ftpupload algorithm a little more robust to corruption of the
file that records the last upload time.

Added observation type 'snow'. It generally follows the semantics of
'rain'.

Fixed possible fatal exception in WS23xx driver.  Fixed use of str as
variable name in WS23xx driver.

Now catches database exceptions raised during commits, converting them
to weedb exceptions. Weewx catches these, allowing the program to keep
going, even in the face of most database errors.

For the fine offset stations, record connection status as rxCheckPercent
(either 0 or 100%) and sensor battery status as outTempBatteryStatus (0
indicates ok, 1 indicates low battery).

For WS23xx stations, hardware record generation is now enabled and is the
default (previously, software record generation was the default).

Fixed bug in WS28xx driver the prevented reading of historical records
when starting with an empty database.

The database schemas are now their own package. The schema that was in
user/schemas.py can now be found in weewx/schemas/wview.py.


### 2.7.0 10/11/14

Added the ability to configure new Vantage sensor types without using
the console. This will be useful to Envoy users.  Thanks to user Deborah 
Pickett for this contribution! 

Allow calibration constants to be set in the Vantage EEPROM. This will
particularly be useful to southern hemisphere users who may want to
align their ISS to true north (instead of south), then apply a 180
correction. Thanks again to Deborah Pickett!
 
Enabled multiple rsync instances for a single weewx instance.
 
More extensive debug information for rscync users.

Added the ability to localize the weewx and server uptime. See the
Customization Guide for details. This will also cause a minor backwards 
incompatibility. See the Upgrading Guide for details.

Added catchup to the WS28xx driver, but still no hardware record generation.

Changed lux-to-W/m^2 conversion factor in the fine offset driver.

Added rain rate calculation to Ultimeter driver.

Changed setTime to retrieve system time directly rather than using a value
passed by the engine. This greatly improves the accuracy of StdTimeSync,
particularly in network based implementations. Thanks to user Denny Page!

Moved clock synchronization options clock_check and max_drift back to
section [StdTimeSynch].

Fixed ENDPOINT_IN in the te923 driver.  This should provide better
compatibility with a wider range of pyusb versions.

Now catches MySQL exceptions during commits and rollbacks (as well
as queries) and converts them to weedb exceptions.

Catch and report configobj errors when reading skin.conf during the
generation of reports.

Ensure correct location, lat, lon, and altitude modifications in the
debian postinst installer script.

In the debian installer, default to ttyUSB0 instead of ttyS0 for stations
with a serial interface.

Added CC3000 to debian installer scripts.

Fixed bug that can affect hardware that emits floating point timestamps,
where the timestamp is within 1 second of the end of an archive interval.

Changed UVBatteryStatus to uvBatteryStatus in the WMR100 driver in order
to match the convention used by other drivers.

Fixed the shebang for te923, ws23xx, ultimeter, ws1, and cc3000 drivers.


### 2.6.4 06/16/14

The WMR100 driver now calculates SLP in software. This fixes a problem
with the WMRS200 station, which does not allow the user to set altitude.

The WMR100 driver was incorrectly tagging rain over the last 24 hours as
rain since midnight. This caused a problem with WU and CWOP posts.

Fix cosmetic problem in wee_config_fousb pressure calibration.

Detect both NP (not present) and OFL (outside factory limits) on ws28xx.

Added driver for PeetBros Ultimeter stations.

Added driver for ADS WS1 stations.

Added driver for RainWise Mark III stations and CC3000 data logger.

Added automatic power cycling to the FineOffsetUSB driver.  Power cycle the
station when a USB lockup is detected.  Only works with USB hubs that provide
per-port power switching.

Fix imagegenerator aggregation to permit data tables with no 'interval' column.

Prompt for metric/US units for debian installations.

For WS28xx stations, return 0 for battery ok and 1 for battery failure.

If a connection to the console has been successfully opened, but then on
subsequent connection attempts suffers an I/O error, weewx will now attempt
a retry (before it would just exit).


### 2.6.3 04/10/14

Hardened the WMR100 driver against malformed packets.

The plot images can now use UTF-8 characters.

Fixed a problem where the Ambient threads could crash if there were
no rain database entries.

Battery status values txBatteryStatus and consBatteryVoltage now appear in
the archive record. The last LOOP value seen is used.  

CWOP posts are now slightly more robust.

Fixed pressure calculation in wee_config_fousb.

Prevent failures in imagegenerator when no unicode-capable fonts are installed.

Provide explicit pairing feedback using wee_config_ws28xx

Count wxengine restarts in logwatch.

Cleaned up USB initialization for fousb, ws28xx, and te923 drivers.


### 2.6.2 02/16/14

Fixed bug that crashes WMR200 driver if outTemp is missing.

Fixed bug that can crash RESTful threads if there is missing rain data.

Sqlite connections can now explicitly specify a timeout and 
isolation_level.

Server uptime now reported for MacOS

Fixed bug that prevented Rapidfire posts from being identified as such.


### 2.6.1 02/08/14

Fixed bug that crashed main thread if a StdQC value fell out of range.


### 2.6.0 02/08/14

Changed the RESTful architecture so RESTful services are now first-class
weewx services. This should simplify the installation of 3rd party
extensions that use these services.

Broke up service_list, the very long list of services to be run, into
five separate lists. This will allow services to be grouped together,
according to when they should be run.

Defined a structure for packaging customizations into extensions, and added
an installer for those extensions to setup.py.

Changed the default time and date labels to use locale dependent formatting.
The defaults should now work in most locales, provided you set the
environment variable LANG before running weewx.

Changed default QC barometric low from 28 to 26. Added inTemp,
inHumidity, and rain.

Ranges in MinMax QC can now include units.

When QC rejects values it now logs the rejection.

Introduced a new unit system, METRICWX. Similar to METRIC, it uses
mm for rain, mm/hr for rain rate, and m/s for speed.

Added an option --string-check and --fix to the utility wee_config_database
to fix embedded strings found in the sqlite archive database.

Font handles are now cached in order to work around a memory leak in PIL.

Now does garbage collection every 3 hours through the main loop.

Image margins now scale with image and font sizes.

Now works with the pure Python version of Cheetah's NameMapper, albeit very
slowly.

Fixed bug that prevented weewx from working with Python v2.5.

Fixed bug in SummaryByMonth and SummaryByYear that would result in duplicate
month/year entries when generating from multiple ByMonth or ByYear templates.

Consolidated pressure calculation code in ws23xx, ws28xx, te923, and fousb.

Catch USB failures when reading Fine Offset archive interval.

Added Vantage types stormRain and windSpeed10 to the list of observation
types.

Simulator now generates types dewpoint, pressure, radiation, and UV.

The forecast extension is once again distributed separately from weewx.

Minor cleanup to Standard skin for better out-of-the-box behavior:
 - default to no radar image instead of pointing every station to Oregon
 - not every WMR100 is a WMR100N
 
Failure to set an archive interval when using bar plots no longer results
in an exception.

Change to skin directory before invoking Cheetah on any templates.


### 2.5.1 12/30/13

Added UV plots to the templates. They will be shown automatically if you
have any UV data.

Fixed bug when reading cooling_base option.

Default to sane behavior if skin does not define Labels.

Fixed bug in setting of CheetahGenerator options.

Fixed qsf and qpf summary values in forecast module.

Fixed handling of empty sky cover fields in WU forecasts.

Forecast module now considers the fctcode, condition, and wx fields for
precipitation and obstructions to visibility.

Added options to forecast module to help diagnose parsing failures and new
forecast formats.

Added retries when saving forecast to database and when reading from database.

Fixes to the Fine Offset driver to eliminate spikes caused by reading from
memory before the pointer had been updated (not the same thing as an unstable
read).

Added driver for LaCrosse 2300 series of weather stations.

Added driver for Hideki TE923 series of weather stations.


### 2.5.0 10/29/13

Introduced a new architecture that makes it easier to define search
list extensions. The old architecture should be 100% backwards compatible.

Added station registry service. This allows weewx to optionally
"phone home" and put your station location on a map.

Added a forecast service and reporting options.  The forecast service
can generate Zambretti weather or XTide tide forecasts, or it can download
Weather Underground or US National Weather Service weather forecasts.  These
data can then be displayed in reports using the Cheetah template engine.  The
forecast service is disabled by default.

Weewx now allows easier localization to non-English speaking locales.
In particular, set the environment variable LANG to your locale, and
then weewx date and number formatting will follow local conventions.
There are also more labeling options in skin.conf. Details in a new section
in the Customization Guide.

Added aggregate type "minmax" and "maxmin". Thank you user Gary Roderick!

New option in [StdArchive] called "loop_hilo". Setting to True will
cause both LOOP and archive data to be used for high/low statistics.
This is the default. Setting to False causes only archive data to be used.

When a template fails, skip only that template, not everything that the
generator is processing.

Trend calculations no longer need a record at precisely (for example)
3 hours in the past. It can be within a "grace" period.

FineOffset driver now uses the 'delay' field instead of the fixed_block
'read_period' for the archive record interval when reading records from
console memory.

FineOffset driver now support for multiple stations on the same USB.

FineOffset driver now reduces logging verbosity when bad magic numbers
appear. Log only when the numbers are unrecognized or change.
The purpose of the magic numbers is still unknown.

WMR100, Vantage, FineOffset, and WS28xx drivers now emit a null wind
direction when the wind speed is zero.  Same for wind gust.

For WMR9x8 stations, wind chill is now retrieved from the console
rather than calculated in software. Thank you user Peter Ferencz!

For WMR9x8 stations, the first extra temperature sensor (packet code 4)
now shows up as extraTemp1 (instead of outTemp). Thanks again to 
Peter Ferencz.

For WMR9x8 stations, packet types 2 and 3 have been separated. Only the
latter is used for outside temperature, humidity, dewpoint. The former
is used for "extra" sensors. Corrected the calculation for channel
numbers >=3. Also, extended the number of battery codes. Thanks to Per
Edström for his patience in figuring this out!

For WMR200 stations, altitude-corrected pressure is now emitted correctly.

ws28xx driver improvements, including: better thread control; better logging
for debugging/diagnostics; better timing to reduce dropouts; eliminate writes
to disk to reduce wear when used on flash devices. Plus, support for
multiple stations on the same USB.

Fixed rain units in ws28xx driver.

The LOOP value for daily ET on Vantages was too high by a factor of 10. 
This has been corrected.

Fixed a bug that caused values of ET to be miscalculated when using
software record generation.

Ported to Korora 19 (Fedora 19). Thanks to user zmodemguru!

Plots under 16 hours in length, now use 1 hour increments (instead of 
3 hours).

No longer emits "deprecation" warning when working with some versions
of the MySQLdb python driver.

Added ability to build platform-specific RPMs, e.g., one for RedHat-based
distributions and one for SuSE-based distributions.

Fixed the 'stop' and 'restart' options in the SuSE rc script.

The weewx logwatch script now recognizes more log entries and errors.


### 2.4.0 08/03/13

The configuration utility wee_config_vantage now allows you to set
DST to 'auto', 'off', or 'on'. It also lets you set either a time
zone code, or a time zone offset.

The service StdTimeSync now catches startup events and syncs the clock
on them. It has now been moved to the beginning of the list
"service_list" in weewx.conf. Users may want to do the same with their
old configuration file.

A new event, END_ARCHIVE_PERIOD has been added, signaling the end of
the archive period.

The LOOP packets emitted by the driver for the Davis Vantage series
now includes the max wind gust and direction seen since the beginning
of the current archive period.

Changed the null value from zero (which the Davis documentation specifies)
to 0x7fff for the VP2 type 'highRadiation'.

Archive record packets with date and time equal to zero or 0xff now
terminate dumps.

The code that picks a filename for "summary by" reports has now been
factored out into a separate function (getSummaryByFileName). This
allows the logic to be changed by subclassing.

Fixed a bug that did not allow plots with aggregations less than 60 minutes
across a DST boundary.

Fixed bug in the WMR100 driver that prevented UV indexes from being 
reported.

The driver for the LaCrosse WS-28XX weather series continues to evolve and
mature. However, you should still consider it experimental.


### 2.3.3 06/21/13

The option week_start now works.

Updated WMR200 driver from Chris Manton.

Fixed bug that prevented queries from being run against a MySQL database.


### 2.3.2 06/16/13

Added support for the temperature-only sensor THWR800. Thanks to
user fstuyk!

Fixed bug that prevented overriding the FTP directory in section
[[FTP]] of the configuration file.

Day plots now show 24 hours instead of 27. If you want the old
behavior, then change option "time_length" to 97200.

Plots shorter than 24 hours are now possible. Thanks to user Andrew Tridgell.

If one of the sections SummaryByMonth, SummaryByYear, or ToDate is missing,
the report engine no longer crashes.

If you live at a high latitude and the sun never sets, the Almanac now
does the right thing.

Fixed bug that caused the first day in the stats database to be left out
of calculations of all-time stats.


### 2.3.1 04/15/13

Fixed bug that prevented Fine Offset stations from downloading archive
records if the archive database had no records in it.

rsync should now work with Python 2.5 and 2.6 (not just 2.7)


### 2.3.0 04/10/13

Davis Vantage stations can now produce station pressures (aka, "absolute
pressure"), altimeter pressures, as well as sea-level pressure. These will
be put in the archive database.

Along the same line, 'altimeter' pressure is now reported to CWOP, rather
than the 'barometer' pressure. If altimeter pressure is not available,
no pressure is reported.

Fixed bug in CWOP upload that put spaces in the upload string if the pressure
was under 1000 millibars.

A bad record archive type now causes a catch up to be abandoned, rather
than program termination.

Fixed bug in trends, when showing changes in temperature. NB: this fix will
not work with explicit unit conversion. I.e., $trend.outTemp.degree_C will
not work.

Modified wee_config_vantage and wee_config_fousb so that the configuration
file will be guessed if none is specified.

Fixed wxformulas.heatindexC to handle arguments of None type.

Fixed bug that causes Corrections to be applied twice to archive records if
software record generation is used.

rsync now allows a port to be specified.

Fixed day/night transition bug.

Added gradients to the day/night transitions.

Numerous fixes to the WMR200 driver. Now has a "watchdog" thread.

All of the device drivers have now been put in their own package
'weewx.drivers' to keep them together. Many have also had name changes
to make them more consistent:
    OLD                        NEW
    VantagePro.py (Vantage)    vantage.py (Vantage)
    WMR918.py     (WMR-918)    wmr9x8.py  (WMR9x8)
    wmrx.py       (WMR-USB)    wmr100.py  (WMR100)

    new (experimental) drivers:
    wmr200.py (WMR200)
    ws28xx.py (WS28xx)

The interface to the device driver "loader" function has changed slightly. It
now takes a second parameter, "engine". Details are in the Upgrading doc.

The FineOffsetUSB driver now supports hardware archive record generation.

When starting weewx, the FineOffsetUSB driver will now try to 'catch up' - it
will read the console memory for any records that are not yet in the database.

Added illuminance-to-radiation conversion in FineOffsetUSB driver.

Added pressure calibration option to wee_config_fousb and explicit support for
pressure calibration in FineOffsetUSB driver.

Fixed windchill calculation in FineOffsetUSB driver.

Fixed FineOffsetUSB driver to handle cases where the 'delay' is undefined,
resulting in a TypeError that caused weewx to stop.

The FineOffsetUSB driver now uses 'max_rain_rate' (measured in cm/hr) instead
of 'max_sane_rain' (measured in mm) to filter spurious rain sensor readings.
This is done in the driver instead of StdQC so that a single parameter can
apply to both LOOP and ARCHIVE records.

### 2.2.1 02/15/13

Added a function call to the Vantage driver that allows the lamp to be
turned on and off. Added a corresponding option to wee_config_vantage.

Fixed bug where an undefined wind direction caused an exception when using
ordinal wind directions.

### 2.2.0 02/14/13

Weewx can now be installed using Debian (DEB) or Redhat (RPM) packages, as well
as with the old 'setup.py' method. Because they install things in different
places, you should stick with one method or another. Don't mix and match.
Thanks to Matthew Wall for putting this together!

Added plot options line_gap_fraction and bar_gap_fraction, which control how
gaps in the data are handled by the plots. Also, added more flexible control of
plot colors, using a notation such as 0xBBGGRR, #RRGGBB, or the English name,
such as 'yellow'. Finally, added day/night bands to the plots. All contributed
by Matthew Wall. Thanks again, Matthew!

Ordinal wind directions can now be shown, just by adding the tag suffix
".ordinal_compass". For example, $current.windDir.ordinal_compass might show
'SSE' The abbreviations are set in the skin configuration file.

Fixed bug that caused rain totals to be misreported to Weather Underground when
using a metric database.

Generalized the weewx machinery so it can be used for applications other than
weather applications.

Got rid of option stats_types in weewx.conf and put it in
bin/user/schemas.py. See upgrading.html if you have a specialized stats
database.

The stats database now includes an internal table of participating observation
types. This allows it to be easily combined with the archive database, should
you choose to do so. The table is automatically created for older stats
databases.

Added rain rate calculation to FineOffsetUSB driver.  Added adaptive polling
option to FineOffsetUSB driver.  Fixed barometric pressure calculation for
FineOffsetUSB driver.

Changed the name of the utilities, so they will be easier to find in /usr/bin:
  weewxd.py          -> weewxd
  runreports.py      -> wee_reports
  config_database.py -> wee_config_database
  config_vp.py       -> wee_config_vantage
  config_fousb.py    -> wee_config_fousb

### 2.1.1 01/02/13

Fixed bug that shows itself when one of the variables is 'None' when
calculating a trend.

### 2.1.0 01/02/13

Now supports the Oregon Scientific WMR918/968 series, courtesy of user
William Page. Thanks, William!!

Now supports the Fine Offset series of weather stations, thanks to user
Matthew Wall. Thanks, Matthew!!

Now includes a Redhat init.d script, contributed by Mark Jenks. Thanks,
Mark!!

Added rsync report type as an alternative to the existing FTP report.
Another thanks to William Page!

Fill color for bar charts can now be specified separately from the outline
color, resulting in much more attractive charts. Another thanks to Matthew
Wall!!

Added a tag for trends. The barometer trend can now be returned as
$trend.barometer. Similar syntax for other observation types.

config_vp.py now returns the console version number if available (older
consoles do not offer this).

Hardware dewpoint calculations with the WMR100 seem to be unreliable below
about 20F, so these are now done in software. Thanks to user Mark Jenks for
sleuthing this.

### 2.0.2 11/23/12

Now allows both the archive and stats data to be held in the same database.

Improved chances of weewx.Archive being reused by allowing optional table
name to be specified.

### 2.0.1 11/05/12

Fixed problem with reconfiguring databases to a new unit system.

### 2.0.0 11/04/12

A big release with lots of changes. The two most important are the support
of additional weather hardware, and the support of the MySQL database.

All skin configurations are backwardly compatible, but the configuration
file, weewx.conf, is not. The install utility setup.py will install a fresh
version, which you will then have to edit by hand.

If you have written a custom service, see the upgrade guide on how to port
your service to the new architecture.

Added the ability to generate archive records in software, thus opening the
door for supporting weather stations that do not have a logger.

Support for the Oregon Scientific WMR100, the cheapest weather station I
could find, in order to demonstrate the above!

Added a software weather station simulator.

Introduced weedb, a database-independent Python wrapper around sqlite3 and
MySQLdb, which fixes some of their flaws.

Ported everything to use weedb, and thus MySQL (as well as sqlite)

Internally, the databases can now use either Metric units, or US Customary.
NB: you cannot switch systems in the middle of a database. You have to
stick to one or other other. However, the utility config_database.py does
have a reconfigure option that allows copying the data to a new database,
performing the conversion along the way. See the Customization Guide.

You can now use "mmHg" as a unit of pressure.

Added new almanac information, such as first and last quarter moons, and
civil twilight.

Changed the engine architecture so it is more event driven. It now uses
callbacks, making it easier to add new event types.

Added utility config_vp.py, for configuring the VantagePro hardware.

Added utility config_database.py, for configuring the databases.

Made it easier to write custom RESTful protocols. Thanks to user Brad, for
the idea and the use case!

The stats type 'squarecount' now contains the number of valid wind
directions that went into calculating 'xsum' and 'ysum'. It used to be the
number of valid wind speeds. Wind direction is now calculated using
'squarecount' (instead of 'count').

Simplified and reduced the memory requirements of the CRC16 calculations.

Improved test suites.

Lots of little nips and tucks here and there, mostly to reduce the coupling
between different modules. In particular, now a service generally gets
configured only using its section of weewx.conf.

I also worked hard at making sure that cursors, connections, files, and
lots of other bits and pieces get properly closed instead of relying on
garbage collection. Hopefully, this will reduce the long-term growth of
memory usage.

### 1.14.1 07/06/12

Hardened retry strategy for the WeatherLink IP. If the port fails to open
at all, or a socket error occurs, it will thrown an exception (resulting in
a retry in 60 seconds). If a socket returns an incomplete result, it will
continue to retry until everything has been read.

Fixed minor bug that causes the reporting thread to prematurely terminate
if an exception is thrown while doing an FTP.

### 1.14.0 06/18/12

Added smartphone formatted mobile webpage, contributed by user Torbjörn
Einarsson. If you are doing a fresh install, then these pages will be
generated automatically. If you are doing an upgrade, then see the upgrade
guide on how to have these webpages generated. Thanks, Tobbe!

Three changes suggested by user Charlie Spirakis: o Changed umask in
daemon.py to 0022; o Allow location of process ID file to be specified on
the command line of weewx; o Start script allows daemon to be run as a
specific user. Thanks, Charlie!

Corrected bug in humidity reports to CWOP that shows itself when the
humidity is in the single digits.

Now includes software in CWOP APRS equipment field.

### 1.13.2 05/02/12

Now allows CWOP stations with prefix 'EW'.

Fixed bug that showed itself in the line color with plots with 3 or more
lines.

Changed debug message when reaching the end of memory in the VP2 to
something slightly less alarming.

### 1.13.1 03/25/12

Added finer control over the line plots. Can now add optional markers. The
marker_type can be 'none' (the default), 'cross', 'box', 'circle', or 'x'.
Also, line_type can now either be 'solid' (the default) or 'none' (for
scatter plots). Same day I'll add 'dashed', but not now. :-)

Conditionally imports sqlite3. If it does not support the "with" statement,
then imports pysqlite2 as sqlite3.

### 1.13.0 03/13/12

The binding to the SQL database to be used now happens much later when
running reports. This allows more than one database to be used when running
a report. Extra databases can be specified in the option list for a report.
I use this to display broadband bandwidth information, which was collected
by a separate program. Email me for details on how to do this. Introducing
this feature changed the signature of a few functions. See the upgrade
guide for details.

### 1.12.4 02/13/12

User Alf Høgemark found an error in the encoding of solar data for CWOP
and sent me a fix. Thanks, Alf!

Now always uses "import sqlite3", resulting in using the version of
pysqlite that comes with Python. This means the install instructions have
been simplified.

Now doesn't choke when using the (rare) Python version of NameMapper used
by Cheetah.

### 1.12.3 02/09/12

Added start script for FreeBSD, courtesy of user Fabian Abplanalp. Thanks,
Fabian!

Added the ability to respond to a "status" query to the Debian startup
script.

RESTful posts can now recover from more HTTP errors.

Station serial port can now recover from a SerialException error (usually
caused when there is a process competing for the serial port).

Continue to fiddle with the retry logic when reading LOOP data.

### 1.12.2 01/18/12

Added check for FTP error code '521' to the list of possibilities if a
directory already exists. Thanks to user Clyde!

More complete information when unable to load a module file. Thanks, Jason!

Added a few new unit types to the list of possible target units when using
explicit conversion. Thanks, Antonio!

Discovered and fixed problem caused by the Davis docs giving the wrong
"resend" code (should be decimal 21, not hex 21).

Improved robustness of VantagePro configuration utility.

Fixed problem where an exception gets thrown when changing VP archive
interval.

Simplified some of the logic in the VP2 driver.

### 1.12.1 11/03/11

Now corrects for rain bucket size if it is something other than the
standard 0.01 inch bucket.

### 1.12.0 10/29/11

Added the ability to change bucket type, rain year start, and barometer
calibration data in the console using the utility configure.py. Added
option "--info", which queries the console and returns information about
EEPROM settings. Changed configure.py so it can do hardware-specific
configurations, in anticipation of supporting hardware besides the Davis
series.

Reorganized the documentation.

### 1.11.0 10/06/11

Added support for the Davis WeatherLinkIP. Thanks, Peter Nock and Travis
Pickle!

Added support for older Rev A type archive records.

Added patch from user Dan Haller that sends UV and radiation data to the
WeatherUnderground if available. Thanks, Dan!

Added patch from user Marijn Vriens that allows fallback to the version of
pysqlite that comes with many versions of Python. Thanks, Marijn!

Now does garbage collection after an archive record is obtained and before
the main loop is restarted.

### 1.10.2 04/14/11

Added RA and declination for the Sun and Moon to the Daily Almanac. Equinox
and solstice are now displayed in chronological order. Same with new and
full moons.

Examples alarm.py and lowBattery.py now include more error checks, allow an
optional 'subject' line to the sent email, and allow a comma separated list
of recipients.

### 1.10.1 03/30/11

Substitutes US Units if a user does not specify anything (instead of
exception KeyError).

Almanac uses default temperature and pressure if they are 'None'.

Prettied up web page almanac data in the case where pyephem has not been
installed.

Fixed up malformed CSS script weewx.css.

### 1.10.0 03/29/11

Added extensive almanac information if the optional package 'pyephem' has
been installed

Added a weewx "favorite icon" favicon.ico that displays in your browser
toolbar.

Added a mobile formatted HTML page, courtesy of user Vince Skahan (thanks,
Vince!!).

Tags can now be ended with a unit type to convert to a new unit. For
example, say your pressure group ("group_pressure") has been set to show
inHg. The normal tag notation of "$day.barometer.avg" will show something
like "30.05 inHg". However, the tag "$day.barometer.avg.mbar" will show
"1017.5 mbar".

Added special tag "exists" to test whether an observation type exists.
Example "$year.foo.exists" will return False if there is no type "foo" in
the statistical database.

Added special tag "has_data" to test whether an observation type exists and
has a non-zero number of data points over the aggregation period. For
example, "$year.soilMoist1.has_data" will return "True" if soilMoist1 both
exists in the stats database and contains some data (meaning, you have the
hardware).

Y-axis plot labels (such as "°F") can now be overridden in the plot
configuration section of skin.conf by using option "y_label".

Added executable module "runreports.py" for running report generation only.

Added package "user", which can contain any user extensions. This package
will not get overridden in the upgrade process.

Added the ability to reconfigure the main database, i.e., add or drop data
types. Along the same line, statistical types can also be added or dropped.
Email me for details on how to do this.

Now makes all of the LOOP and archive data available to services. This
includes new keys:

 LOOP data: 'extraAlarm1' 'extraAlarm2' 'extraAlarm3' 'extraAlarm4'
'extraAlarm5' 'extraAlarm6' 'extraAlarm7' 'extraAlarm8' 'forecastIcon'
'forecastRule' 'insideAlarm' 'outsideAlarm1' 'outsideAlarm2' 'rainAlarm'
'soilLeafAlarm1' 'soilLeafAlarm2' 'soilLeafAlarm3' 'soilLeafAlarm4'
'sunrise' 'sunset'

 Archive data: 'forecastRule' 'highOutTemp' 'highRadiation' 'highUV'
'lowOutTemp'

Started a more formal test suite. There are now tests for the report
generators. These are not included in the normal distribution, but can be
retrieved from SourceForge via svn.

### 1.9.3 02/04/11

Now correctly decodes temperatures from LOOP packets as signed shorts
(rather than unsigned).

Now does a CRC check on LOOP data.

Changed VantagePro.accumulateLoop to make it slightly more robust.

### 1.9.2 11/20/10

Now catches exception of type OverflowError when calculating celsius
dewpoint. (Despite the documentation indicating otherwise, math.log() can
still throw an OverflowError)

Fixed bug that causes crash in VantagePro.accumulateLoop() during fall DST
transition in certain situations.

VP2 does not store records during the one hour fall DST transition.
Improved logic in dealing with this.

Changed install so that it backs up the ./bin subdirectory, then overwrites
the old one. Also, does not install the ./skins subdirectory at all if one
already exists (thus preserving any user customization).

### 1.9.1 09/09/10

Now catches exceptions of type httplib.BadStatusLine when doing RESTful
posts.

Added an extra decimal point of precision to dew point reports to the
Weather Underground and PWS.

### 1.9.0 07/04/10

Added a new service, StdQC, that offers a rudimentary data check.

Corrected error in rain year total if rain year does not start in January.

Moved option max_drift (the max amount of clock drift to tolerate) to
section [Station].

Added check for a bad storm start time.

Added checks for bad dateTime.

Simplified VantagePro module.

### 1.8.4 06/06/10

Fixed problem that shows itself if weewx starts up at precisely the
beginning of an archive interval. Symptom is max recursion depth exceeded.

Units for UV in LOOP records corrected. Also, introduced new group for UV,
group_uv_index. Thanks to user A. Burriel for this fix!

### 1.8.3 05/20/10

Problem with configuring archive interval found and fixed by user A.
Burriel (thanks, Antonio!)

### 1.8.2 05/09/10

Added check to skip calibration for a type that doesn't exist in LOOP or
archive records. This allows windSpeed and windGust to be calibrated
separately.

### 1.8.1 05/01/10

Ported to Cheetah V2.4.X

### 1.8.0 04/28/10

Added CWOP support.

Storage of LOOP and archive data into the SQL databases is now just another
service, StdArchive.

Added a calibration service, StdCalibrate, that can correct LOOP and
archive data.

Average console battery voltage is now calculated from LOOP data, and saved
to the archive as 'consBatteryVoltage'.

Transmitter battery status is now ORd together from LOOP data, and saved to
the archive as 'txBatteryStatus'.

Added stack tracebacks for unrecoverable exceptions.

Added a wrapper to the serial port in the VantagePro code. When used in a
Python "with" statement, it automatically releases the serial port if an
exception happens, allowing a more orderly shutdown.

Offered some hints in the documentation on how to automount your VP2 when
using a USB connection.

Corrected error in units. getTargetType() that showed itself with when the
console memory was freshly cleared, then tried to graph something
immediately.

### 1.7.0 04/15/10

Big update.

Reports now use skins for their "look or feel." Options specific to the
presentation layer have been moved out of the weewx configuration file
'weewx.conf' to a skin configuration file, 'skin.conf'. Other options have
remained behind.

Because the configuration file weewx.conf was split, the installation
script setup.py will NOT merge your old configuration file into the new
one. You will have to reedit weewx.conf to put in your customizations.

FTP is treated as just another report, albeit with an unusual generator.
You can have multiple FTP sessions, each to a different server, or
uploading to or from a different area.

Rewrote the FTP upload package so that it allows more than one FTP session
to be active in the same local directory. This version also does fewer hits
on the server, so it is significantly faster.

The configuration files weewx.conf and skin.conf now expect UTF-8
characters throughout.

The encoding for reports generated from templates can be chosen. By
default, the day, week, month, and year HTML files are encoded using HTML
entities; the NOAA reports encoded using 'strict ascii.' Optionally,
reports can be encoded using UTF-8.

Revamped the template formatting. No longer use class ModelView. Went to a
simpler system built around classes ValueHelper and UnitInfo.

Optional formatting was added to all tags in the templates. There are now
optional endings: 'string': Use specified string for None value.
'formatted': No label. 'format': Format using specified string format.
'nolabel': Format using specified string format; no label. 'raw': return
the underlying data with no string formatting or label.

For the index, week, month, and year template files, added conditional to
not include ISS extended types (UV, radiation, ET) unless they exist.

Added an RSS feed.

Added support for PWSweather.com

Both WeatherUnderground and PWSweather posts are now retried up to 3 times
before giving up.

Now offer a section 'Extras' in the skin configuration file for including
tags added by the user. As an example, the tag radar_url has been moved
into here.

Data files used in reports (such as weewx.css) are copied over to the HTML
directory on program startup.

Included an example of a low-battery alarm.

Rearranged distribution directory structure so that it matches the install
directory structure.

Moved base temperature for heating and cooling degree days into skin.conf.
They now also require a unit.

Now require unit to be specified for 'altitude'.

### 1.5.0 03/07/10

Added support for other units besides the U.S. Customary. Plots and HTML
reports can be prepared using any arbitrary combination of units. For
example, pressure could be in millibars, while everything else is in U.S.
Customary.

Because the configuration file weewx.conf changed significantly, the
installation script setup.py will NOT merge your old configuration file
into the new one. You will have to reedit weewx.conf to put in your
customizations.

Added an exception handler for exception OSError, which is typically thrown
when another piece of software attempts to access the same device port.
Weewx catches the exception, waits 10 seconds, then starts again from the
top.

### 1.4.0 02/22/10

Changed the architecture of stats.py to one that uses very late binding.
The SQL statements are not run until template evaluation. This reduces the
amount of memory required (by about 1/2), reduces memory fragmentation, as
well as greatly simplifying the code (file stats.py shed over 150 lines of
non-test code). Execution time is slightly slower for NOAA file generation,
slightly faster for HTML file generation, the same for image generation,
although your actual results will depend on your disk speed.

Now possible to tell weewx to reread the configuration file without
stopping it. Send signal HUP to the process.

Added option week_start, for specifying which day a calendar week starts
on. Default is 6 (Sunday).

Fixed reporting bug when the reporting time falls on a calendar month or
year boundary.

### 1.3.4 02/08/10

Fixed problem when plotting data where all data points are bad (None).

### 1.3.3 01/10/10

Fixed reporting bug that shows itself if rain year does not start in
January.

### 1.3.2 12/26/09

LOOP data added to stats database.

### 1.3.1 12/22/09

Added a call to syslog.openlog() that inadvertently got left out when
switching to the engine driven architecture.

### 1.3.0 12/21/09

Moved to a very different architecture to drive weewx. Consists of an
engine, that manages a list of 'services.' At key events, each service is
given a chance to participate. Services are easy to add, to allow easy
customization. An example is offered of an 'alarm' service.

Checking the clock of the weather station for drift is now a service, so
the option clock_check was moved from the station specific [VantagePro]
section to the more general [Station] section.

Added an example service 'MyAlarm', which sends out an email should the
outside temperature drop below 40 degrees.

In a similar manner, all generated files, images, and reports are the
product of a report engine, which can run any number of reports. New
reports are easily added.

Moved the compass rose used in progressive vector plots into the interior
of the plot.

Install now deletes public_html/#upstream.last, thus forcing all files to
be uploaded to the web server at the next opportunity.

### 1.2.0 11/22/09

Added progressive vector plots for wind data.

Improved axis scaling. The automatic axis scaling routine now does a better
job for ranges less than 1.0. The user can also hardwire in min and max
values, as well as specify a minimum increment, through parameter 'yscale'
in section [Images] in the configuration file.

Now allows the same SQL type to be used more than once in a plot. This
allows, say, instantaneous and average wind speed to be shown in the same
plot.

Rain year is now parameterized in file templates/year.tmpl (instead of
being hardwired in).

Now does LOOP caching by default.

When doing backfilling to the stats database, configure now creates the
stats database if it doesn't already exist.

setup.py now more robust to upgrading the FTP and Wunderground sections

### 1.1.0 11/14/09

Added the ability to cache LOOP data. This can dramatically reduce the
number of writes to the stats database, reducing wear on solid-state disk
stores.

Introduced module weewx.mainloop. Introduced class weewx.mainloop.MainLoop
This class offers many opportunities to customize weewx through
subclassing, then overriding an appropriate member function.

Refactored module weewx.wunderground so it more closely resembles the
(better) logic in wunderfixer.

setup.py no longer installs a daemon startup script to /etc/init.d. It must
now be done by hand.

setup.py now uses the 'home' value in setup.cfg to set WEEWX_ROOT in
weewx.conf and in the daemon start up scripts

Now uses FTP passive mode by default.

### 1.0.1 11/09/09

Fixed bug that prevented backfilling the stats database after modifying the
main archive.

### 1.0.0 10/26/09

Took the module weewx.factory back out, as it was too complicated and hard
to understand.

Added support for generating NOAA monthly and yearly reports. Completely
rewrote the filegenerator.py module, to allow easy subclassing and
specialization.

Completely rewrote the stats.py module. All aggregate quantities are now
calculated dynamically.

Labels for HTML generation are now held separately from labels used for
image generation. This allows entities such as '&deg;' to be used for the
former.

LOOP mode now requests only 200 LOOP records (instead of the old 2000). It
then renews the request should it run out. This was to get around an
(undocumented) limitation in the VP2 that limits the number of LOOP records
that can be requested to something like 220. This was a problem when
supporting VP2s that use long archive intervals.

Cut down the amount of computing that went on before the processing thread
was spawned, thus allowing the main thread to get back into LOOP mode more
quickly.

Added type 'rainRate' to the types decoded from a Davis archive record. For
some reason it was left out.

Added retries when doing FTP uploads. It will now attempt the upload
several times before giving up.

Much more extensive DEBUG analysis.

Nipped and tucked here and there, trying to simplify.

### 0.6.5 10/11/09

Ported to Cheetah V2.2.X. Mostly, this is making sure that all strings that
cannot be converted with the 'ascii' codec are converted to Unicode first
before feeding to Cheetah.

### 0.6.4 09/22/09

Fixed an error in the calculation of heat index.

### 0.6.3 08/25/09

FTP transfers now default to ACTIVE mode, but a configuration file option
allows PASSIVE mode. This was necessary to support Microsoft FTP servers.

### 0.6.2 08/01/09

Exception handling in weewx/ftpdata.py used socket.error but failed to
declare it. Added 'import socket' to fix.

Added more complete check for unused pages in weewx/VantagePro.py. Now the
entire record must be filled with 0xff, not just the time field. This fixes
a bug where certain time stamps could look like unused records.

### 0.6.1 06/22/09

Fixed minor ftp bug.

### 0.6.0 05/20/09

Changed the file, imaging, ftping functions into objects, so they can be
more easily specialized by the user.

Introduced a StationData object.

Introduced module weewx.factory that produces these things, so the user has
a place to inject his/her new types.

### 0.5.1 05/13/09

1. Weather Underground thread now run as daemon thread, allowing the
program to exit even if it is running.

2. WU queue now hold an instance of archive and the time to be published,
rather than a record. This allows dailyrain to be published as well.

3. WU date is now given in the format "2009-05-13+12%3A35%3A00" rather than
"2009-05-13 12:35:00". Seems to be more reliable. But, maybe I'm imagining
things...

