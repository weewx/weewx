#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Test routines for weeutil.weeutil."""

import unittest
import time

from weeutil.weeutil import startOfInterval, option_as_list, TimeSpan, genYearSpans, genMonthSpans, genDaySpans
from weeutil.weeutil import archiveDaySpan, archiveWeekSpan, archiveMonthSpan, archiveYearSpan, archiveRainYearSpan
from weeutil.weeutil import startOfDay, startOfArchiveDay, timestamp_to_string, intervalgen, stampgen

class WeeutilTest(unittest.TestCase):
    
    def test_option_as_list(self):

        self.assertEqual(option_as_list("abc"), ['abc'])
        self.assertEqual(option_as_list(['a', 'b']), ['a', 'b'])
        self.assertEqual(option_as_list(None), None)
        self.assertEqual(option_as_list(''), [''])
        
    def test_stampgen(self):
        
        # This is over a DST boundary:
        start = time.mktime((2013,3,10,0,0,0,0,0,-1))
        stop  = time.mktime((2013,3,10,6,0,0,0,0,-1))
        print timestamp_to_string(start)
        print timestamp_to_string(stop)
        
        for ts, check_ts in zip(stampgen(start, stop, 1800), [1362902400,1362904200,1362906000,1362907800,
                                                              1362909600,1362911400,1362913200,1362915000,
                                                              1362916800,1362918600,1362920400]):
            print timestamp_to_string(ts)
            self.assertEqual(ts, check_ts)

    def test_startOfInterval(self):
    
        t_length = 1 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 57,  0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 5 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 55,  0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 1 * 60
        t_test = time.mktime((2009, 3, 4, 1,  0, 0, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 0, 59, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 5 * 60
        t_test = time.mktime((2009, 3, 4, 1,  0, 0, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 0, 55, 0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 10 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 50,  0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 15 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 45,  0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 20 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 40,  0, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 30 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 30, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 60 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 1, 00, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        t_length = 120 * 60
        t_test = time.mktime((2009, 3, 4, 1, 57, 17, 0, 0, 0))
        t_ans  = time.mktime((2009, 3, 4, 0, 00, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
        
        # Do a test over the spring DST boundary
        # This is 03:22:05 DST, just after the change over.
        # The correct answer is 02:00:00 DST.
        t_length = 120 * 60
        t_test = time.mktime((2009, 3, 8, 3, 22, 05, 0, 0, 1))
        t_ans  = time.mktime((2009, 3, 8, 2, 00, 00, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
        
        # Do a test over the fall DST boundary.
        # This is 01:22:05 DST, just before the change over.
        # The correct answer is 00:00:00 DST.
        t_length = 120 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 05, 0, 0, 1))
        t_ans  = time.mktime((2009, 11, 1, 0,  0,  0, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        # Do it again, except after the change over
        # This is 01:22:05 ST, just after the change over.
        # The correct answer is 00:00:00 ST (which is 01:00:00 DST).
        t_length = 120 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 05, 0, 0, 0))
        t_ans  = time.mktime((2009, 11, 1, 0, 00, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        # Once again at 01:22:05 ST, just before the change over, but w/shorter interval
        t_length = 5 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 05, 0, 0, 1))
        t_ans  = time.mktime((2009, 11, 1, 1, 20, 00, 0, 0, 1))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        # Once again at 01:22:05 ST, just after the change over, but w/shorter interval
        t_length = 5 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 05, 0, 0, 0))
        t_ans  = time.mktime((2009, 11, 1, 1, 20, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
        # Once again at 01:22:05 ST, just after the change over, but with 1 hour interval
        t_length = 60 * 60
        t_test = time.mktime((2009, 11, 1, 1, 22, 05, 0, 0, 0))
        t_ans  = time.mktime((2009, 11, 1, 1, 00, 00, 0, 0, 0))
        t_start = startOfInterval(t_test, t_length)
        self.assertEqual(t_start, t_ans)
    
    def test_TimeSpans(self):
    
        t = TimeSpan(1230000000, 1231000000)
        # Reflexive test:
        self.assertEqual(t, t)
        tsub = TimeSpan(1230500000, 1230600000)
        self.assertTrue(t.includes(tsub))
        self.assertFalse(tsub.includes(t))
        tleft = TimeSpan(1229000000, 1229100000)
        self.assertFalse(t.includes(tleft))
        tright = TimeSpan(1232000000, 1233000000)
        self.assertFalse(t.includes(tright))
        
        dic={}
        dic[t] = 't'
        dic[tsub] = 'tsub'
        dic[tleft] = 'tleft'
        dic[tright] = 'tright'
        
        self.assertEqual(dic[t], 't')
    
    def test_genYearSpans(self):

        # Should generate years 2007 through 2008:"
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts = time.mktime((2008, 3, 1, 0, 0, 0, 0, 0, -1))

        yearlist = [span for span in genYearSpans(start_ts, stop_ts)]
        
        expected = ["[2007-01-01 00:00:00 PST (1167638400) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2009-01-01 00:00:00 PST (1230796800)]"]

        for got, expect in zip(yearlist, expected):
            self.assertEqual(str(got), expect)

    def test_genMonthSpans(self):
        # Should generate months 2007-12 through 2008-02:
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts  = time.mktime((2008,  3, 1,  0,  0, 0, 0, 0, -1))
    
        monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
                    "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]"]

        for got, expect in zip(monthlist, expected):
            self.assertEqual(str(got), expect)

        # Add a second to the stop time. This should generate months 2007-12 through 2008-03:"
        start_ts = time.mktime((2007, 12, 3, 10, 15, 0, 0, 0, -1))
        stop_ts  = time.mktime((2008,  3, 1,  0,  0, 1, 0, 0, -1))
    
        monthlist = [span for span in genMonthSpans(start_ts, stop_ts)]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]",
                    "[2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]",
                    "[2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]"]

        for got, expect in zip(monthlist, expected):
            self.assertEqual(str(got), expect)

    def test_genDaySpans(self):

        # Should generate 2007-12-23 through 2008-1-5:"
        start_ts = time.mktime((2007, 12, 23, 10, 15, 0, 0, 0, -1))
        stop_ts  = time.mktime((2008,  1,  5,  9, 22, 0, 0, 0, -1))
        
        daylist = [span for span in genDaySpans(start_ts, stop_ts)]

        expected = ["[2007-12-23 00:00:00 PST (1198396800) -> 2007-12-24 00:00:00 PST (1198483200)]",
                    "[2007-12-24 00:00:00 PST (1198483200) -> 2007-12-25 00:00:00 PST (1198569600)]",
                    "[2007-12-25 00:00:00 PST (1198569600) -> 2007-12-26 00:00:00 PST (1198656000)]",
                    "[2007-12-26 00:00:00 PST (1198656000) -> 2007-12-27 00:00:00 PST (1198742400)]",
                    "[2007-12-27 00:00:00 PST (1198742400) -> 2007-12-28 00:00:00 PST (1198828800)]",
                    "[2007-12-28 00:00:00 PST (1198828800) -> 2007-12-29 00:00:00 PST (1198915200)]",
                    "[2007-12-29 00:00:00 PST (1198915200) -> 2007-12-30 00:00:00 PST (1199001600)]",
                    "[2007-12-30 00:00:00 PST (1199001600) -> 2007-12-31 00:00:00 PST (1199088000)]",
                    "[2007-12-31 00:00:00 PST (1199088000) -> 2008-01-01 00:00:00 PST (1199174400)]",
                    "[2008-01-01 00:00:00 PST (1199174400) -> 2008-01-02 00:00:00 PST (1199260800)]",
                    "[2008-01-02 00:00:00 PST (1199260800) -> 2008-01-03 00:00:00 PST (1199347200)]",
                    "[2008-01-03 00:00:00 PST (1199347200) -> 2008-01-04 00:00:00 PST (1199433600)]",
                    "[2008-01-04 00:00:00 PST (1199433600) -> 2008-01-05 00:00:00 PST (1199520000)]",
                    "[2008-01-05 00:00:00 PST (1199520000) -> 2008-01-06 00:00:00 PST (1199606400)]"]

        for got, expect in zip(daylist, expected):
            self.assertEqual(str(got), expect)

        # Should generate the single date 2007-12-1:"
        daylist = [span for span in genDaySpans(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                                                time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)))]

        expected = ["[2007-12-01 00:00:00 PST (1196496000) -> 2007-12-02 00:00:00 PST (1196582400)]"]
        for got, expect in zip(daylist, expected):
            self.assertEqual(str(got), expect)

    def test_daySpan(self):
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 12, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1))))
        # Try it again with grace=0
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)), grace=0), 
               TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveDaySpan(time.mktime((2007, 12, 13, 0, 0, 1, 0, 0, -1))),
               TimeSpan(time.mktime((2007, 12, 13, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 14, 0, 0, 0, 0, 0, -1))))

    def test_weekSpan(self):
    
        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))),
               TimeSpan(time.mktime((2007, 12, 2, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveWeekSpan(time.mktime((2007, 12, 9, 0, 0, 1, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 9, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 16, 0, 0, 0, 0, 0, -1))))
    
    def test_monthSpan(self):

        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 11, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2007, 12, 1, 0, 0, 1, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveMonthSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 12, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))

    def test_yearSpan(self):        

        self.assertEqual(archiveYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1))), 
               TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))),
               TimeSpan(time.mktime((2007, 1, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveYearSpan(time.mktime((2008, 1, 1, 0, 0, 1, 0, 0, -1))), 
               TimeSpan(time.mktime((2008, 1, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2009, 1, 1, 0, 0, 0, 0, 0, -1))))

    def test_rainYearSpan(self):    

        self.assertEqual(archiveRainYearSpan(time.mktime((2007, 2, 13, 10, 15, 0, 0, 0, -1)), 10), 
               TimeSpan(time.mktime((2006, 10, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(archiveRainYearSpan(time.mktime((2007, 12, 13, 10, 15, 0, 0, 0, -1)), 10), 
               TimeSpan(time.mktime((2007, 10, 1, 0, 0, 0, 0, 0, -1)),
                        time.mktime((2008, 10, 1, 0, 0, 0, 0, 0, -1))))

    def test_DST(self):

        # Test start-of-day routines around a DST boundary:
        start_ts = time.mktime((2007, 3, 11, 1, 0, 0, 0, 0, -1))
        start_of_day = startOfDay(start_ts)
        start2 = startOfArchiveDay(start_of_day)

        # Check that this is, in fact, a DST boundary:
        self.assertEqual(start_of_day, int(time.mktime((2007, 3, 11, 0, 0, 0, 0, 0, -1))))
        self.assertEqual(start2      , int(time.mktime((2007, 3, 10, 0, 0, 0, 0, 0, -1))))

if __name__ == '__main__':
    unittest.main()
    