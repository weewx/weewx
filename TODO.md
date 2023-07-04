# To do

## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"? If the last, then the Debian
install instructions should become 

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list

## Utilities

Lot of inconsistencies in how the path to the config file is handled. Some utilities accept a
command line option, others require `--config=`.

Finish migrating `wee_database` to `weectl database`
- I think we can do without `check-strings` and `fix-strings`.
- "Usage" strings are inconsistent between the commands. 
  E.g., compare `weectl station --help` with `weectl database --help`
- Allow rebuild daily summaries for only selected types.
- Edit documentation to show `weectl database` instead.
- Check semantics of specifying a time for `--from` and/or `--to` 
  in `weectl database calc-missing`.
- Change `weectl station` and `weectl extension` documentation to follow
  the style of `weectl database`.
- Remove old `wee_database` references.

## Logging

Log to `~/weewx-data/log/weewx.log`.

Update the logging wiki.

## Website

Change the forwarding `.htm` files in `weewx.com/docs` to point to the V5 versions.

## Docs

do a pass through the old docs for all of the 'id' references, and ensure that
they have been inserted into the new markdown docs.

why install gcc for a pip install?  that is a massive dependency!
same for the python-dev/devel.  should just use wheels.  only install gcc
and the dev stuff it the os does not have wheels in pypi. [Fixed by no longer requiring rsa].

need to verify the suse pip pre-requisite steps. [Done by tk]

need to verify method for installing latest python in rocky 8.  default is
python 3.6.8. [Done by tk]

need a page that shows how to download, install, and configure a driver.

need a page that shows how to download, install, and configure a skin.

web browsers do not expand the tilde [Chrome does; Firefox does not.]

## Wiki

Update the wiki entries for going from MySQL to SQLite and for SQLite to MySQL, this time
by using `weectl database transfer`.