basic - a very basic weewx skin
Copyright 2014 Matthew Wall

This skin illustrates how to package a skin so it can be installed by the
weewx extension installer.


Installation instructions:

cd /home/weewx
setup.py --extension --install extensions/basic


Manual installation instructions:

1) copy files to the weewx user directory:

cp -rp skins/basic /home/weewx/skins

2) add a new report in weewx.conf:

[StdReport]
    [[basic]]
        skin = basic
        HTML_ROOT = public_html/basic

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
