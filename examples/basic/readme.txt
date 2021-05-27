basic - a very basic WeeWX skin
Copyright 2014 Matthew Wall

This example illustrates how to implement a skin and package it so that it can be installed by the
extension installer. It also illustrates how to internationalize a skin.


Installation instructions

1) install the extension

wee_extension --install=/home/weewx/examples/basic

2) Restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


Manual installation instructions

1) Copy files to the WeeWX skins directory. See https://bit.ly/33YHsqX for where your skins
directory is located. For example, if you used the setup.py install method:

cp -rp skins/basic /home/weewx/skins

2) In the WeeWX configuration file, add a report

[StdReport]
    ...
    [[basic]]
        skin = basic
        HTML_ROOT = public_html/basic
        lang = en
        unit_system = us

3) Restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
