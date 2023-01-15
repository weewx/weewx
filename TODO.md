# To do


## Configuration related

Get config update working again. 

Remove wunderfixer. Remove references in docs.

Change `bin/user.py` to `lib/user.py`. This would require that the installer intercept paths
with `bin` in them and change them to `lib`.

## Daemon


## Commands
```
✅ weectl station create
✅ weectl station reconfigure
½ weectl station upgrade
weectl station upgrade-skins
½ weectl daemon install
weectl daemon uninstall
✅ weectl extension install
✅ weectl extension uninstall
✅ weectl extension list
✅ weectl extension transfer
```
Key: 
✅ means largely completed
½ means started

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.

Update the logging wiki.


## Build and distribution


## Documentation

Update internal links in the customizing guide.

Update internal links in the User's Guide.

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Define $WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

References to `/home/weewx` become `$WEEWX_ROOT`

Put legacy (V4.x) docs at weewx.com/legacy_docs.

Warn the user to make sure that  `~/.local/bin` is in `PATH`.

On minimal installations, a pip install may require:

```
sudo apt install gcc
sudo apt install python3-dev
```

## Testing


## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.

Guide on how to migrate to V5. (In progress)


## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549