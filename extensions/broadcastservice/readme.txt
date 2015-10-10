BroadcastService - simple local network meteo data broadcaster.
Copyright 2015 Jakub Kakona

Installation instructions:

1) run the installer:

sudo ./wee_extension --install ./weewx/extensions/broadcastservice

2) start weewx:

sudo /etc/init.d/weewx start


Manual installation instructions:

1) copy files to the weewx user directory:

cp bin/user/broadcastservice.py /home/weewx/bin/user

2) modify weewx.conf, register new service: 

user.broadcastservice.BroadcastService

3) start weewx

sudo /etc/init.d/weewx start
