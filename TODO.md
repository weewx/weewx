# To do

Think about how `WEEWX_ROOT` is defined.

## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"? If the last, then the Debian
install instructions should become 

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list


## Utilities

- Lot of inconsistencies in how the path to the config file is handled. Some utilities accept a
  command line option, others require `--config=`.
- Allow rebuild daily summaries for only selected types.
- Check semantics of specifying a time for `--from` and/or `--to` 
  in `weectl database calc-missing`.


## Logging

Log to `~/weewx-data/log/weewx.log`.

Update the logging wiki.

## Website

Change the forwarding `.htm` files in `weewx.com/docs` to point to the V5 versions.

## Docs

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.

Check usersguide/troubleshooting/software.md.


## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL, this time
by using `weectl database transfer`.