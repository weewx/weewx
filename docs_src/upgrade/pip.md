# Upgrade using pip

!!! Note
    If you are upgrading from an old `setup.py` installation, see the
    instructions <a href="https://github.com/weewx/weewx/wiki/v5-upgrade"><em>Migrating setup.py installs to Version 5.0</em></a>.

To upgrade a WeeWX installation that was installed using pip:
```
pip install weewx --upgrade --user
```

Optional: You may want to upgrade your documentation and examples.
```
weectl station upgrade --what docs examples util
```

Optional: You may want to upgrade your skins, although this may break or
remove modifications you have made to them. Your old skins will be saved
in a timestamped directory.
```
weectl station upgrade --what skins
```

Optional: You may want to upgrade your configuration file.  This is only
necessary in the rare case that a new WeeWX release is not backward
compatible with older configuration files.
```
weectl station upgrade --what config
```

Finally, restart WeeWX.
