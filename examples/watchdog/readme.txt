Name   :  weewx_watchdog
Author :  Leon Shaner
Version:  1.1.3
Date   :  Fri 10 May 2019 18:18:06 EDT

This is an example of a "watchdog" script, primarily used to detect loss of
communications and/or lack of updates from a weather station.

This was originally written as a workaround for an issue with the WMR300 on
Raspberry Pi, whereby the USB connection to the station would "hang" and for
which restarting weewx didn't help.  A host reboot was effective in getting
the station communicating again.

Obviously rebooting the host is a "big hammer" and would not be the least bit
tolerable on anything but a dedicated weewx host, so by default the watchdog
merely sends a warning e-mail when there is loss of communications for any
reason.

The script has simple toggles to control the remediation behavior:
doweewxrestart=1        # 1 means yes remediate by restarting weewx 
dohostreboot=1          # 1 means yes remediate by rebooting host
doraincounterwarning=1  # 1 means yes check WMR300 rain counter warning
dowufixer=1             # 1 means yes run wunderfixer (only after an outage)


Main features (weewx_watchdog):
  - Checks for weewx not running (e.g. crashed or stopped)
  - Checks for lack of updates from station (e.g. loss of comms or other)
  - Calls wunderfixer after an outage to catch up WU soon after
  - Checks for WMR300 rain counter warning and sends an e-mail notification
    NOTE: This check is essentially a no-op for any other weatherstation,
          but is disabled by default anyway.

Supplemental features (weewx_wunderfixer):

  - The weewx_wunderfixer is a wrapper that computes today's and yesterday's
    dates and then calls wunderfixer once for each.
    NOTE:  This is intended to be run twice a day to catch any records
           that failed to upload to WU or were dropped for any reason.


Pre-requisites:

  - The e-mail notifications rely on mailx to be able to send e-mail.
    On Debian / Raspian, that typically means:

	$ sudo apt-get install mailtutils

    On Fedora-based Linux, that typcially means:
	  
	$ sudo yum install mailtutils

    NOTE: Typically the sytem mailer will need to be configured to rely
          on a smart-relay host (outside the scope of this example).


Installation:

  - Edit the weewx_watchdog script and change the email address, and
    customize toggles appropriately.

  - Copy the scripts to a suitable location like /usr/local/sbin.
    Just be sure to adjust the example crontab entry if you use
    some other path.

    $ sudo cp weewx_watchdog weewx_wunderfixer /usr/local/sbin
    $ sudo chmod 744 /usr/local/sbin/weewx_watchdog /usr/local/sbin/weewx_wunderfixer

  - Copy the weewx_logrotate as /etc/logrotate.d/weewx, for auto-rotation of 
    supplemental log at /var/log/weewx.log, a la:

    $ sudo cp weewx_logrotate /etc/logrotate.d/weewx

  - Add a crontab entry for root to execute the script, using a method similar
    to the following:

    $ sudo crontab -e

An example root cron entry follows...

NOTE:  Please vary the 11,11 (minute part of the weewx_wunderfixer to
       avoid every user of these utilities hitting WU always at the same time.

# WeeWX Watchdog script
2,12,22,32,42,52 * * * * /usr/local/sbin/weewx_watchdog
11,11 1,13 * * * /usr/local/sbin/weewx_wunderfixer
