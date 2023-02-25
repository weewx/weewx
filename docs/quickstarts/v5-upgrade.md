# Migrating `setup.py` installs to Version 5.0

This is a guide for migrating V4.x installations that were installed using the `setup.py` method,
to Version 5.0.

## Code vs user data
With V5.0, there is now a clean separation between *WeeWX code*, and *user data*. They are stored
in separate areas, rather than everything under `/home/weewx`.

### WeeWX code
With one exception, the software used by the WeeWX application is now kept in the normal Python
directories, rather than under `/home/weewx/bin`. This software includes:

- Executables such as `weewxd` and `wee_reports`;
- Their libraries.

### User data
By contrast, *user data* is specific to your station. By default, it is now stored in your
home directory in `~/weewx-data`, although you may continue to use your old user data located in
`/home/weewx` by following this guide. User data includes:

* The configuration file, `weewx.conf`;
* Skins;
* Database;
* Generated HTML files and images; and
* Extensions (Python code specific to a station).

## Using your old `/home/weewx`
With this in mind, here is how you can continue to use the old user data in `/home/weewx`.
The code will be replaced by new code.

1. Install V5.0 by using the tool `pip`. (You can find more details in the document 
   [_Installation using pip_](pip.md), but note that you are *only going to follow step 1*.
   Do not do step 2.)

    ```shell
    python3 -m pip install weewx --user
    ```

    When you are done, the new V5.0 executable will be in `~/.local/bin/weewxd`,
    rather than the more familiar V4.x location `/home/weewx/bin/weewxd`.

2. You do not have to do Step 2, provision a new station, because you will be simply reusing
   your old user data in `/home/weewx`. However, you do need to upgrade your old configuration
   file, documentation, examples, and daemon utility files:

    ```shell
    weectl station upgrade --config=/home/weewx/weewx.conf
    ```

3. At this point, try running the V5.0 version of `weewxd` directly, using your
   old configuration file.

    ```shell
    weewxd --config=/home/weewx/weewx.conf
    ```

4. If that works, then it's time to modify your old daemon configuration file
   so that it uses the new V5.0 executable. These steps will require root privileges.

    !!! Note
        If you previously used a SysV `init.d` startup file, you will need to clean up any
        previous `init.d` remnants. Please consult the [wiki article](https://github.com/weewx/weewx/wiki/Switching-from-SysVinit-to-systemd)
        for how to do so.
   
    === "Debian"

        !!! Note
            The resulting daemon will be run using your username. If you prefer to use run as `root`,
            you will have to modify the file `/etc/systemd/system/weewx.service`.
   
        ```bash
        cd /home/weewx
        sudo cp util/systemd/weewx.service /etc/systemd/system
        sudo systemctl daemon-reload
        sudo systemctl enable weewx
        sudo systemctl start weewx
        ```

    === "Very old Debian"
      
        !!! Note
            The resulting daemon will be run using your username. If you prefer to use run as `root`,
            you will have to modify the file `/etc/init.d/weewx`.
      
        ```bash
        # Use the old init.d method if your os is ancient
        cd /home/weewx
        sudo cp util/init.d/weewx.debian /etc/init.d/weewx
        sudo chmod +x /etc/init.d/weewx
        sudo update-rc.d weewx defaults 98
        sudo /etc/init.d/weewx start     
        ```
      
    === "Redhat"
      
        !!! Note
            The resulting daemon will be run using your username. If you prefer to use run as `root`,
            you will have to modify the file `/etc/systemd/system/weewx.service`.

        ```shell
        # If SELinux is enabled, you will need the following command first:
        chcon -R --reference /bin/ls ~/.local/bin

        # Then proceed as normal:
        cd /home/weewx
        sudo cp util/systemd/weewx.service /etc/systemd/system
        sudo systemctl daemon-reload
        sudo systemctl enable weewx
        sudo systemctl start weewx
        ```
      
    === "openSUSE Leap"
      
        !!! Note
            The resulting daemon will be run using your username. If you prefer to use run as `root`,
            you will have to modify the file `/etc/systemd/system/weewx.service`.

        ```bash
        cd /home/weewx
        sudo cp util/systemd/weewx.service /etc/systemd/system
        sudo systemctl daemon-reload
        sudo systemctl enable weewx
        sudo systemctl start weewx
        ```
      
    === "macOS"
      
        ```bash
        cd /Users/Shared/weewx
        sudo cp util/launchd/com.weewx.weewxd.plist /Library/LaunchDaemons
        sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
        ```

## Old code

Note that your old V4.x code will still be under `/home/weewx/bin` 
(`/Users/Shared/weewx` for macOS).

To avoid confusing yourself and any tools that you might use, you should consider moving your old
code aside. Unfortunately, you cannot simply rename it, because your `user` directory is located
underneath, so you would lose access to it and any extensions it might contain. Here's how to do it
without disturbing the things you want to keep:

=== "Linux"
    ``` bash
    cd /home/weewx
    mv bin bin.old
    mkdir bin
    cp -r ./bin.old/user bin 
    ```

=== "macOS"
    ``` bash
    cd /Users/Shared/weewx
    mv bin bin.old
    mkdir bin
    cp -r ./bin.old/user bin 
    ```

When you're done, you should have a directory tree that looks something like this:

```
bin
└── user
    ├── __init__.py
    ├── extensions.py
    └── installer
bin.old
    ├── daemon.py
    ├── schemas
    ... etc
```
