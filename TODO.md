# To do


## Configuration related

Get config update working again. 

Remove wunderfixer. Remove references in docs.

## Daemon

Do we need the `--type` option for `weectl daemon install`? Can we make decisions on the basis
of the OS encountered?

How to get around the problem that pipx isolates its VE from pip's? This requires that
a dependency, such as `requests`, get installed as

    pipx weewx inject requests

Can we use a regular venv VE? Does it see pip --user installs?

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

New guide for weectl.

Update utilities guide. Remove references to wee_config wee_extension from it.

Update internal links in the customizing guide.

Update internal links in the User's Guide.

Update install documentation. Replace setup.py guide with a pip guide (in progress)

Check whether we need macOS install instructions any longer. Probably not: pip install supercedes
them.

Get rid of Python 2 install instructions wherever they occur.

Use a dollar sign when referring to symbolic names. For example, $WEEWX_ROOT instead of WEEWX_ROOT.

Define $WEEWX_ROOT.

Note that SQLITE is now relative to WEEWX_ROOT.

References to `/home/weewx` become `$WEEWX_ROOT`

Put legacy (V4.x) docs at weewx.com/legacy_docs.

Update instructions on how to install the necessary daemon files. See `usersguide/running-weewx`.

## Testing


## Upgrade guide

Note that SQLITE is now relative to WEEWX_ROOT.

Note the change in the weedb.sqlite API. Can't imagine it will affect anyone.

Installs to ~/weewx-data now.

Guide on how to migrate to V5. (In progress)


## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549