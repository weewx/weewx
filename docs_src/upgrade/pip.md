# Upgrade using pip

!!! Note
    If you are upgrading from an old `setup.py` installation, see the
    instructions <a href="https://github.com/weewx/weewx/wiki/v5-upgrade"><em>Migrating setup.py installs to Version 5.0</em></a>.

To upgrade a pip installation:

```
pip install weewx --upgrade --user
```

You may then wish to upgrade your configuration file, documentation, examples,
and daemon utility files by using the tool `weectl`:

````
weectl station upgrade
```

You may also want to upgrade your skins, although this may break any
modifications you have made to them. Your old skins will be saved in a
timestamped directory.

```
weectl station upgrade --what skins
```

Finally, restart WeeWX.
