# Migrating `setup.py` installs to Version 5.0

This guide is for migrating V4.x installations that were installed using the `setup.py` method,
to Version 5.0.

With V5.0, there is now a clean separation between *WeeWX code*, and *user data*. They are stored in
separate areas, rather than everything under `/home/weewx`.

*WeeWX code* is now in the normal Python directories. It is generic, and not specific to any
particular installation. It includes:

  - Executables such as `weewxd` and `wee_reports`;
  - Their libraries.

By contrast, *user data* is specific to your installation. By default, it is now stored in your home
directory in `~/weewx-data`, although you may continue to use your old user data located in
`/home/weewx` by following this guide. User data includes:

  * The configuration file, `weewx.conf`;
  * Skins;
  * Database;
  * Generated HTML files and images; and
  * Extensions.

With this in mind, here is how you can continue to use your old `/home/weewx`:

1. Install V5.0 using the tool  [pipx](https://pypa.github.io/pipx/) . 
   To familiarize yourself with the process, take a look at the document
   [_Installation using pip_](pip.md), but note that you are *only going to follow
   step 1* (using pipx). Do not do step 2.

    Here are the relevant commands for step 1 again:

    ```shell
    # Install the tool pipx as a 'user' app
    python3 -m pip install pipx --user
    # Then use it to install weewx
    pipx install weewx
    ```

    When you are done, the new V5.0 executable will be in `~/.local/bin/weewxd`,
    rather than the more familiar V4.x location `/home/weewx/bin/weewxd`.

2. You do not have to do anything to set up the user data area because you will be simply reusing 
   your old user data in `/home/weewx`. This includes your old `weewx.conf`, databases, skins,
   etc.
   
3. At this point, try running the V5.0 version of `weewxd` directly, using your
   old configuration file:

    ```shell
    weewxd --config=/home/weewx/weewx.conf
    ```

4. If that works, then it's time to modify your old daemon configuration file
   so that it uses the new V5.0 executable. The only change should be the
   location of `weewxd`.

    !!! note 
        Be sure to use the path to `weewxd`, not a path to `python` plus 
        `weewxd`. The reason is that the first line in `weewxd` is a "shebang",
        which will find the python executable used by the virtual environment.
        Without it, your daemon will be unable to find the WeeWX libraries.

    In what follows, replace `username` with your username.

    === "Debian"
        For Debian systemd, change this
    
        ```ini
        ExecStart=/home/weewx/bin/weewxd /home/weewx/weewx.conf
        ```
       
        to this
    
        ```ini
        ExecStart=/home/username/.local/bin/weewxd /home/weewx/weewx.conf
        ```
    
    === "Redhat"
        For Red Hat sysv, change this
    
        ```sh
        WEEWX_BIN=/home/weewx/bin/weewxd
        ```
       
        to this
    
        ```sh
        WEEWX_BIN=/home/user/.local/bin/weewxd
        ```
    
    === "macOS"
        For macOS, change this
    
        ```{.xml hl_lines="2"}
        <array>
            <string>/Users/Shared/weewx/bin/weewxd</string>
            <string>/Users/Shared/weewx/weewx.conf</string>
        </array>
        ```
       
        to this
    
        ```{.xml hl_lines="2"}
        <array>
            <string>/Users/username/.local/bin/weewxd</string>
            <string>/Users/Shared/weewx/weewx.conf</string>
        </array>
        ```
       
!!! Note
    Note that your old V4.x code will still be under `/home/weewx/bin`.

To avoid confusing yourself and any tools you might use, you should consider moving it aside.
Unfortunately, you cannot simply rename it, because your `user` directory is located underneath,
so you would lose access to it and any extensions it might contain. Here's how to do it
without disturbing the things you want to keep:

``` bash
cd /home/weewx
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