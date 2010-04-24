#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Example of how to implement an alarm in weewx. 

********************************************************************************

To use this alarm, add the following somewhere in your configuration file
weewx.conf:

[Alarm]
  expression = "outTemp < 40.0"
  time_wait = 3600
  smtp_host = smtp.mymailserver.com
  smtp_user = myusername
  smtp_password = mypassword
  mailto = auser@adomain.com
  
In this example, if the outside temperature falls below 40, it will send an
email to the recipient auser@adomain.com.

The example assumes that your SMTP email server is at smtp.mymailserver.com and
that it uses secure logins. If it does not use secure logins, leave out the
lines for smtp_user and smtp_password and no login will be attempted.

To avoid a flood of emails, one will only be sent every 3600 seconds (one hour).

********************************************************************************

To specify that this new service be loaded and run, it must be added to the
configuration option service_list, located in sub-section [Engines][[WxEngine]]:

[Engines]
  [[WxEngine]]
    service_list = weewx.wxengine.StdWunderground, weewx.wxengine.StdCatchUp, weewx.wxengine.StdTimeSynch, weewx.wxengine.StdPrint, weewx.wxengine.StdReportService, examples.alarm.MyAlarm

********************************************************************************

If you wish to use both this example and the lowBattery.py example, simply merge
the two configuration options together under [Alarm] and add both services to
the service_list.

********************************************************************************
"""

import time
import smtplib
from email.mime.text import MIMEText
import threading
import syslog

from weewx.wxengine import StdService
from weeutil.weeutil import timestamp_to_string

# Inherit from the base class StdService:
class MyAlarm(StdService):
    """Custom service that sounds an alarm if an arbitrary expression evaluates true"""
    
    def __init__(self, engine, config_dict):
        # Pass the initialization information on to my superclass:
        super(MyAlarm, self).__init__(engine, config_dict)
        
        # This will hold the time when the last alarm message went out:
        self.last_msg_ts = None
        
        try:
            # Dig the needed options out of the configuration dictionary.
            # If a critical option is missing, an exception will be thrown and
            # the alarm will not be set.
            self.expression    = config_dict['Alarm']['expression']
            self.time_wait     = int(config_dict['Alarm'].get('time_wait', 3600))
            self.smtp_host     = config_dict['Alarm']['smtp_host']
            self.smtp_user     = config_dict['Alarm'].get('smtp_user')
            self.smtp_password = config_dict['Alarm'].get('smtp_password')
            self.TO            = config_dict['Alarm']['mailto']
            syslog.syslog(syslog.LOG_INFO, "alarm: Alarm set for expression: \"%s\"" % self.expression)
        except:
            self.expression = None
            self.time_wait  = None

    def newArchivePacket(self, rec):
        # Let the super class see the record first:
        StdService.newArchivePacket(self, rec)

        # See if the alarm has been set:
        if self.expression:
            # To avoid a flood of nearly identical emails, this will do
            # the check only if we have never sent an email, or if we haven't
            # sent one in the last self.time_wait seconds:
            if not self.last_msg_ts or abs(time.time() - self.last_msg_ts) >= self.time_wait :
                
                # Evaluate the expression in the context of 'rec'.
                # Sound the alarm if it evaluates true:
                if eval(self.expression, None, rec):            # NOTE 1
                    # Sound the alarm!
                    # Launch in a separate thread so it doesn't block the main LOOP thread:
                    t  = threading.Thread(target = MyAlarm.soundTheAlarm, args=(self, rec))
                    t.start()
                    # Record when the message went out:
                    self.last_msg_ts = time.time()

    def soundTheAlarm(self, rec):
        """This function is called when the given expression evaluates True."""
        
        # Get the time and convert to a string:
        t_str = timestamp_to_string(rec['dateTime'])
        # Form the message text:
        msg_text = "Alarm expression \"%s\" evaluated True at %s\nRecord:\n%s" % (self.expression, t_str, str(rec))
        # Convert to MIME:
        msg = MIMEText(msg_text)
        
        # Fill in MIME headers:
        msg['Subject'] = "Alarm message from weewx"
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
        syslog.syslog(syslog.LOG_INFO, "alarm: Alarm sounded for expression: \"%s\"" % self.expression)
        syslog.syslog(syslog.LOG_INFO, "       *** email sent to: %s" % self.TO)
        
        
