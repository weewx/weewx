Document the suffixes `.exists` and `.has_data`.

Explore using the Python `logging` facility instead of `syslog`.

Track down all usages of
``` 
weeutil.weeutil.search_up
weeutil.weeutil.accumulateLeaves
weeutil.weeutil.merge_config
weeutil.weeutil.patch_config
weeutil.weeutil.comment_scalar
weeutil.weeutil.conditional_merge
```
and change them to use `weeutil.conf` instead.


Explore introducing extendable observation types. They would be registered
with `Manager`.

The following drivers have been checked under Python 3:

```
vantage.py
wmr100.py
```

In general, we should expect the user to run the command `python`, whatever that might
point to. On some systems, it will be Python 2, others Python 3.

Nevertheless, we should probably include a section on how to run explicitly under 
Python 2 vs 3.

Update macos.htm for how to install using Python 3.

Update redhat.htm for how to install using Python 3.

Update suse.htm for how to install using Python 3.