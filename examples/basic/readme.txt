basic - a very basic weewx skin
Copyright 2014 Matthew Wall

This example illustrates how to implement a skin and package it so that it
can be installed by the extension installer.


Installation instructions:

1) install the extension:

wee_extension --install=/home/weewx/examples/basic

2) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


Manual installation instructions:

1) copy files to the weewx skins directory:

cp -rp skins/basic /home/weewx/skins

2) add a new report in weewx.conf:

[StdReport]
    ...
    [[basic]]
        skin = basic
        HTML_ROOT = public_html/basic

3) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
