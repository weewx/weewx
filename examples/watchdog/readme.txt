Name  :  weewx_watchdog
Author:  Leon Shaner
Date  :  Tue 30 Apr 2019 10:38:14 EDT

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


Main features:
  - Checks for lack of updates from station, sends an e-mail notification
  - Calls wunderfixer periodically
  - Checks for WMR300 rain counter warning and sends an e-mail notification
    NOTE: This check is essentially a no-op for any other rainstation, but
          you can comment those lines out if you prefer


Pre-requisites:

  - The e-mail notifications rely on mailx to be able to send e-mail.
    NOTE: Typically mailx will need to be configured to rely on a
          smart-relay host.


Installation:

  - Edit the script and change the email address, appropriately.

  - Copy the script to a suitable location like /usr/local/sbin, if desired,
    or just leave it in the examples location (as shown in the crontab example).
  - Copy the weewx_logrotate as /etc/logrotate.d/weewx, for auto-rotation of 
    supplemental log at /var/log/weewx.log, a la:

    $ sudo cp weewx_logrotate /etc/logrotate.d/weewx

  - Add a crontab entry for root to execute the script
    NOTE:  Script could run as non-root user if shutdown command is commented out

Example Cron entry (a la "sudo crontab -e"):

# WeeWX Watchdog script
5,15,25,35,45,55 * * * * /usr/share/weewx/examples/weewx_watchdog
