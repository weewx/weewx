### Logging
Refactor wee_import to use the new logging facility.

Update *Upgrading Guide*.


### Other
Document the suffixes `.exists` and `.has_data`.

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