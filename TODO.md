# V5.0 "To Do"


## Package installers

Right now, the Debian depository is for a "squeeze" and "buster" distribution.
Do we keep adding them ("bullseye", "bookworm", etc.)? Or, do we just use
"stable"? If the last, then the Debian install instructions should become

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list

Right now, the function `weewx.read_config()` will convert `WEEWX_ROOT=/` to
`WEEWX_ROOT=/etc/weewx` at runtime. Is there a way to do this when upgrading?

Can we copy `/usr/share/weewx/user` to `/etc/weewx/user` when upgrading? Then
delete the former.

Any reason why we can't use `weectl station create` to populate `/etc/weewx`
instead of custom shell scripts?


## Utilities


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

