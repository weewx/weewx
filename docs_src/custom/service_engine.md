# Customizing the WeeWX service engine {#service_engine}

This is an advanced topic intended for those who wish to try their hand
at extending the internal engine in WeeWX. Before attempting these
examples, you should be reasonably proficient with Python.

!!! Warning
    Please note that the API to the service engine may change in future versions!

At a high level, WeeWX consists of an *engine* that is responsible for
managing a set of *services*. A service consists of a Python class which
binds its member functions to various *events*. The engine arranges to
have the bound member function called when a specific event happens,
such as a new LOOP packet arriving.

The services are specified in lists in the
[`[Engine][[Services]]`](../../usersguide/weewx-config-file/engine/#services)
stanza of the configuration file. The `[[Services]]` section
lists all the services to be run, broken up into different *service
lists*.

These lists are designed to orchestrate the data as it flows through the WeeWX engine. For example,
you want to make sure that data has been processed by the quality control service, `StdQC`, before
putting them in the database. Similarly, the reporting system must come *after* the data has been
put in the database. These groups ensure that things happen in the proper sequence.

See the table [The standard WeeWX services](../../custom/#the-weewx-service-architecture) for a list of the
services that are normally run.

## Modifying an existing service {#Customizing_a_service}

The service `weewx.engine.StdPrint` prints out new LOOP and
archive packets to the console when they arrive. By default, it prints
out the entire record, which generally includes a lot of possibly
distracting information and can be rather messy. Suppose you do not like
this, and want it to print out only the time, barometer reading, and the
outside temperature whenever a new LOOP packet arrives. 

This could be done by subclassing the default print service `StdPrint` and overriding member
function `new_loop_packet()`.

Create the file `user/myprint.py`:

``` python
from weewx.engine import StdPrint
from weeutil.weeutil import timestamp_to_string

class MyPrint(StdPrint):

    # Override the default new_loop_packet member function:
    def new_loop_packet(self, event):
        packet = event.packet
        print("LOOP: ", timestamp_to_string(packet['dateTime']),
            "BAR=",  packet.get('barometer', 'N/A'),
            "TEMP=", packet.get('outTemp', 'N/A'))
```

This service substitutes a new implementation for the member function
`new_loop_packet`. This implementation prints out the time, then
the barometer reading (or `N/A` if it is not available) and the
outside temperature (or `N/A`).

You then need to specify that your print service class should be loaded
instead of the default `StdPrint` service. This is done by
substituting your service name for `StdPrint` in
`service_list`, located in `[Engine]/[[Services]]`:

``` ini
[Engine]
    [[Services]]
        ...
        report_services = user.myprint.MyPrint, weewx.engine.StdReport
```

Note that the `report_services` must be all on one line.
Unfortunately, the parser `ConfigObj` does not allow options to
be continued on to following lines.

## Creating a new service {#Adding_a_service}

Suppose there is no service that can be easily customized for your
needs. In this case, a new one can easily be created by subclassing off
the abstract base class `StdService`, and then adding the
functionality you need. Here is an example that implements an alarm,
which sends off an email when an arbitrary expression evaluates
`True`.

This example is included in the standard distribution as
`examples/alarm.py:`

``` python linenums="1" hl_lines="40 56 59"
import smtplib
import socket
import syslog
import threading
import time
from email.mime.text import MIMEText

import weewx
from weeutil.weeutil import timestamp_to_string, option_as_list
from weewx.engine import StdService


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
            syslog.syslog(syslog.LOG_INFO, "alarm: Alarm set for expression: '%s'" % self.expression)

            # If we got this far, it's ok to start intercepting events:
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)    # NOTE 1
        except KeyError as e:
            syslog.syslog(syslog.LOG_INFO, "alarm: No alarm set.  Missing parameter: %s" % e)

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
                syslog.syslog(syslog.LOG_DEBUG, "alarm: %s" % e)

    def sound_the_alarm(self, rec):
        """Sound the alarm in a 'try' block"""

        # Wrap the attempt in a 'try' block so we can log a failure.
        try:
            self.do_alarm(rec)
        except socket.gaierror:
            # A gaierror exception is usually caused by an unknown host
            syslog.syslog(syslog.LOG_CRIT, "alarm: unknown host %s" % self.smtp_host)
            # Reraise the exception. This will cause the thread to exit.
            raise
        except Exception as e:
            syslog.syslog(syslog.LOG_CRIT, "alarm: unable to sound alarm. Reason: %s" % e)
            # Reraise the exception. This will cause the thread to exit.
            raise

    def do_alarm(self, rec):
        """Send an email out"""

        # Get the time and convert to a string:
        t_str = timestamp_to_string(rec['dateTime'])

        # Log the alarm
        syslog.syslog(syslog.LOG_INFO, 'alarm: Alarm expression "%s" evaluated True at %s' % (self.expression, t_str))

        # Form the message text:
        msg_text = 'Alarm expression "%s" evaluated True at %s\nRecord:\n%s' % (self.expression, t_str, str(rec))
        # Convert to MIME:
        msg = MIMEText(msg_text)

        # Fill in MIME headers:
        msg['Subject'] = self.SUBJECT
        msg['From']    = self.FROM
        msg['To']      = ','.join(self.TO)

        try:
            # First try end-to-end encryption
            s = smtplib.SMTP_SSL(self.smtp_host, timeout=self.timeout)
            syslog.syslog(syslog.LOG_DEBUG, "alarm: using SMTP_SSL")
        except (AttributeError, socket.timeout, socket.error):
            syslog.syslog(syslog.LOG_DEBUG, "alarm: unable to use SMTP_SSL connection.")
            # If that doesn't work, try creating an insecure host, then upgrading
            s = smtplib.SMTP(self.smtp_host, timeout=self.timeout)
            try:
                # Be prepared to catch an exception if the server
                # does not support encrypted transport.
                s.ehlo()
                s.starttls()
                s.ehlo()
                syslog.syslog(syslog.LOG_DEBUG,
                              "alarm: using SMTP encrypted transport")
            except smtplib.SMTPException:
                syslog.syslog(syslog.LOG_DEBUG,
                              "alarm: using SMTP unencrypted transport")

        try:
            # If a username has been given, assume that login is required for this host:
            if self.smtp_user:
                s.login(self.smtp_user, self.smtp_password)
                syslog.syslog(syslog.LOG_DEBUG, "alarm: logged in with user name %s" % self.smtp_user)

            # Send the email:
            s.sendmail(msg['From'], self.TO,  msg.as_string())
            # Log out of the server:
            s.quit()
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "alarm: SMTP mailer refused message with error %s" % e)
            raise

        # Log sending the email:
        syslog.syslog(syslog.LOG_INFO, "alarm: email sent to: %s" % self.TO)
```

This service expects all the information it needs to be in the
configuration file `weewx.conf` in a new section called
`[Alarm]`. So, add the following lines to your configuration
file:

``` ini
[Alarm]
    expression = "outTemp < 40.0"
    time_wait = 3600
    smtp_host = smtp.example.com
    smtp_user = myusername
    smtp_password = mypassword
    mailto = auser@example.com, anotheruser@example.com
    from   = me@example.com
    subject = "Alarm message from WeeWX!"
```

There are three important points to be noted in this example, each
marked with a `NOTE` flag in the code.

1.  (Line 40) Here is where the binding happens between an event,
    `weewx.NEW_ARCHIVE_RECORD` in this example, and a member
    function, `self.new_archive_record`. When the event
    `NEW_ARCHIVE_RECORD` occurs, the function
    `self.new_archive_record` will be called. There are many
    other events that can be intercepted. Look in the file
    `weewx/_init_.py`.
2.  (Line 56) Some hardware do not emit all possible observation types in every
    record, so it's possible that a record may be missing some types
    that are used in the expression. This try block will catch the
    `NameError` exception that would be raised should this occur.
3.  (Line 59) This is where the test is done for whether to sound the
    alarm. The `[Alarm]` configuration options specify that the
    alarm be sounded when `outTemp < 40.0` evaluates
    `True`, that is when the outside temperature is below 40.0
    degrees. Any valid Python expression can be used, although the only
    variables available are those in the current archive record.

Another example expression could be:

``` ini
expression = "outTemp < 32.0 and windSpeed > 10.0"
```

In this case, the alarm is sounded if the outside temperature drops
below freezing and the wind speed is greater than 10.0.

Note that units must be the same as whatever is being used in your
database, that is, the same as what you specified in option
[`target_unit`](../../usersguide/weewx-config-file/stdconvert-config/#target_unit).

Option `time_wait` is used to avoid a flood of nearly identical
emails. The new service will wait this long before sending another email
out.

Email will be sent through the SMTP host specified by option
`smtp_host`. The recipient(s) are specified by the comma
separated option `mailto`.

Many SMTP hosts require user login. If this is the case, the user and
password are specified with options `smtp_user` and
`smtp_password`, respectively.

The last two options, `from` and `subject` are optional.
If not supplied, WeeWX will supply something sensible. Note, however,
that some mailers require a valid "from" email address and the one
WeeWX supplies may not satisfy its requirements.

To make this all work, you must first copy the `alarm.py` file to
the `user` directory. Then tell the engine to load this new
service by adding the service name to the list `report_services`,
located in `[Engine]/[[Services]]`:

``` ini
[Engine]
   [[Services]]
        report_services = weewx.engine.StdPrint, weewx.engine.StdReport, user.alarm.MyAlarm
```

Again, note that the option `report_services` must be all on one
line &mdash; the `ConfigObj` parser does not allow options to be
continued on to following lines.

In addition to this example, the distribution also includes a
low-battery alarm (`lowBattery.py`), which is similar, except
that it intercepts LOOP events instead of archiving events.


## Adding a second data source {#Adding_2nd_source}

A very common problem is wanting to augment the data from your weather
station with data from some other device. Generally, you have two
approaches for how to handle this:

-   Run two instances of WeeWX, each using its own database and
    `weewx.conf` configuration file. The results are then
    combined in a final report, using WeeWX's ability [to use more than
    one database](../../custom/multiple_bindings/). See the Wiki entry [*How to
    run multiple instances of
    WeeWX*](https://github.com/weewx/weewx/wiki/weewx-multi) for details
    on how to do this.
-   Run one instance, but use a custom WeeWX service to augment the
    records coming from your weather station with data from the other
    device.

This section covers the latter approach.

Suppose you have installed an electric meter at your house and you wish
to correlate electrical usage with the weather. The meter has some sort
of connection to your computer, allowing you to download the total power
consumed. At the end of every archive interval you want to calculate the
amount of power consumed during the interval, then add the results to
the record coming off your weather station. How would you do this?

Here is the outline of a service that retrieves the electrical
consumption data and adds it to the archive record. It assumes that you
already have a function `download_total_power()` that, somehow,
downloads the amount of power consumed since time zero.

File `user/electricity.py`

``` python
import weewx
from weewx.engine import StdService

class AddElectricity(StdService):

    def __init__(self, engine, config_dict):

      # Initialize my superclass first:
      super(AddElectricity, self).__init__(engine, config_dict)

      # Bind to any new archive record events:
      self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

      self.last_total = None

    def new_archive_record(self, event):

        total_power = download_total_power()

        if self.last_total:
            net_consumed = total_power - self.last_total
            event.record['electricity'] = net_consumed

        self.last_total = total_power
```

This adds a new key `electricity` to the record dictionary and
sets it equal to the difference between the amount of power currently
consumed and the amount consumed at the last archive record. Hence, it
will be the amount of power consumed over the archive interval. The unit
should be Watt-hours.

As an aside, it is important that the function
`download_total_power()` does not delay very long because it will
sit right in the main loop of the WeeWX engine. If it's going to cause
a delay of more than a couple seconds you might want to put it in a
separate thread and feed the results to `AddElectricity` through
a queue.

To make sure your service gets run, you need to add it to one of the
service lists in `weewx.conf`, section `[Engine]`,
subsection `[[Services]]`.

In our case, the obvious place for our new service is in
`data_services`. When you're done, your section
`[Engine]` will look something like this:

``` ini hl_lines="11"
 #   This section configures the internal WeeWX engine.

[Engine]

    [[Services]]
        # This section specifies the services that should be run. They are
        # grouped by type, and the order of services within each group
        # determines the order in which the services will be run.
        xtype_services = weewx.wxxtypes.StdWXXTypes, weewx.wxxtypes.StdPressureCooker, weewx.wxxtypes.StdRainRater, weewx.wxxtypes.StdDelta
        prep_services = weewx.engine.StdTimeSynch
        data_services = user.electricity.AddElectricity
        process_services = weewx.engine.StdConvert, weewx.engine.StdCalibrate, weewx.engine.StdQC, weewx.wxservices.StdWXCalculate
        archive_services = weewx.engine.StdArchive
        restful_services = weewx.restx.StdStationRegistry, weewx.restx.StdWunderground, weewx.restx.StdPWSweather, weewx.restx.StdCWOP, weewx.restx.StdWOW, weewx.restx.StdAWEKAS
        report_services = weewx.engine.StdPrint, weewx.engine.StdReport
```
