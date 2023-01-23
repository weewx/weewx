basic - a very basic WeeWX skin
=============

Copyright 2014-2023 Matthew Wall

This example illustrates how to implement a skin and package it so that it can be installed by the
extension installer. It also illustrates how to internationalize a skin.


Installation instructions using the installer (recommended)
-------------------------

1) install the extension.

    For pip installs:

        weectl extension install ~/weewx-data/examples/basic

    For package installs

        sudo weectl extension install /usr/share/doc/weewx/examples/basic

2) Restart WeeWX

        sudo systemctl restart weewx


Manual installation instructions
-------------------------

1) Copy files to the WeeWX skins directory.

    If you used the pip install method:

        cd ~/weewx-data
        cp -rp skins/basic skins

    If you used a package installer:

        cd /usr/share/doc/weewx/examples/basic
        sudo cp -rp skins/basic/ /etc/weewx/skins/

2) In the WeeWX configuration file, add a report

       [StdReport]
           ...
           [[basic]]
               skin = basic
               HTML_ROOT = public_html/basic
               lang = en
               unit_system = us

3) Restart WeeWX

       sudo systemctl restart weewx
