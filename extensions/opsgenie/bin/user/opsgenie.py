#==============================================================================
#                    OpsGenie
#==============================================================================
"""OpsGenie extension to weewx to post Heartbeats and Alerts to OpsGenie"""

import Queue
import threading
import syslog
import json

import weewx
import weewx.units
from weewx.units import ValueTuple
from weeutil.weeutil import option_as_list
from weeutil.weeutil import to_bool, accumulateLeaves
from weewx.restx import StdRESTful, RESTThread

class OpsGenieHeartbeat(StdRESTful):
    """Class for sending an OpsGenie heartbeat

    To enable this module, add the following to weewx.conf:

    [OpsGenie]
        [[Heartbeat]]
            send_heartbeat = True
            apiKey = 
            heartbeatName = 

    This will periodically do a http GET with the following information:

        apiKey              OpsGenie API Heartbeat Key
        heartbeatName       Name of the heartbeat (must already be created in OpsGenie)

    """

    archive_url = 'https://api.opsgenie.com/v1/json/heartbeat/send/'

    def __init__(self, engine, config_dict):
        
        super(OpsGenieHeartbeat, self).__init__(engine, config_dict)
        
        # Extract the required parameters. If one of them is missing,
        # a KeyError exception will occur. Be prepared to catch it.
        try:
            # Extract a copy of the dictionary with the registry options:
            _opsgenie_dict = accumulateLeaves(config_dict['OpsGenie']['Heartbeat'], max_level=1)

            # Should the service be run?
            if not to_bool(_opsgenie_dict.pop('send_heartbeat', False)):
                syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieHeartbeat: "
                          "Send Heartbeat not requested.")
                return

            if _opsgenie_dict['apiKey'] is None:
                raise KeyError("apiKey")
            if _opsgenie_dict['heartbeatName'] is None:
                raise KeyError("heartbeatName")
        except KeyError, e:
            syslog.syslog(syslog.LOG_DEBUG, "restx: OpsGenieHeartbeat: "
                          "Heartbeats will not be sent. Missing option {}".format(e))
            return

        self.archive_queue = Queue.Queue()
        self.archive_thread = OpsGenieHeartbeatThread(self.archive_queue,
                                                    **_opsgenie_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieHeartbeat: "
                      "Heartbeats will be sent.")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)
        
class OpsGenieHeartbeatThread(RESTThread):
    """Concrete threaded class for sending OpsGenie heartbeats."""
    
    def __init__(self, queue, apiKey, heartbeatName,
                 server_url=OpsGenieHeartbeat.archive_url,
                 post_interval=300, max_backlog=0, stale=None,
                 log_success=True, log_failure=True,
                 timeout=60, max_tries=1, retry_wait=5):
        """Initialize an instance of OpsGenieHeartbeatThread.
        
        Required parameters:

          queue: An instance of Queue.Queue where the records will appear.

          apiKey: OpsGenie heartbeat api key

          heartbeatName : OpsGenie heartbeat name

        Optional parameters:
        
          server_url: The OpsGenie heartbeat URL. 
          Default is 'https://api.opsgenie.com/v1/json/heartbeat/send/'
          
          post_interval: How long to wait between posts.
          Default is 300 seconds (5 minutes).
          
          max_backlog: How many records are allowed to accumulate in the queue
          before the queue is trimmed.
          Default is zero (no backlog at all).
          
          stale: How old a record can be and still considered useful.
          Default is None (never becomes too old).
          
          log_success: If True, log a successful post in the system log.
          Default is True.
          
          log_failure: If True, log an unsuccessful post in the system log.
          Default is True.
          
          timeout: How long to wait for the server to respond before giving up.
          Default is 10 seconds.        

          max_tries: How many times to try the post before giving up.
          Default is 3
          
          retry_wait: How long to wait between retries when failures.
          Default is 5 seconds.
        """

        super(OpsGenieHeartbeatThread, self).__init__(queue,
                                                    protocol_name='OpsGenieHeartbeat',
                                                    post_interval=post_interval,
                                                    max_backlog=max_backlog,
                                                    stale=stale,
                                                    log_success=log_success,
                                                    log_failure=log_failure,
                                                    timeout=timeout,
                                                    max_tries=max_tries,
                                                    retry_wait=retry_wait)
        self.server_url = server_url
        self.apiKey   = apiKey
        self.heartbeatName = heartbeatName
        
    def get_record(self, dummy_record, dummy_manager):
        _record = {}
        _record['apiKey']   = self.apiKey
        _record['name']   = self.heartbeatName
        _record['usUnits'] = weewx.US
        
        return _record
        
    def format_url(self, record):
        """Return an URL for posting using the OpsGenie protocol."""
        return self.server_url

    def format_data(self, record):
        """Return Data for posting to OpsGenie Restful interface"""
        #need to pop usUnits as OpsGenie will not be expecting
        record.pop('usUnits', None)
        syslog.syslog(syslog.LOG_DEBUG, "restx: OpsGenieHeartbeat: format_data: {}".format(json.dumps(record)))
        return json.dumps(record)

class OpsGenieAlerts(StdRESTful):
    """Class for spawning OpsGenie alert threads

    OpsGenie Alerts config weewx.conf:

    [OpsGenie]
	    [[Alerts]]
		    apiKey = 
		    ExpressionUnits = METRICWX
		    Recipients = 
		    Entity = 
		    Source = 
		    Tags = 
		    Actions = 

		    [[[IsRaining]]]
			    Expression = precipType > 0
			    Alias = IsRaining
			    Message = It is Raining
			    Description = Test Description
			    Details = precipType, rainRate

        Global Options
        
        apiKey              OpsGenie API Integration Key [Required]
        ExpressionUnits     Units that expression statements are written in. Conversions will be done
                            for each loop packet. This is global for all alerts as this is done at the
                            Service Level [Optional: If not provided default will be database units]

        A thread will be created for each alert and the expression evaluated on each
        loop packet. Each alert will look for parent config values under [[Alerts]]

            Alias               An alias for the OpsGenie alert. OpsGenie will treat subsequent triggering of this
                                alert as the same due to the same alias being passed. [Required]
            Recipients          Comma separated list of OpsGenie recipients. Must match a valid OpsGenie recipient
                                which include Users, and Schedules. For users you MUST use the user email address!
                                Use a User for a free OpsGenie account. [Optional: Recpients can be left blank if 
                                you have configured this in the OpsGenie integration]
            Entity              What you wish passed to OpsGenie as an Entity [Optional]
            Source              What you wish passed to OpsGenie as an Source [Optional]
            Tags                What you wish passed to OpsGenie as Tags [Optional]
            Actions             What you wish passed to OpsGenie as custom Actions [Optional]
            Expression          Valid Python expression using valid Weewx observation types [Required]
            Message             A message for the alert [Required]
            Description         A longer description for the alert [Optional]
            Details             OpsGenie allows passing of detail properties with an alert. This Weewx implementation
                                will pass observations as details based on units set with ExpressionUnits. Provide a comma 
                                separated list of ovbservation details you wish to pass. [Optional][Max 8000 chars for 
                                the nested JSON map that will be created]

            See https://www.opsgenie.com/docs/web-api/alert-api#createAlertRequest for more details on these fields.
            NOTE: The exact implementation and effect of these fields will depend on your OpsGenie API integration.
            Those supported by this implementation generally support the default OpsGenie API integration.

    """

    alert_url = 'https://api.opsgenie.com/v1/json/alert/' 

    def __init__(self, engine, config_dict):
        
        super(OpsGenieAlerts, self).__init__(engine, config_dict)
        
        if not config_dict['OpsGenie'].has_key('Alerts'):
            syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieAlerts: no Alerts section! No alerts will be set")
            return

        if not config_dict['OpsGenie']['Alerts'].has_key('apiKey'):
            syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieAlerts: no apiKey! No alerts will be set")
            return

        if config_dict['OpsGenie']['Alerts'].has_key('ExpressionUnits'):
            if config_dict['OpsGenie']['Alerts']['ExpressionUnits'] == "US":
                self.unit_system = weewx.US
            if config_dict['OpsGenie']['Alerts']['ExpressionUnits'] == "METRIC":
                self.unit_system = weewx.METRIC
            if config_dict['OpsGenie']['Alerts']['ExpressionUnits'] == "METRICWX":
                self.unit_system = weewx.METRICWX
        else:
            self.unit_system = None
         
        self.alerts = dict()
                        
        for subsection in config_dict['OpsGenie']['Alerts'].sections:
            alert_config = accumulateLeaves(config_dict['OpsGenie']['Alerts'][subsection], max_level=1)
            
            if not alert_config.has_key('Alias'):
                syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieAlerts: Missing Alias in config section: ".format(subsection))
                continue
            
            self.alerts[subsection] = dict()            
            self.alerts[subsection]['Alias'] = alert_config['Alias']

            try:
                if alert_config['Expression'] is None:
                    raise KeyError("Expression")
                if alert_config['Message'] is None:
                    raise KeyError("Message")
            except KeyError, e:
                syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieAlerts: "
                                "Missing option {} for Alert: {}".format(e, self.alerts[subsection]['Alias']))
                return

            self.alerts[subsection]['Expression'] = alert_config['Expression']
            self.alerts[subsection]['AlertActive'] = False

            self.alerts[subsection]['my_queues'] = Queue.Queue()
            self.alerts[subsection]['my_threads'] = OpsGenieAlertsThread(self.alerts[subsection]['my_queues'],
                                                        alert_config)
            self.alerts[subsection]['my_threads'].start()
            syslog.syslog(syslog.LOG_INFO, "restx: OpsGenieAlerts: "
                          "Alerts will be created for {}.".format(self.alerts[subsection]['Alias']))

        #bind one packet loop. 
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
    
    def shutDown(self):
        for subsection in self.my_threads:
            StdRESTful.shutDown_thread(self.alerts[subsection]['my_queues'], self.alerts[subsection]['my_threads'])

    #packet loop 
    def new_loop_packet(self, event):
        targetUnits = self.unit_system
        if targetUnits is None:
            targetUnits = event.packet['usUnits']

        _record = weewx.units.to_std_system(event.packet, targetUnits)

        for subsection in self.alerts:
            try:
                if eval(self.alerts[subsection]['Expression'], None, _record):
                    if not self.alerts[subsection]['AlertActive']:
                        self.alerts[subsection]['AlertActive'] = True
                        self.alerts[subsection]['my_queues'].put(_record)
                else:
                    self.alerts[subsection]['AlertActive'] = False
            except Exception:
                syslog.syslog(syslog.LOG_CRIT, "restx: OpsGenieAlerts: Exception while evaluation expression for {}".format(self.alerts[subsection]['Alias']))
                weeutil.weeutil.log_traceback('*** ', syslog.LOG_DEBUG)            
        
class OpsGenieAlertsThread(RESTThread):
    """Concrete threaded class for sending OpsGenie alerts."""
    
    def __init__(self, queue, alert_dict,
                 server_url=OpsGenieAlerts.alert_url,
                 post_interval=3600, max_backlog=0, stale=None,
                 log_success=True, log_failure=True,
                 timeout=60, max_tries=1, retry_wait=5):
        """Initialize an instance of OpsGenieAlertsThread.
        
        Required parameters:

          queue: An instance of Queue.Queue where the records will appear.

          alert: Name of the alert for tracking.
          
          config: Config dictionary for the alert.  

        Optional parameters:
        
          server_url: The OpsGenie alert URL. 
          Default is 'https://api.opsgenie.com/v1/json/alert'
          
          post_interval: How long to wait between alert notifications.
          Default is 3600 seconds (1 hour).
          
          max_backlog: How many records are allowed to accumulate in the queue
          before the queue is trimmed.
          Default is zero (no backlog at all).
          
          stale: How old a record can be and still considered useful.
          Default is None (never becomes too old).
          
          log_success: If True, log a successful post in the system log.
          Default is True.
          
          log_failure: If True, log an unsuccessful post in the system log.
          Default is True.
          
          timeout: How long to wait for the server to respond before giving up.
          Default is 10 seconds.        

          max_tries: How many times to try the post before giving up.
          Default is 3
          
          retry_wait: How long to wait between retries when failures.
          Default is 5 seconds.
        """

        super(OpsGenieAlertsThread, self).__init__(queue,
                                                    protocol_name='OpsGenieAlert',
                                                    post_interval=post_interval,
                                                    max_backlog=max_backlog,
                                                    stale=stale,
                                                    log_success=log_success,
                                                    log_failure=log_failure,
                                                    timeout=timeout,
                                                    max_tries=max_tries,
                                                    retry_wait=retry_wait)
        self.server_url = server_url
        self.apiKey = alert_dict['apiKey']
        self.Alias = alert_dict['Alias']
        self.Message = alert_dict['Message']
        self.Recipients = option_as_list(alert_dict.get('Recipients'))
        self.Entity = alert_dict.get('Entity') 
        self.Source = alert_dict.get('Source')     
        self.Tags = alert_dict.get('Tags')   
        self.Actions = alert_dict.get('Actions') 
        self.Description = alert_dict.get('Description') 
        self.Details = option_as_list(alert_dict.get('Details'))
        
    def get_record(self, record, dummy_manager):
        _record = {}
        _record['apiKey'] = self.apiKey
        _record['message'] = self.Message
        _record['alias'] = self.Alias
        _record['recipients'] = self.Recipients
        _record['entity'] = self.Entity
        _record['source'] = self.Source
        _record['tags'] = self.Tags
        _record['actions'] = self.Actions
        _record['description'] = self.Description
        _record['details'] = dict()

        for detail in self.Details:
            vt = weewx.units.as_value_tuple(record, detail)
            vh = weewx.units.ValueHelper(vt, converter=weewx.units.StdUnitConverters[record['usUnits']])
            _record['details'][detail] = vh.toString()

        _record['usUnits'] = weewx.US
        
        return _record
        
    def format_url(self, record):
        """Return an URL for posting using the OpsGenie Alert protocol."""
        return self.server_url

    def format_data(self, record):
        """Return Data for posting to OpsGenie Alert interface"""
        #need to pop usUnits as OpsGenie will not be expecting
        record.pop('usUnits', None)
        json_data = json.dumps(record)
        syslog.syslog(syslog.LOG_DEBUG, "restx: OpsGenieAlerts: {}: JSON: {!r}".format(self.Alias, json_data))
        return json_data