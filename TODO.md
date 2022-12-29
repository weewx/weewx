# To do


## Configuration related

Get config update working again. 

## Commands
```
weectl station create
weectl station reconfigure
weectl station upgrade
weectl station upgrade-skins
weectl daemon install
weectl daemon uninstall
weectl extension install
weectl extension uninstall
weectl extension list
```

## Documentation

Update "where to find things" in user's guide.

Update install documentation. Replace setup.py guide with a pip guide.

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

## Testing


## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.