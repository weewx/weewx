This is a forecasting extension for the weewx weather system.
Copyright 2013-2014 Matthew Wall

This package includes the forecasting module, unit tests, and a sample skin.
Four forecast sources are supported: US National Weather Service (NWS), the
weather underground (WU), Zambretti, and tide predictions using xtide.
forecast.inc is a cheetah template file designed to be included in other
templates.  At the beginning of forecast.inc is a list of variables that
determine which forecast data will be displayed.  The icons directory contains
images for cloud cover, storms, etc.

Credits:

Icons were derived from Adam Whitcroft's climacons.

Installation instructions:

1) expand the tarball:

cd /var/tmp
tar xvfz ~/Downloads/weewx-forecast.tgz

2) copy files

cd /var/tmp/weewx-forecast
# copy the forecast module to your weewx installation:
cp bin/user/forecast.py /home/weewx/bin/user
# copy the sample forecast template files to the skin directory:
cp -r skins/forecast /home/weewx/skins

3) modify weewx.conf

# add a forecast section to the StdReport
[StdReport]
    [[forecast]]
        skin = forecast
        HTML_ROOT = public_html/forecast
        [[[Extras]]]
            forecast_table = /home/weewx/skins/forecast/forecast_table.inc

# add the forecast configuration
[Forecast]
    database = forecast_sqlite
    [[NWS]]
        lid = MAZ014
        foid = BOX
    [[WU]]
        api_key = XXXXXXXXXXXXXXXX
    [[XTide]]
        location = Boston
    [[Zambretti]]
        hemisphere = NORTH

# add the forecast database configuration
[Databases]
    [[forecast_sqlite]]
        root = %(WEEWX_ROOT)s
        database = archive/forecast.sdb
        driver = weedb.sqlite

# add the desired foreasts to the service list
[Engines]
    [[WxEngine]]
        process_services = ..., user.forecast.ZambrettiForecast, user.forecast.NWSForecast, user.forecast.WUForecast, user.forecast.XTideForecast

4) modify forecast_table.inc to indicate which data should be displayed

5) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
