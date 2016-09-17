# installer for the OpsGenie extesion
# Copyright 2016 Darryn Capes-Davis

from setup import ExtensionInstaller
import configobj

def loader():
    return OpsGenieInstaller()

class OpsGenieInstaller(ExtensionInstaller):
    def __init__(self):
        cf_dict =   {   'OpsGenie': 
                        {
                            'Heartbeat':
                            {
                                'send_heartbeat': 'False',    
                            },               
                            'Alerts':
                            {
                                'TestAlert':   
                                {
                                    'Alias': 'TestAlert',
                                    'Expression': 'outTemp > 0',
                                    'Message': 'Outside temperature greater than zero',
                                    'Description': 'A long description of the event',
                                    'Details': 'outTemp',
                                    'Tags': 'TEST',
                                    'Recipients': 'someone@somewhere.com'
                                }                           
                            }  
                        }
                    }
           
        cf = configobj.ConfigObj(cf_dict)
        cf['OpsGenie']['Heartbeat'].comments['send_heartbeat']={"apiKey = #Set to OpsGenie Heartbeat Integration API Key",
                                                   "heartbeatName = #Set to the name of the heartbeat in OpsGenie"}
        cf['OpsGenie']['Alerts'].comments['TestAlert'] = {"apiKey = #Set OpsGenie Alert apiKey and modify and add alerts below",
                                                       "ExpressionUnits = #Set to units you wish to evaluate expressions in: US, METRIC, METRICWX",
                                                       "Entity = #Can also be set at the Alert level",
                                                       "Source = #Can also be set at the Alert level"}

        super(OpsGenieInstaller, self).__init__(
            version="0.1",
            name='OpsGenie',
            description='OpsGenie - Weewx extension to send OpsGenie Heartbeats and Alerts',
            author="Darryn Capes-Davis",
            author_email="weather@carlingfordweather.sydney",
            restful_services = {"user.opsgenie.OpsGenieHeartbeat", "user.opsgenie.OpsGenieAlerts"},
            config= cf,
            files=[('bin/user', ['bin/user/opsgenie.py'])]
            )
