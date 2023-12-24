#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.
#      Modifications by Brice Ruth <bdruth@gmail.com> (c) 2023 MIT License
#      https://opensource.org/license/mit/

"""Example of how to implement a low battery alarm in WeeWX.

*******************************************************************************

To use this alarm, add the following somewhere in your configuration file
weewx.conf:

[Alarm]
    time_wait = 3600
    count_threshold = 10
    app_token = <your Pushover app token>
    user_key = <your Pushover user key>
    subject = "Time to change the battery!"

To avoid a flood of notifications, one will only be sent every 3600 seconds (one
hour).

It will also not send a notification unless the low battery indicator has been on
greater than or equal to count_threshold times in an archive period. This
avoids sending out an alarm if the battery is only occasionally being signaled
as bad.

*******************************************************************************

To enable this service:

1) Copy this file to your user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the weewx configuration file by adding this service to the option
"report_services", located in section [Engine][[Services]].

[Engine]
  [[Services]]
    ...
    report_services = weewx.engine.StdPrint, weewx.engine.StdReport, user.lowBatteryPushover.BatteryAlarm

*******************************************************************************

If you wish to use both this example and the alarm.py example, simply merge the
two configuration options together under [Alarm] and add both services to
report_services.

*******************************************************************************
"""

import logging
import time
import http.client, urllib
import threading

import weewx
from weewx.engine import StdService
from weeutil.weeutil import timestamp_to_string, option_as_list

log = logging.getLogger(__name__)


# Inherit from the base class StdService:
class BatteryAlarm(StdService):
    """Service that sends pushover notification if one of the batteries is low"""

    battery_flags = ['txBatteryStatus', 'windBatteryStatus',
                     'rainBatteryStatus', 'inTempBatteryStatus',
                     'outTempBatteryStatus']

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
            self.count_threshold = int(config_dict['Alarm'].get('count_threshold', 10))
            self.app_token       = config_dict['Alarm']['app_token']
            self.user_key       = config_dict['Alarm']['user_key']
            self.SUBJECT         = config_dict['Alarm'].get('subject', "Low battery alarm message from weewx")
        except KeyError as e:
            log.info("No alarm set.  Missing parameter: %s", e)
        else:
            # If we got this far, it's ok to start intercepting events:
            self.bind(weewx.NEW_LOOP_PACKET,    self.new_loop_packet)
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            log.info("LowBattery alarm enabled. Count threshold is %d", self.count_threshold)

    def new_loop_packet(self, event):
        """This function is called on each new LOOP packet."""

        packet = event.packet

        # If any battery status flag is non-zero, a battery is low. Use dictionary comprehension
        # to build a new dictionary that just holds the non-zero values.
        low_batteries = {k : packet[k] for k in BatteryAlarm.battery_flags
                         if k in packet and packet[k]}

        # If there are any low batteries, see if we need to send an alarm
        if low_batteries:
            self.alarm_count += 1

            # Don't panic on the first occurrence. We must see the alarm at
            # least count_threshold times before sounding the alarm.
            if self.alarm_count >= self.count_threshold:
                # We've hit the threshold. However, to avoid a flood of nearly
                # identical notifications, send a new one only if it's been a long
                # time since we sent the last one:
                if abs(time.time() - self.last_msg_ts) >= self.time_wait :
                    # Sound the alarm!
                    timestamp = event.packet['dateTime']
                    # Launch in a separate thread so it does not block the
                    # main LOOP thread:
                    t = threading.Thread(target=BatteryAlarm.sound_the_alarm,
                                         args=(self, timestamp,
                                               low_batteries,
                                               self.alarm_count))
                    t.start()
                    # Record when the message went out:
                    self.last_msg_ts = time.time()
        
    def new_archive_record(self, event):
        """This function is called on each new archive record."""
        
        # Reset the alarm counter
        self.alarm_count = 0

    def sound_the_alarm(self, timestamp, battery_flags, alarm_count):
        """This function is called when the alarm has been triggered."""
        
        # Get the time and convert to a string:
        t_str = timestamp_to_string(timestamp)

        # Log it in the system log:
        log.info("Low battery status sounded at %s: %s" % (t_str, battery_flags))

        # Form the message text:
        indicator_strings = []
        for bat in battery_flags:
            indicator_strings.append("%s: %04x" % (bat, int(battery_flags[bat])))
        msg_text = """
The low battery indicator has been seen %d times since the last archive period.

Alarm sounded at %s

Low battery indicators:
%s

""" % (alarm_count, t_str, '\n'.join(indicator_strings))
        
        try:
            conn = http.client.HTTPSConnection("api.pushover.net:443")
            conn.request("POST", "/1/messages.json",
              urllib.parse.urlencode({
                "token": self.app_token,
                "user": self.user_key,
                "message": msg_text,
              }), { "Content-type": "application/x-www-form-urlencoded" })
            conn.getresponse()
        except Exception as e:
            log.error("Send pushover notification failed: %s", e)
            raise
        
        # Log sending the notification:
        log.info("Pushover notification sent to: %s", self.user_key)


if __name__ == '__main__':
    """This section is used to test lowBattery.py. It uses a record that is guaranteed to
    sound a battery alert.

     You will need a valid weewx.conf configuration file with an [Alarm]
     section that has been set up as illustrated at the top of this file."""

    from optparse import OptionParser
    import weecfg
    import weeutil.logger

    usage = """Usage: python lowBattery.py --help    
       python lowBattery.py [CONFIG_FILE|--config=CONFIG_FILE]

Arguments:

      CONFIG_PATH: Path to weewx.conf """

    epilog = """You must be sure the WeeWX modules are in your PYTHONPATH. For example:

    PYTHONPATH=/home/weewx/bin python lowBattery.py --help"""

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
    weeutil.logger.setup('lowBattery', config_dict)

    if 'Alarm' not in config_dict:
        exit("No [Alarm] section in the configuration file %s" % config_path)

    # This is the fake packet that we'll use
    pack = {'txBatteryStatus': 1.0,
            'dateTime': int(time.time())}

    # We need the main WeeWX engine in order to bind to the event, but we don't need
    # for it to completely start up. So get rid of all services:
    config_dict['Engine']['Services'] = {}
    # Now we can instantiate our slim engine, using the DummyEngine class...
    engine = weewx.engine.DummyEngine(config_dict)
    # ... and set the alarm using it.
    alarm = BatteryAlarm(engine, config_dict)

    # Create a NEW_LOOP_PACKET event
    event = weewx.Event(weewx.NEW_LOOP_PACKET, packet=pack)

    # Trigger the alarm enough that we reach the threshold
    for count in range(alarm.count_threshold):
        alarm.new_loop_packet(event)
