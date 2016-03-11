#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Example of how to implement a low battery alarm in weewx. 

********************************************************************************

To use this alarm, add the following somewhere in your configuration file
weewx.conf:

[Alarm]
  time_wait = 3600
  count_threshold = 50
  smtp_host = smtp.mymailserver.com
  smtp_user = myusername
  smtp_password = mypassword
  from   = me@mydomain.com
  mailto = auser@adomain.com, another@somewhere.com
  subject = "Time to change the battery!"

In this example, an email will be sent to the comma separated list of recipients
auser@domain.com, another@somewhere.com

The example assumes that your SMTP email server is at smtp.mymailserver.com and
that it uses secure logins. If it does not use secure logins, leave out the
lines for smtp_user and smtp_password and no login will be attempted.

Setting an email "from" is optional. If not supplied, one will be filled in, but
your SMTP server may or may not accept it.

Setting an email "subject" is optional. If not supplied, one will be filled in.

To avoid a flood of emails, one will only be sent every 3600 seconds (one hour).

It will also not send an email unless the low battery indicator has been on
greater than or equal to count_threshold times in an archive period. This avoids
sending out an alarm if the battery is only occasionally being signaled as bad.

********************************************************************************

To specify that this new service be loaded and run, it must be added to the
configuration option "report_services", located in sub-section [Engine][[Services]].

[Engine]
  [[Services]]
    ...
    report_services = weewx.engine.StdPrint, weewx.engine.StdReport, examples.lowBattery.BatteryAlarm

********************************************************************************

If you wish to use both this example and the alarm.py example, simply merge the
two configuration options together under [Alarm] and add both services to
report_services.

*****************************************************************************
"""

import time
import smtplib
from email.mime.text import MIMEText
import threading
import syslog

import weewx
from weewx.engine import StdService
from weeutil.weeutil import timestamp_to_string, option_as_list

# Inherit from the base class StdService:
class BatteryAlarm(StdService):
    """Custom service that sounds an alarm if one of the batteries is low"""
    
    def __init__(self, engine, config_dict):
        # Pass the initialization information on to my superclass:
        super(BatteryAlarm, self).__init__(engine, config_dict)
        
        # This will hold the time when the last alarm message went out:
        self.last_msg_ts = 0
        # This will hold the count of the number of times the VP2 has signaled
        # a low battery alarm this archive period
        self.alarm_count = 0
        
        try:
            # Dig the needed options out of the configuration dictionary.
            # If a critical option is missing, an exception will be thrown and
            # the alarm will not be set.
            self.time_wait       = int(config_dict['Alarm'].get('time_wait', 3600))
            self.count_threshold = int(config_dict['Alarm'].get('count_threshold', 50))
            self.smtp_host       = config_dict['Alarm']['smtp_host']
            self.smtp_user       = config_dict['Alarm'].get('smtp_user')
            self.smtp_password   = config_dict['Alarm'].get('smtp_password')
            self.SUBJECT         = config_dict['Alarm'].get('subject', "Low battery alarm message from weewx")
            self.FROM            = config_dict['Alarm'].get('from', 'alarm@weewx.com')
            self.TO              = option_as_list(config_dict['Alarm']['mailto'])
            syslog.syslog(syslog.LOG_INFO, "lowBattery: LowBattery alarm turned on. Count threshold is %d" % self.count_threshold)

            # If we got this far, it's ok to start intercepting events:
            self.bind(weewx.NEW_LOOP_PACKET,    self.newLoopPacket)
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.newArchiveRecord)

        except KeyError, e:
            syslog.syslog(syslog.LOG_INFO, "lowBattery: No alarm set. %s" % e)

    def newLoopPacket(self, event):
        """This function is called with the arrival of every new LOOP packet."""

        # If the Transmit Battery Status byte is non-zero, an alarm is on
        if event.packet['txBatteryStatus']:

            self.alarm_count += 1

            # Don't panic on the first occurrence. We must see the alarm at
            # least count_threshold times before sounding the alarm.
            if self.alarm_count >= self.count_threshold:
                # We've hit the threshold. However, to avoid a flood of nearly
                # identical emails, send a new one only if it's been a long time
                # since we sent the last one:
                if abs(time.time() - self.last_msg_ts) >= self.time_wait :
                    # Sound the alarm!
                    timestamp = event.packet['dateTime']
                    battery_status = event.packet['txBatteryStatus']
                    # Launch in a separate thread so it doesn't block the main LOOP thread:
                    t  = threading.Thread(target = BatteryAlarm.soundTheAlarm,
                                          args=(self, timestamp, battery_status, self.alarm_count))
                    t.start()
                    # Record when the message went out:
                    self.last_msg_ts = time.time()
        
    def newArchiveRecord(self, event):  # @UnusedVariable
        """This function is called with the arrival of every new archive record."""
        
        # Reset the alarm counter
        self.alarm_count = 0

    def soundTheAlarm(self, timestamp, battery_status, alarm_count):
        """This function is called when the low battery alarm has been sounded."""
        
        # Get the time and convert to a string:
        t_str = timestamp_to_string(timestamp)

        # Log it in the system log:
        syslog.syslog(syslog.LOG_INFO, "lowBattery: Low battery alarm (0x%04x) sounded at %s." % (battery_status, t_str))

        # Form the message text:
        msg_text = """The low battery alarm (0x%04x) has been seen %d times since the last archive period.\n\n"""\
                   """Alarm sounded at %s\n\n""" % (battery_status, alarm_count, t_str)
        # Convert to MIME:
        msg = MIMEText(msg_text)
        
        # Fill in MIME headers:
        msg['Subject'] = self.SUBJECT
        msg['From']    = self.FROM
        msg['To']      = ','.join(self.TO)
        
        # Create an instance of class SMTP for the given SMTP host:
        s = smtplib.SMTP(self.smtp_host)
        try:
            # Some servers (eg, gmail) require encrypted transport.
            # Be prepared to catch an exception if the server
            # doesn't support it.
            s.ehlo()
            s.starttls()
            s.ehlo()
            syslog.syslog(syslog.LOG_DEBUG, "  **** using encrypted transport")
        except smtplib.SMTPException:
            syslog.syslog(syslog.LOG_DEBUG, "  **** using unencrypted transport")

        try:
            # If a username has been given, assume that login is required for this host:
            if self.smtp_user:
                s.login(self.smtp_user, self.smtp_password)
                syslog.syslog(syslog.LOG_DEBUG, "  **** logged in with user name %s" % (self.smtp_user,))

            # Send the email:
            s.sendmail(msg['From'], self.TO,  msg.as_string())
            # Log out of the server:
            s.quit()
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "lowBattery: SMTP mailer refused message with error %s" % (e,))
            raise
        
        # Log sending the email:
        syslog.syslog(syslog.LOG_INFO, "  **** email sent to: %s" % self.TO)
