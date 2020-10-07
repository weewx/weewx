'''
Created on 26.07.2020

@author: edi-x
'''
import unittest
import configobj
import sys
import logging
import os.path
from weewx.drivers import fousb


log = logging.getLogger(__name__)

# Find the configuration file. It's assumed to be in the same directory as me:
config_path = os.path.join(os.path.dirname(__file__), "testgen_fousb.conf")

class FousbTest(unittest.TestCase):

    def setUp(self):
        global config_path

        try:
            self.config_dict = configobj.ConfigObj(config_path, file_error=True, encoding='utf-8')
        except IOError:
            print("Unable to open configuration file %s" % config_path, file=sys.stderr)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            print("Error while parsing configuration file %s" % config_path, file=sys.stderr)
            raise
        self._last_rain_loop = None
        self._last_rain_ts_loop = None
        self._last_spurious_rain_loop = None
        self.rain_counter_size = int(self.config_dict['FineOffsetUSB'].get('rain_counter_size', '0x1000'),16)
        self.max_rain_rate = int(self.config_dict['FineOffsetUSB'].get('max_rain_rate_cmh', '50'),16)

    def testSpuriousRain(self):
        
        self.assertEqual(self.rain_counter_size, 219, "Rain counter size")
        
        self.loopData(38.7,100)
        self.assertEqual(round(self._last_rain_loop,2), 3.87, "normal startup")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(39.0,148)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "0.3 cm rain")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(54.0,196)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "spurious increased value due to high rain rate")
        self.assertEqual(round(self._last_spurious_rain_loop,2), 5.40, "spurious increased value due to high rain rate")
        
        self.loopData(39.0,244)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "decreased to normal value")
        self.assertEqual(self._last_spurious_rain_loop, None, "decreased to normal value")
        
        self.loopData(15.0,292)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "spurious decreased value")
        self.assertEqual(round(self._last_spurious_rain_loop,2), 1.50, "spurious decreased value")
        
        self.loopData(39.0,340)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "increased to normal value")
        self.assertEqual(self._last_spurious_rain_loop, None, "increased to normal value")
        
        self.loopData(15.0, 388)
        self.assertEqual(round(self._last_rain_loop,2), 3.90, "spurious decreased value 2")
        self.assertEqual(round(self._last_spurious_rain_loop,2), 1.50, "spurious decreased value 2")
        
        self.loopData(15.0, 436)
        self.assertEqual(round(self._last_rain_loop,2), 1.50, "spurious value stays the same -> take it as as real")
        self.assertEqual(self._last_spurious_rain_loop, None, "spurious value stays the same -> take it as as real")
        
    
    def loopData(self, rain, ts):

        # driver = FineOffsetUSB(**self.config_dict['FineOffsetUSB'])
        packet = {}
        packet['rain'] = rain
        ts = ts
        packet = fousb.pywws2weewx(packet, ts,
                         self._last_rain_loop, self._last_rain_ts_loop,
                         self._last_spurious_rain_loop, self.rain_counter_size,
                         self.max_rain_rate)
        self._last_rain_loop = packet['rainTotal']
        self._last_rain_ts_loop = ts
        print(self._last_rain_ts_loop)
        self._last_spurious_rain_loop = packet['spuriousRain']
    

if __name__ == "__main__":
    unittest.main()
    