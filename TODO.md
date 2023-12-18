# V5.0 "To Do"

## startup

- tk eliminate daemonize.py
- tk before logger is initialized, output to stdout/stderr as appropriate

## Package installers

- mw verify upgrade behavior on skin files in /etc/weewx/skins.  do the non-
    modified skin files get upgraded from apt/yum?
- mw see if backport of importlib.resources exists for suse 15 and rocky8 for
    python 3.6
- mw ensure that maintainer's version of weewx.conf is created but no used
  ensure that existing weewx.conf is not overwritten
    /etc/weewx/weewx.conf - untouched config
    /etc/weewx/weewx.conf-OLD-LATEST - maintainer; 'weewctl upgrade'
    /etc/weewx/weewx.conf-LATEST - distribution
  update the docs (each quickstart) to make this process explicit

## Testing

- mw convert to pytest
- mw Automate the testing of install/upgrade/uninstall for each installation
    method using vagrant


## Drivers

- mw The `fousb` driver needs to be ported to Python 12.  post weewx 5.0 release


## Docs

- tk update docs to reflect use of standalone logging
  - each quickstart page
  - where-to-find-things in users guide
  - running-weewx section of users guide



# Before final release

## `pyproject.toml`

Change parameter `description`.


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

