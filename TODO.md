# To do

Think about how `WEEWX_ROOT` is defined.

What is the subdirectory `user`? Is it station data, and therefore should be
located under `~/weewx-data`? Or, is it code, and should be installed in the 
virtual environment? Same issue with a package install.


## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"? If the last, then the Debian
install instructions should become 

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list


## Utilities

- Allow rebuild daily summaries for only selected types.
- Check semantics of specifying a time for `--from` and/or `--to` 
  in `weectl database calc-missing`.


## Logging

Log to `~/weewx-data/log/weewx.log`.

Update the logging wiki.

## Docs

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL, this time
by using `weectl database transfer`.

# Before release

## Website

Change the forwarding `.htm` files in `weewx.com/docs` to point to the V5 versions.

## `pyproject.toml`
Change parameter `description`.

