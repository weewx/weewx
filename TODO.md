# To do


## Configuration related


## Daemon


## Commands
```
✅ weectl station create
✅ weectl station reconfigure
✅ weectl station upgrade
✅ weectl station upgrade-skins
✅ weectl extension install
✅ weectl extension uninstall
✅ weectl extension list
✅ weectl extension transfer
```
Key: 
✅ means completed
½ means started

## Utilities

Get the following working again:

- wee_database
- wee_debug
- wee_device
- wee_import
- wee_reports

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.

Update the logging wiki.


## Build and distribution


## Documentation

Fill out "Preparation" section in pip.md for RedHat, SuSE, and macOS.

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Define $WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

Put legacy (V4.x) docs at weewx.com/legacy_docs.


## Testing


## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.

Guide on how to migrate to V5. (In progress)


## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549