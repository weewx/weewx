basic - a very basic WeeWX skin
Copyright 2014 Matthew Wall

This example illustrates how to implement a skin and package it so that it
can be installed by the extension installer.


Installation instructions

1) install the extension

wee_extension --install=/home/weewx/examples/basic

2) restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


Manual installation instructions

1) copy files to the WeeWX skins directory

cp -rp skins/basic /home/weewx/skins

2) in the WeeWX configuration file, add a report

[StdReport]
    ...
    [[basic]]
        skin = basic
        HTML_ROOT = public_html/basic

3) restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
