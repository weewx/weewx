# V5.0 "To Do"


## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"? If the last, then the Debian
install instructions should become 

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list


## Utilities


## Docs

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.

Need a page on how to provision a second instance.



# Before final release

## `pyproject.toml`

Change parameter `description`.

## Logging

Update the logging wiki.

## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL,
this time by using `weectl database transfer`.

