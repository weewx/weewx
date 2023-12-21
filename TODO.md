# V5.0 "To Do"

## startup

- tk eliminate daemonize.py
- tk before logger is initialized, output to stdout/stderr as appropriate
- tk Rationalize startup procedure, making it consistent.


## Package installers

- mw verify upgrade behavior on skin files in /etc/weewx/skins.  do the non-
    modified skin files get upgraded from apt/yum?

## Testing

- mw convert to pytest
- mw Automate the testing of install/upgrade/uninstall for each installation
    method using vagrant


## Drivers

- mw The `fousb` driver needs to be ported to Python 12.  post weewx 5.0 release


## Docs

- tk update docs to reflect that Python 3.6 is now supported.


# Before final release

## `pyproject.toml`

Change parameter `description`.


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

