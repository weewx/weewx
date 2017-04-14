previmeteo - weewx extension that sends data to Previmeteo (http://www.previmeteo.com)
Copyright 2016 Jean-Pierre Bouchillou

Installation instructions :

1) run the installer :

setup.py install --extension weewx-previmeteo.tgz

2) modify weewx.conf:

[StdRESTful]
    [[OpenWeatherMap]]
        station = USERNAME
        password = OWM_PASSWORD

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
