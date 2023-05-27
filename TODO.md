# To do



## Debian packaging

Right now, the depository is for a "squeeze" and "buster" distribution. Do we keep adding them
("bullseye", "bookworm", etc.)? Or, do we just use "stable"?

Test upgrade process.
- Upgrade from v4 Python 2
- Upgrade from v4 Python 3
- Upgrade from V5 to a later V5

Input validation when provisioning Debian. Not sure how to do that for db_input when it might
come from a script, not a human.

## Upgrade guide

How to switch from init.d to systemd.
c
How to upgrade from V4 using Python 2, to V5 using Python 3.


## Utilities

Lot of inconsistencies in how the path to the config file is handled. Some utilities accept a
command line option, others require `--config=`.

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.

Update the logging wiki.


## Documentation


Put legacy (V4.x) docs at weewx.com/legacy_docs.

Change Debian install instructions to

    echo "deb [arch=all] http://weewx.com/apt/python3 stable main" | sudo tee /etc/apt/sources.list.d/weewx.list



## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549