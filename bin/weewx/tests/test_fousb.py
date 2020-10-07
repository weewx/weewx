'''
Created on 26.07.2020

@author: edi-x
'''
import unittest
import configobj
import sys
import time
import logging
import os.path
import weewx
from weewx import wxformulas


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
        pass

    def testSpuriousRain(self):
        
        self.assertEqual(self.rain_counter_size, 219, "Rain counter size")
        
        self.loopData(0.00)
        self.assertEqual(self._last_rain_loop, 0.00, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(0.03)
        self.assertEqual(self._last_rain_loop, 0.03, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(0.15)
        self.assertEqual(self._last_rain_loop, 0.15, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(0.30)
        self.assertEqual(self._last_rain_loop, 0.30, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(2.15)
        self.assertEqual(self._last_rain_loop, 2.15, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(0.30)
        self.assertEqual(self._last_rain_loop, 2.15, "")
        self.assertEqual(self._last_spurious_rain_loop, 0.30, "")
        
        self.loopData(0.30)
        self.assertEqual(self._last_rain_loop, 0.30, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
        self.loopData(0.30)
        self.assertEqual(self._last_rain_loop, 0.30, "")
        self.assertEqual(self._last_spurious_rain_loop, None, "")
        
    
    def loopData(self, rain):

        # driver = FineOffsetUSB(**self.config_dict['FineOffsetUSB'])
        packet = {}
        packet['rain'] = rain
        ts = int(time.time() + 0.5)
        packet = self.pywws2weewx(packet, ts,
                         self._last_rain_loop, self._last_rain_ts_loop,
                         self._last_spurious_rain_loop, self.rain_counter_size)
        self._last_rain_loop = packet['rainTotal']
        self._last_rain_ts_loop = ts
        self._last_spurious_rain_loop = packet['spuriousRain']
    
    def pywws2weewx(self, p, ts, last_rain, last_rain_ts, last_spurious_rain, rain_counter_size):
    
        packet = p
        rain_per_bucket_tip = 0.03
        DEBUG_RAIN = True
        
        # calculate the rain increment from the rain total
        # watch for spurious rain counter decrement.  if decrement is significant
        # then it is a counter wraparound.  a small decrement is either a sensor
        # glitch or a read from a previous record.
        total = packet['rain']
        packet['rainTotal'] = packet['rain']
        if DEBUG_RAIN:
            log.debug('rainTotal %s', total)
        if total > (rain_counter_size - 1) * rain_per_bucket_tip:
            log.warn('configured rain_counter_size is too small. rainTotal: %s rainTotalMax: %s',
                     packet['rainTotal'], (rain_counter_size - 1) * rain_per_bucket_tip)
            
        packet['spuriousRain'] = None
        if packet['rain'] is not None and last_rain is not None:
            if packet['rain'] < last_rain:
                pstr = '0x%04x'
                if last_rain - packet['rain'] < (rain_counter_size - 1) * rain_per_bucket_tip * 0.5:
                    print('ignoring spurious rain counter decrement (%s): '
                             'new: %s old: %s' % (pstr, packet['rain'], last_rain))
                    print('last_spurious_rain = %s' % (last_spurious_rain))
                                        
                    if last_spurious_rain is not None and last_spurious_rain == total:
                        # if the small decrement persists
                        # across multiple samples, it was probably a firmware glitch rather than
                        # a sensor glitch or old read.
                        print('got this spurious value a second time -> setting lastRain to this spurious value')
                    else:
                        # ignore current spurious reading and use last one instead
                        packet['rainTotal'] = last_rain
                        packet['spuriousRain'] = total
                    total = None
                else:
                    log.info('rain counter wraparound detected (%s): '
                             'new: %s old: %s max: %s' % (pstr, packet['rain'], last_rain,
                                                          (rain_counter_size - 1) * rain_per_bucket_tip))
                    total += (rain_counter_size) * rain_per_bucket_tip
        packet['rain'] = weewx.wxformulas.calculate_rain(total, last_rain)
    
        # report rainfall in log to diagnose rain counter issues
        if DEBUG_RAIN and packet['rain'] is not None and packet['rain'] > 0:
            log.debug('got rainfall of %.2f cm (new: %.2f old: %.2f)' %
                      (packet['rain'], packet['rainTotal'], last_rain))
    
        return packet


if __name__ == "__main__":
    unittest.main()
    