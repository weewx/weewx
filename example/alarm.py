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

In this example, if the outside temperature falls below 40, it
will send an email to a specified recipient.

It assumes that your SMTP email server uses secure logins. The
username and password information for the login should be put
in a configuration file named '.secure', placed in your home
directory. It should contain something like this:

[Email]
SMTP_HOST=smtp.mymail.net
USER = myusername
PASSWORD = mypassword

Alternatively, you could put this information in your weewx
configuration file weewx.conf. I didn't do it this way because I couldn't
trust myself to remember to remove this sensitive information before posting
the new code!

The recipient of the email is given by variable "TO", hardwired
below. This could also be set in the weewx configuration file.

Should you chose to put this information in the the weewx configuration
file, it is available as a dictionary at

  self.engine.config_dict

"""

# Configuration file that contains the secure login information. 
# See the comments above for its contents
PASSWORD_FILE = '/home/tkeffer/.secure'

# Hardwired email sender and recipient:
FROM = "weewx"
TO    ="keffer@gorge.net"

import time
import smtplib
from email.mime.text import MIMEText
from ConfigParser import RawConfigParser as ConfigParser

from weewx.wxengine import StdService
from weeutil.weeutil import timestamp_to_string

# Inherit from the base class StdService:
class MyAlarm(StdService):
    """Custom service that sounds an alarm if outside temperature drops below 40"""
    
    # Pass the initialization information on to my superclass:
    def __init__(self, engine):
        StdService.__init__(self, engine)
        
        # This will hold the time when the last alarm message went out:
        self.last_msg = None
    

    def postArchiveData(self, rec):
        StdService.postArchiveData(self, rec)

        # To avoid a flood of nearly identical emails, this will do
        # the check only if we have never sent an email, or if we haven't
        # sent any in the last 30 minutes:
        if not self.last_msg or abs(time.time() - self.last_msg) >= 1800 :
            
            # Sound the alarm if the outside temperature is less than 40:
            if rec['outTemp'] is not None and rec['outTemp'] < 40.0 :
                self.soundTheAlarm(rec)
            
            # Alternative: suppose you have an extra temperature sensor
            # in your freezer, and you want to be notified if the temperature
            # rises above 15. It would look like:
            # if rec['extraTemp1'] is not None and rec['extraTemp1'] > 15.0 :
            #     self.soundTheAlarm(rec)

    def soundTheAlarm(self, rec):
        """This function is called when an out-of-bounds temperature is detected."""
        
        # Get the time and convert to a string:
        t_str = timestamp_to_string(rec['dateTime'])
        # Form the message text:
        msg_text = "Out of bounds temperature of %f recorded at %s" % (rec['outTemp'], t_str)
        # Convert to MIME:
        msg = MIMEText(msg_text)
        
        # Fill in MIME headers:
        msg['Subject'] = "Alarm message from weewx"
        msg['From']    = FROM
        msg['To']      = TO
        
        # Get the secure login information from file ~/.secure:
        parser = ConfigParser()
        parser.read(PASSWORD_FILE)
        
        # Create an instance of class SMTP for the given SMTP host:
        s = smtplib.SMTP(parser.get('Email', 'SMTP_HOST'))
        # Log in:
        s.login(parser.get('Email', 'USER'), parser.get('Email', 'PASSWORD'))
        # Send the email:
        s.sendmail(FROM, [TO],  msg.as_string())
        # Log out of the server:
        s.quit()
        # Record when the message went out:
        self.last_msg = time.time()
        