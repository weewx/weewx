#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.

"""Example of how to implement an alarm in WeeWX.

*******************************************************************************

To use this alarm, add the following somewhere in your configuration file
weewx.conf:

[Alarm]
    expression = "outTemp < 40.0"
    time_wait = 3600
    smtp_host = smtp.example.com
    smtp_user = myusername
    smtp_password = mypassword
    from = sally@example.com
    mailto = jane@example.com, bob@example.com
    subject = "Alarm message from weewx!"
  
In this example, if the outside temperature falls below 40, it will send an
email to the users specified in the comma separated list specified in option
"mailto", in this case:

jane@example.com, bob@example.com

The example assumes an SMTP email server at smtp.example.com that requires
login.  If the SMTP server does not require login, leave out the lines for
smtp_user and smtp_password.

Setting an email "from" is optional. If not supplied, one will be filled in,
but your SMTP server may or may not accept it.

Setting an email "subject" is optional. If not supplied, one will be filled in.

To avoid a flood of emails, one will only be sent every 3600 seconds (one
hour).

*******************************************************************************

To enable this service:

1) Copy this file to the user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the weewx configuration file by adding this service to the option
"report_services", located in section [Engine][[Services]].

[Engine]
  [[Services]]
    ...
    report_services = weewx.engine.StdPrint, weewx.engine.StdReport, user.alarm.MyAlarm

*******************************************************************************

If you wish to use both this example and the lowBattery.py example, simply
merge the two configuration options together under [Alarm] and add both
services to report_services.

*******************************************************************************
"""

import logging
import smtplib
import socket
import threading
import time
from email.mime.text import MIMEText

import weewx
from weeutil.weeutil import timestamp_to_string, option_as_list
from weewx.engine import StdService

log = logging.getLogger(__name__)


# Inherit from the base class StdService:
class MyAlarm(StdService):
    """Service that sends email if an arbitrary expression evaluates true"""
    
    def __init__(self, engine, config_dict):
        # Pass the initialization information on to my superclass:
        super(MyAlarm, self).__init__(engine, config_dict)
        
        # This will hold the time when the last alarm message went out:
        self.last_msg_ts = 0
        
        try:
            # Dig the needed options out of the configuration dictionary.
            # If a critical option is missing, an exception will be raised and
            # the alarm will not be set.
            self.expression    = config_dict['Alarm']['expression']
            self.time_wait     = int(config_dict['Alarm'].get('time_wait', 3600))
            self.timeout       = int(config_dict['Alarm'].get('timeout', 10))
            self.smtp_host     = config_dict['Alarm']['smtp_host']
            self.smtp_user     = config_dict['Alarm'].get('smtp_user')
            self.smtp_password = config_dict['Alarm'].get('smtp_password')
            self.SUBJECT       = config_dict['Alarm'].get('subject', "Alarm message from weewx")
            self.FROM          = config_dict['Alarm'].get('from', 'alarm@example.com')
            self.TO            = option_as_list(config_dict['Alarm']['mailto'])
        except KeyError as e:
            log.info("No alarm set.  Missing parameter: %s", e)
        else:
            # If we got this far, it's ok to start intercepting events:
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)    # NOTE 1
            log.info("Alarm set for expression: '%s'", self.expression)

    def new_archive_record(self, event):
        """Gets called on a new archive record event."""
        
        # To avoid a flood of nearly identical emails, this will do
        # the check only if we have never sent an email, or if we haven't
        # sent one in the last self.time_wait seconds:
        if not self.last_msg_ts or abs(time.time() - self.last_msg_ts) >= self.time_wait:
            # Get the new archive record:
            record = event.record
            
            # Be prepared to catch an exception in the case that the expression contains 
            # a variable that is not in the record:
            try:                                                              # NOTE 2
                # Evaluate the expression in the context of the event archive record.
                # Sound the alarm if it evaluates true:
                if eval(self.expression, None, record):                       # NOTE 3
                    # Sound the alarm!
                    # Launch in a separate thread so it doesn't block the main LOOP thread:
                    t = threading.Thread(target=MyAlarm.sound_the_alarm, args=(self, record))
                    t.start()
                    # Record when the message went out:
                    self.last_msg_ts = time.time()
            except NameError as e:
                # The record was missing a named variable. Log it.
                log.info("%s", e)

    def sound_the_alarm(self, record):
        """Sound the alarm in a 'try' block"""

        # Wrap the attempt in a 'try' block so we can log a failure.
        try:
            self.do_alarm(record)
        except socket.gaierror:
            # A gaierror exception is usually caused by an unknown host
            log.critical("Unknown host %s", self.smtp_host)
            # Reraise the exception. This will cause the thread to exit.
            raise
        except Exception as e:
            log.critical("Unable to sound alarm. Reason: %s", e)
            # Reraise the exception. This will cause the thread to exit.
            raise

    def do_alarm(self, record):
        """Send an email out"""

        # Get the time and convert to a string:
        t_str = timestamp_to_string(record['dateTime'])

        # Log the alarm
        log.info('Alarm expression "%s" evaluated True at %s' % (self.expression, t_str))

        # Form the message text:
        msg_text = 'Alarm expression "%s" evaluated True at %s\nRecord:\n%s' \
                   % (self.expression, t_str, str(record))
        # Convert to MIME:
        msg = MIMEText(msg_text)
        
        # Fill in MIME headers:
        msg['Subject'] = self.SUBJECT
        msg['From']    = self.FROM
        msg['To']      = ','.join(self.TO)

        try:
            # First try end-to-end encryption
            s = smtplib.SMTP_SSL(self.smtp_host, timeout=self.timeout)
            log.debug("Using SMTP_SSL")
        except (AttributeError, socket.timeout, socket.error) as e:
            log.debug("Unable to use SMTP_SSL connection. Reason: %s", e)
            # If that doesn't work, try creating an insecure host, then upgrading
            s = smtplib.SMTP(self.smtp_host, timeout=self.timeout)
            try:
                # Be prepared to catch an exception if the server
                # does not support encrypted transport.
                s.ehlo()
                s.starttls()
                s.ehlo()
                log.debug("Using SMTP encrypted transport")
            except smtplib.SMTPException as e:
                log.debug("Using SMTP unencrypted transport. Reason: %s", e)

        try:
            # If a username has been given, assume that login is required for this host:
            if self.smtp_user:
                s.login(self.smtp_user, self.smtp_password)
                log.debug("Logged in with user name %s", self.smtp_user)
            
            # Send the email:
            s.sendmail(msg['From'], self.TO,  msg.as_string())
            # Log out of the server:
            s.quit()
        except Exception as e:
            log.error("SMTP mailer refused message with error %s", e)
            raise
        
        # Log sending the email:
        log.info("Email sent to: %s", self.TO)


if __name__ == '__main__':
    """This section is used to test alarm.py. It uses a record and alarm
     expression that are guaranteed to trigger an alert.
     
     You will need a valid weewx.conf configuration file with an [Alarm]
     section that has been set up as illustrated at the top of this file."""

    from optparse import OptionParser
    import weecfg
    import weeutil.logger

    usage = """Usage: python alarm.py --help    
       python alarm.py [CONFIG_FILE|--config=CONFIG_FILE]
    
Arguments:
    
      CONFIG_PATH: Path to weewx.conf """

    epilog = """You must be sure the WeeWX modules are in your PYTHONPATH. For example:
    
    PYTHONPATH=/home/weewx/bin python alarm.py --help"""

    # Force debug:
    weewx.debug = 1

    # Create a command line parser:
    parser = OptionParser(usage=usage,
                          epilog=epilog)
    parser.add_option("--config", dest="config_path", metavar="CONFIG_FILE",
                      help="Use configuration file CONFIG_FILE.")
    # Parse the arguments and options
    (options, args) = parser.parse_args()

    try:
        config_path, config_dict = weecfg.read_config(options.config_path, args)
    except IOError as e:
        exit("Unable to open configuration file: %s" % e)

    print("Using configuration file %s" % config_path)

    # Set logging configuration:
    weeutil.logger.setup('alarm', config_dict)

    if 'Alarm' not in config_dict:
        exit("No [Alarm] section in the configuration file %s" % config_path)

    # This is a fake record that we'll use
    rec = {'extraTemp1': 1.0,
           'outTemp': 38.2,
           'dateTime': int(time.time())}

    # Use an expression that will evaluate to True by our fake record.
    config_dict['Alarm']['expression'] = "outTemp<40.0"

    # We need the main WeeWX engine in order to bind to the event, but we don't need
    # for it to completely start up. So get rid of all services:
    config_dict['Engine']['Services'] = {}
    # Now we can instantiate our slim engine, using the DummyEngine class...
    engine = weewx.engine.DummyEngine(config_dict)
    # ... and set the alarm using it.
    alarm = MyAlarm(engine, config_dict)

    # Create a NEW_ARCHIVE_RECORD event
    event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=rec)

    # Use it to trigger the alarm:
    alarm.new_archive_record(event)
