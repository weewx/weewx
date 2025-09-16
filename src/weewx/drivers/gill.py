'''
Driver for the Gill MetConnect Series of weatherstations (i.e MX500)

This driver has been tested with the stations MX400, MX500 and MX600
however more models may be compatible.

You are required to configure your reciever to send data over serial
with gill metset - https://gillinstruments.com/downloads/metset-download-form/
and then download your .mcf config file to get data packet structure,

V 1.3
https://github.com/Cosmospacedog
https://siriusinsight.ai
'''
import socket
import logging
import time

import xml.etree.ElementTree as ET


import weewx.drivers
from weewx.units import ValueTuple,convert

DRIVER_NAME = 'Gill'
DRIVER_VERSION = '1.3'

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

if not log.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

#This dictionary controls the format wwewx extracts data from the
#config file.
#
#Structured as:
# weewx_gill_mapping
# ├── group
# │   ├── vals
# │   │   ├── value type 1   : [preferred source, secondary source...]
# │   │   └── value type 2   : [preferred source, secondary source...]
# │   ├── units
# │   │   ├── default : (standard unit, conversion rate)
# │   │   ├── TBD     : (None, -1)
# │   │   ├── Unit1   : (weewx unit 1, conversion rate)
# │   │   └── Unit2   : (weewx unit 2, conversion rate)
# │   └── config      : Path to unit variable in config or None if there is only one unit avaliable

weewx_gill_mapping = {
    'group_direction':{
        'vals':{
            'gustdir':[
                'CGDIR',
                'GDIR',
            ],
            'windDir':[
                'DIR',
                'CDIR'
            ]
        },
        'units':{
            'default':('degree_compass',1)
        },
        'config':None
    },
    'group_percent':{
        'vals':{
            'outHumidity':[
                'RH'
            ]
        },
        'units':{
            'default':('percent',1)
        },
        'config':None
    },
    'group_pressure':{
        'vals':{
            'barometer':[
                'PSTN'
            ],
            'altimeter':[
                'PASL'
            ],
            'pressure':[
                'PRESS'
            ]
        },
        'units':{
            'default':('mbar',1),
            'TBD':(None,-1),
            'HPA':('hPa',1),
            'MB':('mbar',1),
            'MMHG':('inHg',25.4),
            'INHG':('inHg',1)
        },
        'config':".//category[@name='Pressure']/param[@name='Pressure Units']/valuestring"
    },
    'group_rain':{
        'vals':{
            'rain':[
                'PRECIPT'
            ]
        },
        'units':{
            'default':('mm',1),
            'TBD':(None,-1),
            'MM':('mm',1),
            'IN':('inch',1)
        },
        'config':".//category[@name='Precipitation']/param[@name='Precipitation Units']/valuestring"
    },
    'group_rainrate':{
        'vals':{
            'rainRate':[
                'PRECIPI'
            ]
        },
        'units':{
            'default':('mm_per_hour',1),
            'TBD':(None,-1),
            'MM':('mm_per_hour',1),
            'IN':('inch_per_hour ',1)
        },
        'config':".//category[@name='Precipitation']/param[@name='Precipitation Units']/valuestring"
    },
    'group_speed':{
        'vals':{
            'windSpeed':[
                'CSPEED',
                'AVGCSPEED',
                'SPEED',
                'AVGSPEED'
            ],
            'windGust':[
                'CGSPEED',
                'GSPEED'
            ]
        },
        'units':{
            'default':('meter_per_second ',1),
            'TBD':(None,-1),
            'MS':('meter_per_second ',1),
            'KTS':('knot',1),
            'MPH':('mile_per_hour',1),
            'KPH':('km_per_hour',1),
            'FPM':('mile_per_hour',1/88)
        },
        'config':".//category[@name='Wind']/param[@name='Wind speed Units']/valuestring"
    },
    'group_temperature':{
        'vals':{
            'outTemp':[
                'TEMP'
            ],
            'heatindex':[
                'HEATIDX'
            ],
            'windchill':[
                'WCHILL'
            ],
            'dewpoint':[
                'DEWPOINT'
            ]
        },
        'units':{
            'default':('degree_C',1),
            'TBD':(None,-1),
            'C':('degree_C',1),
            'F':('degree_F',1),
            'K':('degree_K',1)
        },
        'config':".//category[@name='Temperature']/param[@name='Temperature Units']/valuestring"

    },
    'group_volt':{
        'vals':{
            'supplyVoltage':[
                'VOLT'
            ]
        },
        'units':{
            'default':('volt',1)
        },
        'config':None
    }
}


class Gill(weewx.drivers.AbstractDevice):
    '''
    Driver to communicate between weewx and Gill Metconnect Devices
    '''
    def __init__(self,ip_addr:str,port:int,sample_rate:int,config_path:str) -> None:
        #Private value initialisation
        self.__ip_addr = ip_addr
        self.__port = port
        self.__sample_rate = sample_rate

        self.network_stream = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.network_stream.connect((self.__ip_addr,self.__port))

        #Build output framework
        self._output_map = {}
        self._value_string = None
        self._weewx_map = None
        self._config = ET.parse(config_path)
        self._config_root = self._config.getroot()

        #Pull config information
        self._hardware_name = self._config_root.find(
            ".//device"
        ).get('name')

        self._initalise_packet_map()

    @property
    def hardware_name(self):
        '''
        Get Gill Model
        '''
        return self._hardware_name


    def _initalise_packet_map(self) -> None:
        '''
        Generate our weewx output format to match weatherstation configuration
        '''

        #Pull Config String - Like
        value_string = self._config_root.find(
            ".//category[@name='Reporting']/param[@name='Report Format']/reportvalue"
        )

        #Split up config string
        self._value_string = value_string.text.split(' ')

        #Iterate through each weewx field and find if the station is transmitting
        #it. If it is - build a tuple ->
        #weewx unit:(GILL unit,gill unit group,(weewx unit,conversion rate))

        for group,group_data in weewx_gill_mapping.items():
            for value_map,value in group_data['vals'].items():
                for key in value:
                    if key not in self._value_string:
                        continue
                    config = group_data['config']

                    if config is None:
                        unit =group_data['units']['default']
                    else:
                        unit = group_data['units'][
                            self._config_root.find(
                                config
                            ).text
                        ]

                    self._output_map[value_map] = (key,group,unit)

    def proccess_packet(self, data_out) -> dict:
        '''
        Proccess an array packet to match the provided gill encoding
        '''
        packet = {
                'dateTime': int(time.time() + 0.5),
                'usUnits': weewx.METRICWX
            }
        for field,value in self._output_map.items():
            index = self._value_string.index(value[0])
            tuple_temp = ValueTuple(float(data_out[index])*value[2][1],value[2][0],value[1])
            normalised_data = convert(
                tuple_temp,weewx_gill_mapping[value[1]]['units']['default'][0]
                )
            packet[field] = normalised_data[0]
        logging.info(packet)
        return packet

    def genLoopPackets(self):
        while True:
            time.sleep(self.__sample_rate)

            data =  self.network_stream.recv(
                1024).decode(errors="ignore").strip()  # read up to 1024 bytes at a time

            #Bad sync -> go to generate new packet
            if not data.lstrip('\x02').split(',')[0].isalpha():
                continue

            packet_size = len(self._value_string) + 1 #one more for checksum

            #Missed packet end -> cache current data and request the rest
            if len(data.strip().split(',')) < packet_size:
                logging.info("Failed Sync")

                while len(data.strip().split(',')) != packet_size:
                    logging.info("Data Apeended")
                    buffer = str(data)
                    data =  self.network_stream.recv(1024).decode(errors="ignore").strip()
                    data = buffer + data
                    print (data)

            current_values = data.strip().split(',')

            # Final check if packet is legit
            if len(current_values) != packet_size:
                logging.info("Failed Size")
                continue

            #load values into packet
            yield self.proccess_packet(current_values)

def loader(config_dict, engine):
    gill_config = config_dict['Gill']
    return Gill(
        gill_config['eth_address'],
        int(gill_config['eth_port']),
        int(gill_config['sample_rate']),
        gill_config['gill_config'],
    )

class GillConfEditor(weewx.drivers.AbstractConfEditor):
    '''
    Generate default config
    '''
    @property
    def default_stanza(self):
        '''
        Returns defaults
        '''
        return """
[Gill]
    # This section is for the Gill MetConnect series of weather stations

    # Connection type: serial or ethernet
    # serial (via a com port or tty USB device)
    # ethernet (via a TCP connection i.e a MOXA or DIGI device port)
    type = ethernet

    # Internal IPV4 adress of the weather station
    eth_address = x.x.x.x

    # port your Gill device operates on - typically 4001 for a tcp connection
    eth_port = 4001

    serial_port = /dev/ttyUSB0

    gps = 0

    gill_config = /x/x/config.mcf
    ###############################################################
    #  Advanced Config

    sample_rate = 1

    driver = user.gill
"""
