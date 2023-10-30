# V5.0 "To Do"


## Package installers

Convert `WEEWX_ROOT=/` to`WEEWX_ROOT=/etc/weewx` when upgrading.

Copy `/usr/share/weewx/user` to `/etc/weewx/user` when upgrading, then move the 
old one aside with a label.

## `weectl`

When doing a `weectl station create`, selectively copy what's in the `util`
subdirectory to `~/weewx-data`. We only want
- `import`
- `systemd`
- `launchd`
- `udev`


## Drivers

The `fousb` driver needs to be ported to Python 12.


## Docs

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.

Need a page on how to provision a second instance, for both a pip install and a
package install.



# Before final release

## `pyproject.toml`

Change parameter `description`.

## Logging

Update the logging wiki.

## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

