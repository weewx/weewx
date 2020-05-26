# Copyright 2017-2020 Graham Eddy <graham.eddy@gmail.com>
# Distributed under the terms of the GNU Public License (GPLv3)
# weewx:
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your full rights.
"""
alarm module provides weewx service that detects alarm conditions and acts
in response. At present, email is the only response.

* An alarm condition is when the data_type's value exceeds the threshold
  (climbs above for a rising alarm or falls below for a falling alarm).
* Crossing the threshold triggers an action.
* Simply remaining in excess of the threshold does NOT cause a trigger.
* The trigger is re-armed when the alarm condition is no longer met.
* It is possible that a large change in value can cross multiple thresholds
  at once, perhaps triggering a series of actions. These are detected and
  acted upon in order of increasing excessiveness.
* Alarms are only assessed at each ARCHIVE packet.

Configuration parameters:
  [Alarms]
    smtp_server    optional   email relay host (default: 'localhost')
    smtp_user                 not implemented
    smtp_password             not implemented
    mail_from      mandatory  apparent email sender
    mail_to        optional   list of email recipients, can be overriden
                              by individual alarms (default: none, in which
                              case every alarm must specify a value)
    subject_prefix optional   prefix to each email subject line
    units          optional   units system for text produced, including for
                              emails: one of US, METRIC or METRICWX
                              (default: METRIC)

    [[alarm_name]] mandatory  identifies alarm, simple text
      data_type    mandatory  metric being observed, must be a valid
                              weewx data_type
      threshold    mandatory  value at which alarm condition is triggered,
                              either a naked value (in which case no units
                              system conversion) or comma-separated pair
                              of value,unit
      direction   mandatory   must be 'rising' or 'falling'
      mail_to     optional*   list of email recipients that overrides global
                              mail_to (default none, which reqires that global
                              mail_to must be provided)

example of configuration via weewx.conf:
  [Alarms]
      smtp_server = mail.tpg.com.au
      #smtp_user = ignored_not_used
      #smtp_password = ignored_not_used
      mail_from = 'Buxton Wx <weather@geddy.com.au>'
      mail_to = 'Graham Eddy <graham.eddy@gmail.com>'  # should be list, but ok
      subject_prefix = "DW4311: "
      units = METRICWX
 
      [[Hot]]
          data_type = outTemp
          threshold = 30, degree_C
          direction = rising
      [[Very Hot]]
          data_type = outTemp
          threshold = 100, degree_F
          direction = rising
      [[Cold]]
          data_type = outTemp
          threshold = 10, degree_C
          direction = falling
      [[Freezing]]
          data_type = outTemp
          threshold = 0, degree_C
          direction = falling
          mail_to = 'Graham Eddy <graham.eddy@gmail.com>', \
                    'Buxton Trout Farm <buxtontrout@bigpond.com>'
      [[ISS Battery OK]]
          data_type = txBatteryStatus
          threshold = 0, bit    # bit 0 = ISS, clear = battery ok
          direction = falling
      [[River Temp Battery LOW]]
          data_type = txBatteryStatus
          threshold = 1, bit    # bit 1 = additional sensor, set = battery low
          direction = rising
      [[Invalid example]]       # <-- no direction specified
          data_type = outTemp
          threshold = 100, degree_F
"""

import smtplib
from email.mime.text import MIMEText
import logging
import threading

import weewx
import weewx.units
from weewx.engine import StdService
from weeutil.weeutil import timestamp_to_string

log = logging.getLogger(__name__)
version = "3.3"

mailer = None       # sends email by SMTP
presenter = None    # converts between internal format and units system


class ConfigError(Exception):
    pass


class Alarm(object):
    """encapsulates an alarm, including its threshold and response to
       alarm condition"""

    def __init__(self, name, data_type, threshold, is_rising, mail_to):
        """create instance of Alarm
            :arg name           descriptive alarm name
            :arg data_type      metric being monitored
            :arg threshold      value if exceeded causes trigger to fire
            :arg is_rising      True iff triggers on rising above threshold
            :arg mail_to        list of destination mail addresses """

        # saved arguments
        self.name = name
        self.data_type = data_type
        self.threshold = threshold
        self.is_rising = is_rising
        self.mail_to = mail_to

        # instance attributes
        self.is_armed = True         # true iff not yet in alarm condition
        self.threshold_str = None    # cached value

    def __lt__(self, alarm):
        """partial ordering for sorting, ascending threshold then name
            :arg alarm  the other alarm being compared to self
            :result True if other alarm "less than" self """

        return self.threshold < alarm.threshold \
            or (self.threshold == alarm.threshold and self.name < alarm.name)

    def is_condition_met(self, value):
        """alarm condition is met if threshold crossed
            :arg value      observed value
            "return: True iff value exceeds threshold """

        if value is None:
            log.warning(f"{self.__class__.__name__} [{self.name}]"
                        f" {self.data_type} is null so ignored")
            return False

        return (self.is_rising and value >= self.threshold) or \
               (not self.is_rising and value <= self.threshold)

    def get_alarm_message(self, value):
        """create a string describing the alarm condition
            :arg value      observed value
            :return string """

        if not self.threshold_str:
            self.threshold_str = presenter.externalise(self.data_type, self.threshold)
        value_str = presenter.externalise(self.data_type, value)
        sign = '>' if self.is_rising else '<'
        return f"value {value_str} {sign} threshold {self.threshold_str}"

    def assess(self, packet):
        """assess alarm by checking if meets alarm condition and triggering
           action if threshold has just been crossed
            :arg packet     weewx loop/archive record
            :return (nothing) """
        global mailer, presenter

        # extract value from packet
        if self.data_type not in packet:
            log.warning(f"{self.__class__.__name__} [{self.name}] {self.data_type} missing")
            return  # skip this alarm
        value = packet[self.data_type]

        if self.is_condition_met(value):
            if self.is_armed:
                # fire!
                subject = f"Alarm [{self.name}] {self.data_type} {self.get_alarm_message(value)}"
                msg = f"Triggered at {Presenter.epoch_to_string(packet['dateTime'])}"

                try:
                    t = threading.Thread(target=mailer.send, args=(self.mail_to, subject, msg))
                    t.start()
                except threading.ThreadError as e:
                    log.warning(f"{self.__class__.__name__} [{self.name}] thread failed",
                                exc_info=e)
                    # keep armed to try again next time
                else:
                    self.is_armed = False
            else:  # condition continues to be met so don't re-arm
                pass
        else:  # alarm condition no longer met
            if not self.is_armed:
                log.debug(f"{self.__class__.__name__} [{self.name}] re-armed")
            self.is_armed = True


class MaskAlarm(Alarm):
    """encapsulates an alarm that depends upon seeing a bit set/cleared
       rather than having a scalar threshold"""

    def __init__(self, name, data_type, threshold, is_rising, mail_to):
        """create instance of MaskAlarm
            :arg name       descriptive alarm name
            :arg data_type  metric being monitored
            :arg threshold  value if exceeded causes trigger to fire
            :arg is_rising  True iff triggers on rising above threshold
            :arg mail_to    list of destination mail addresses """
        super(MaskAlarm, self).__init__(name, data_type, threshold, is_rising,
                                        mail_to)

    def is_condition_met(self, value):
        """alarm condition is met if specific bit is set/cleared"""

        mask = 0x00 if value is None else int(value)
        return (self.is_rising and mask & self.threshold) or \
               (not self.is_rising and not mask & self.threshold)

    def get_alarm_message(self, value):
        """alarm description for bit set/cleared"""

        return "set" if self.is_rising else "cleared"


class Mailer(object):

    def __init__(self, smtp_server, smtp_user, smtp_password, mail_from, subject_prefix):
        """create instance of Mailer
            :arg smtp_server    hostname of SMTP server (often 'localhost')
            :arg smtp_user      ignored
            :arg smtp_password  ignored
            :arg mail_from      email address of sender
            :arg subject_prefix prepended to email's subject text """

        # saved arguments
        self.smtp_server = smtp_server
        self.smtp_user = smtp_user          # not used
        self.smtp_password = smtp_password  # not used
        self.mail_from = mail_from
        self.subject_prefix = subject_prefix if subject_prefix else ""

    def send(self, mail_to, subject, msg):

        # compose email
        body = MIMEText(f'{msg}\n')
        body['Subject'] = self.subject_prefix + subject
        body['From'] = self.mail_from
        body['To'] = ', '.join(mail_to)

        # send it via relay. assumes no authentication required
        smtp = None
        try:
            smtp = smtplib.SMTP(self.smtp_server)
            smtp.sendmail(body['From'], body['To'], body.as_string())
            log.info(f"{self.__class__.__name__}: sent: {subject}")
        except smtplib.SMTPException as e:
            log.error(f"{self.__class__.__name__}: SMTP send failed: {subject}", exc_info=e)
        finally:
            if smtp:
                smtp.quit()


class Presenter(object):
    """converts values to/from display format for units system"""

    def __init__(self, units):
        """create instance of Presenter
            :arg units      name of units system for values presented"""

        # instance attributes
        self.units_system = weewx.units.unit_constants[units]
                                    # units system (US, METRIC or METRICWX)

    def externalise(self, data_type, value):
        """convert internal weewx format value to string as required by
           units system"""

        unit_type, unit_group = weewx.units.StdUnitConverters[weewx.US].getTargetUnit(data_type)
        vt = weewx.units.ValueTuple(value, unit_type, unit_group)
        vh = weewx.units.ValueHelper(vt,
                                     converter=weewx.units.StdUnitConverters[self.units_system])
        return vh.toString(addLabel=True)

    @staticmethod
    def epoch_to_string(epoch):
        """convert epoch time to string"""

        return timestamp_to_string(epoch)[:19]

    @staticmethod
    def internalise(data_type, unit_type, value):
        """convert readable value in unit system to internal weewx format
            :arg data_type  metric being observed e.g. outTemp
            :arg unit_type  value type e.g. mbar
            :arg value      observed value
             :return ValueHelper """

        unit_group = weewx.units.obs_group_dict[data_type]
        vt = weewx.units.ValueTuple(value, unit_type, unit_group)
        vh = weewx.units.ValueHelper(vt, converter=weewx.units.StdUnitConverters[weewx.US])
        return vh.raw


class AlarmsMgr(StdService):
    """service that detects and responds to alarm conditions"""

    def __init__(self, engine, config_dict):
        super(AlarmsMgr, self).__init__(engine, config_dict)
        global mailer, presenter

        alarm_count = 0
        try:
            log.debug(f"{self.__class__.__name__} starting")

            # ### initialisation

            # instance attributes
            self.alarms = None     # list of alarms in correct processing order

            try:
                # global parameters
                alarms_stanza = config_dict['Alarms']

                # mailer
                smtp_server = alarms_stanza['smtp_server']
                smtp_user = None
                smtp_password = None
                mail_from = alarms_stanza['mail_from']
                mail_to = alarms_stanza.get('mail_to', None)
                if mail_to and isinstance(mail_to, str):
                    mail_to = [mail_to]
                subject_prefix = alarms_stanza.get('subject_prefix', None)
                mailer = Mailer(smtp_server, smtp_user, smtp_password,
                                mail_from, subject_prefix)
            except KeyError as e:
                raise ConfigError(f"missing parameter: {e.args[0]}")

            # units system
            units = alarms_stanza.get('units', 'METRIC')
            presenter = Presenter(units)
            
            # ### create alarm definitions

            rising_alarms = []
            falling_alarms = []
            for alarm_name, alarm_dict in alarms_stanza.items():
                if isinstance(alarm_dict, dict):
                    alarm_count += 1
                    try:
                        # data_type is mandatory.
                        # just a name
                        data_type = alarm_dict['data_type']

                        # threshold is mandatory.
                        # should be a [value, unit] list with special case
                        #     for bit spec [bit#, 'bit']
                        # a bare string is taken as raw value
                        is_bit = False
                        value = alarm_dict['threshold']
                        if isinstance(value, str):
                            threshold = float(value)        # raw scalar
                        elif value[1] == 'bit':
                            threshold = 0x01 << int(value[0])  # mask
                            is_bit = True
                        else:
                            threshold = Presenter.internalise(data_type, value[1], float(value[0]))

                        # direction is mandatory.
                        # must be either 'rising' or 'falling'
                        is_rising = False
                        value = alarm_dict['direction']
                        if value == 'rising':
                            is_rising = True
                        elif value == 'falling':
                            pass
                        else:
                            raise ConfigError(f"invalid: direction={value}")

                        # mail_to is optional if global mail_to is provided.
                        # convert to list if singleton string
                        alarm_mail_to = alarm_dict.get('mail_to', None)
                        if not alarm_mail_to and not mail_to:
                            raise ConfigError(f"missing parameter: mail_to")
                        if isinstance(alarm_mail_to, str):   # should be a list
                            alarm_mail_to = [alarm_mail_to]

                    except (IndexError, KeyError, ValueError, ConfigError) as e:
                        log.warning(f"{self.__class__.__name__} [{alarm_name}] config error",
                                    exc_info=e)
                        continue  # skip this alarm

                    # create alarm.
                    # segregate rising from falling alarms for now
                    alarm = (MaskAlarm if is_bit else Alarm)(
                                  alarm_name, data_type, threshold, is_rising,
                                  alarm_mail_to if alarm_mail_to else mail_to)
                    if is_rising:
                        rising_alarms.append(alarm)
                    else:
                        falling_alarms.append(alarm)

            # ### merge rising_ and falling_ into single alarm list

            # partially sort. it is sufficient that inferior alarms are
            # processed before related superior alarms, no stronger
            # ordering is necessary
            rising_alarms.sort()        # smallest to largest rising threshold
            falling_alarms.sort(reverse=True)
                                        # largest to smallest falling threshold
            self.alarms = rising_alarms + falling_alarms

        except ConfigError as e:
            log.error(f"{self.__class__.__name__}: config: {e.args[0]}")
            self.alarms = None

        # ### bind to listening loop (if we have work to do)

        if not self.alarms:
            log.error(f"{self.__class__.__name__}: not started (version {version}): no alarms")
            return  # just slip away without binding to any listeners...

        # start listening to new packets
        #hmm... self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_record)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info(f"{self.__class__.__name__} started (version {version}): {len(self.alarms)}"
                 f" alarms ({alarm_count - len(self.alarms)} skipped)")

    def new_archive_record(self, event):
        """handle ARCHIVE record by dispatching any alarms triggered"""
        self.assess(event.record)

    #def new_loop_record(self, event):
    #    """handle LOOP record by dispatching any alarms triggered"""
    #    self.assess(event.packet)

    def assess(self, packet):
        """assess all alarms against incoming packet"""
        for alarm in self.alarms:
            alarm.assess(packet)
