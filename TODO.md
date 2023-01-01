# To do


## Configuration related

Get config update working again. 

## Daemon

Do we need the `--type` option for `weectl daemon install`? Can we make decisions on the basis
of the OS encountered?


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
```
Key: 
✅ means largely completed
½ means started

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.


## Documentation

Update "where to find things" in user's guide.

Update install documentation. Replace setup.py guide with a pip guide.

Update MacOS install instructions. Are they needed now that a pip install can be done?

Get rid of Python 2 install instructions.

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

## Testing


## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.