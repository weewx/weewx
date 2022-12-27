# To do

## For the poetry implementation

Applications need to be converted into poetry scripts.

## Configuration related

Change default directory to `~/weewx-data`.

Check for validity of station_url.

SQLITE_ROOT is now relative to WEEWX_ROOT.

Get rid of all the config update stuff.


## Obsolete

Make sure distutil isn't used anywhere. E.g., `distutils.copytree()`.

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

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

## Testing

Try doctest in `manager.py`.

## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.