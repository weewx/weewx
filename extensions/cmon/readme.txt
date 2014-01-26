cmon - Computer Monitor
Copyright 2014 Matthew Wall

cmon is a weewx extension to monitor computer metrics such as cpu usage,
memory use, disk space, and ups status.  It saves data to its own database,
then those data can be displayed in weewx reports.  This extension also
includes a sample skin that illustrates how to use the data.

Installation instructions:

1) expand the tarball:

cd /var/tmp
tar xvfz ~/Downloads/weewx-cmon.tgz

2) copy files

cd /var/tmp/weewx-cmon
# copy the module to your weewx installation:
cp bin/user/cmon.py /home/weewx/bin/user
# copy the sample template files to the skin directory:
cp -r skins/cmon /home/weewx/skins

3) modify weewx.conf

# add a section to the StdReport
[StdReport]
    [[cmon]]
        skin = cmon
        HTML_ROOT = public_html/cmon

# add the cmon configuration
[ComputerMonitor]
    database = computer_sqlite
    max_age = 2592000 # 30 days; None to store indefinitely

# add the cmon database configuration
[Databases]
    ...
    [[computer_sqlite]]
        root = %(WEEWX_ROOT)s
        database = archive/computer.sdb
        driver = weedb.sqlite

# add to the service list
[Engines]
    [[WxEngine]]
        service_list = ..., user.cmon.ComputerMonitor

4) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
