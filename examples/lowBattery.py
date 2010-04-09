#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
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
  mailto = auser@adomain.com
  
The example assumes that your SMTP email server is at smtp.mymailserver.com and
that it uses secure logins. If it does not use secure logins, leave out the
lines for smtp_user and smtp_password and no login will be attempted.

To avoid a flood of emails, one will only be sent every 3600 seconds (one hour).

It will also not send an email unless the low battery indicator has been on
greater than or equal to count_threshold times in an archive period. This avoids
sending out an alarm if the battery is only occasionally being signaled as bad.

********************************************************************************

To specify that this new service be loaded and run, it must be added to the
configuration option service_list, located in sub-section [Engines][[WxEngine]]:

[Engines]
  [[WxEngine]]
    service_list = weewx.wxengine.StdWunderground, weewx.wxengine.StdCatchUp, weewx.wxengine.StdTimeSynch, weewx.wxengine.StdPrint, weewx.wxengine.StdReportService, examples.lowBattery.BatteryAlarm

********************************************************************************

If you wish to use both this example and the alarm.py example, simply merge the
two configuration options together under [Alarm] and add both services to the
service_list.

*****************************************************************************
"""

import time
import smtplib
from email.mime.text import MIMEText
import threading
import syslog

from weewx.wxengine import StdService
from weeutil.weeutil import timestamp_to_string

# Inherit from the base class StdService:
class BatteryAlarm(StdService):
    """Custom service that sounds an alarm if one of the batteries is low"""
    
    def __init__(self, engine):
        # Pass the initialization information on to my superclass:
        StdService.__init__(self, engine)
        
        # This will hold the time when the last alarm message went out:
        self.last_msg_ts = 0
        # This will hold the count of the number of times the VP2 has signaled
        # a low battery alarm this archive period
        self.alarm_count = 0
        
    def setup(self):
        
        try:
            # Dig the needed options out of the configuration dictionary.
            # If a critical option is missing, an exception will be thrown and
            # the alarm will not be set.
            self.time_wait       = int(self.engine.config_dict['Alarm'].get('time_wait', 3600))
            self.count_threshold = int(self.engine.config_dict['Alarm'].get('count_threshold', 50))
            self.smtp_host       = self.engine.config_dict['Alarm']['smtp_host']
            self.smtp_user       = self.engine.config_dict['Alarm'].get('smtp_user')
            self.smtp_password   = self.engine.config_dict['Alarm'].get('smtp_password')
            self.TO              = self.engine.config_dict['Alarm']['mailto']
            syslog.syslog(syslog.LOG_INFO, "lowBattery: LowBattery alarm turned on. Count threshold is %d" % self.count_threshold)
        except:
            self.time_wait  = None

    def processLoopPacket(self, loopPacket):
        """This function is called with the arrival of every LOOP packet."""
        
        # Let the superclass have a peek first:
        StdService.processLoopPacket(self, loopPacket)
                
        # If the Transmit Battery Status byte is non-zero, an alarm is on
        if self.time_wait is not None and loopPacket['transmitBattery']:

            self.alarm_count += 1

            # Don't panic on the first occurrence. We must see the alarm at
            # least count_threshold times before sounding the alarm.
            if self.alarm_count >= self.count_threshold:
                # We've hit the threshold. However, to avoid a flood of nearly
                # identical emails, send a new one only if it's been a long time
                # since we sent the last one:
                if abs(time.time() - self.last_msg_ts) >= self.time_wait :
                    # Sound the alarm!
                    # Launch in a separate thread so it doesn't block the main LOOP thread:
                    t  = threading.Thread(target = BatteryAlarm.soundTheAlarm, args=(self, loopPacket, self.alarm_count))
                    t.start()
                    # Record when the message went out:
                    self.last_msg_ts = time.time()
        
    def postArchiveData(self, rec):
        """This function is called when it's time to post some archive data."""
        
        # Let the superclass do its thing first:
        StdService.postArchiveData(self, rec)

        # Reset the alarm counter
        self.alarm_count = 0

    def soundTheAlarm(self, rec, alarm_count):
        """This function is called when the low battery alarm has been sounded."""
        
        # Get the time and convert to a string:
        t_str = timestamp_to_string(rec['dateTime'])
        # Form the message text:
        msg_text = """The low battery alarm (0x%04x) has been seen %d times since the last archive period.\n\n"""\
                   """Alarm sounded at %s\n\n"""\
                   """LOOP record:\n%s""" % (rec['transmitBattery'], alarm_count, t_str, str(rec))
        # Convert to MIME:
        msg = MIMEText(msg_text)
        
        # Fill in MIME headers:
        msg['Subject'] = "Low battery alarm message from weewx"
        msg['From']    = "weewx"
        msg['To']      = self.TO
        
        # Create an instance of class SMTP for the given SMTP host:
        s = smtplib.SMTP(self.smtp_host)
        try:
            # Some servers (eg, gmail) require encrypted transport.
            # Be prepared to catch an exception if the server
            # doesn't support it.
            s.ehlo()
            s.starttls()
            s.ehlo()
        except smtplib.SMTPException:
            pass
        # If a username has been given, assume that login is required for this host:
        if self.smtp_user:
            s.login(self.smtp_user, self.smtp_password)
        # Send the email:
        s.sendmail(msg['From'], [self.TO],  msg.as_string())
        # Log out of the server:
        s.quit()
        # Log it in the system log:
        syslog.syslog(syslog.LOG_INFO, "lowBattery: Low battery alarm (0x%04x) sounded." % rec['transmitBattery'])
        syslog.syslog(syslog.LOG_INFO, "       ***  email sent to: %s" % self.TO)
        
