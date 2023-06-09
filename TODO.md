# To do


## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"? If the last, then the Debian
install instructions should become 

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list

## Pip install

In anticipation of Debian 12, default pip install should use a virtual environment, not a `--user` 
flag.

## Upgrade guide

How to switch from init.d to systemd.

How to upgrade from V4 using Python 2, to V5 using Python 3.


## Utilities

Lot of inconsistencies in how the path to the config file is handled. Some utilities accept a
command line option, others require `--config=`.

## Logging

Log to `~/weewx-data/log/weewx.log`.

Update the logging wiki.

## Website

Change the forwarding `.htm` files in `weewx.com/docs` to point to the V5 versions.

## Docs

do a pass through the old docs for all of the 'id' references, and ensure that
they have been inserted into the new markdown docs.
