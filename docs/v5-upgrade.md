# Migrating to Version 5.0

This guide is for migrating V4.x installations to Version 5.0.

Relevant changes:

- With V5.0, there is now a clean separation between WeeWX code, and "user
  data" (such as configuration files, skins, database, etc). They are stored in
  separate areas, rather than everything under `/home/weewx`.

- With V5.0, all WeeWX code is now in the normal Python directories and no code
  is under `/home/weewx`. In fact, no code in `/home/weewx`, _including any
  extensions_, is used at all.

- By default, WeeWX user data is now stored in your home directory in
  `~/weewx-data`. However, you may continue to use your old user data located in
  `/home/weewx` by following this guide.

With this in mind, here is how you can continue to use your old `/home/weewx`:

1. Move the old source tree aside so you won't confuse yourself, or any tools
   you might use:

    ```shell
    mv /home/weewx/bin /home/weewx/bin.old
    ```

2. Install V5.0 using the tool  [pipx](https://pypa.github.io/pipx/) . 
   To familiarize yourself with the process, take a look at the document
   [_Installation using pip_](pip.md), but note that you are only going to follow
   step 1 (using pipx), and not step 2, which sets up the user data area. For 
   that, you will use your old `/home/weewx`.

    Here are the relevant steps again:

    ```shell
    # Install the tool pipx as a 'user' app
    python3 -m pip install pipx --user
    # Then use it to install weewx
    pipx install weewx
    ```

    When you are done, the new V5.0 executable will be in `~/.local/bin/weewxd`,
    rather than the more familiar V4.x location `/home/weewx/bin/weewxd`.

3. Migrate your old extensions over by using the tool `weectl`. 

    First, try a dry run to make sure it will do what you expect:

    ```shell
   weectl extension transfer --dry-run 
    ```
   
    If all looks good, do the actual transfer:

    ```shell
   weectl extension transfer 
    ```
   
4. At this point, try running the V5.0 version of `weewxd` directly, using your
   old configuration file:

    ```shell
    weewxd --config=/home/weewx/weewx.conf
    ```

5. If that works, then it's time to modify your old daemon configuration file
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
       
