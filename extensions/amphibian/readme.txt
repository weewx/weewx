This is the skin amphibian for the weewx weather system.
Copyright 2012-2014 Matthew Wall

Installation instructions:

1) copy the amphibian files to the skins directory:

cd /var/tmp
tar xvfz ~/Downloads/amphibian.tgz
cp -rp amphibian/skins/amphibian /home/weewx/skins

2) add this to the StdReport section of weewx.conf:

    [[Amphibian]]
        skin = amphibian
        HTML_ROOT = public_html/amphibian
        [[[Extras]]]
            footer = /home/weewx/skins/amphibian/footer.inc
            header = /home/weewx/skins/amphibian/header.inc
            charts = /home/weewx/skins/amphibian/charts.inc

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
