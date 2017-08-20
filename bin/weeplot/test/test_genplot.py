# $Id$
# Copyright: 2013 Matthew Wall
# License: GPLv3

"""Tests for weeplot.genplot

The output from these tests must be manually inspected.  Many tests emit an
image and/or html file.  The suite emits a single html file with references
to all of the images and html files.  Use these to browse the test output."""

# FIXME: make colors work consistently everywhere
# FIXME: move common code to a shared test library
# FIXME: decide on home for generatePoints
# FIXME: convert this from procedural testing to object testing
# FIXME: 'width' should be 'line_width'

import calendar
import math
import os
import random
import sys
import time
import unittest

import weeutil.Sun
import weeplot.genplot
import weewx.imagegenerator
import weewx.units
from weewx.units import ValueTuple


TMP_DIR = '/var/tmp/weewx_test'
SUITE_NAME = 'test_genplot'
LATITUDE = 42.385
LONGITUDE = -71.106


def mkdir(d):
    try:
        os.makedirs(d)
    except:
        pass

def get_testdir(test_name):
    return '%s/%s/%s' % (TMP_DIR, SUITE_NAME, test_name)

def compass_degree_to_radian(d):
    return degree_to_radian(compass_degree_to_degree(d))

def radian_to_compass_degree(r):
    return degree_to_compass_degree(radian_to_degree(r))

def degree_to_compass_degree(d):
    x = 450.0 - d
    if x >= 360:
        x -= 360
    return x

def compass_degree_to_degree(d):
    return degree_to_compass_degree(d)

def degree_to_radian(d):
    return d * math.pi / 180

def radian_to_degree(r):
    return r * 180 / math.pi




# the TestPlot class encapsulates rather than inherits from TimePlot.
class TestPlot(object):
    def __init__(self, test_name, plot_name, plot_options={}):
        self.test_name = test_name
        self.plot_name = plot_name
        self.plot = weeplot.genplot.TimePlot(plot_options)
        # FIXME: these need to have defaults
        self.plot.setBottomLabel(test_name)
        self.plot.setYScaling((-2, 2, 0.5))

    def addLine(self, plotline):
        self.plot.addLine(plotline)

    def saveImage(self):
        test_dir = '%s/%s/%s' % (TMP_DIR, SUITE_NAME, self.test_name)
        fn = '%s/%s.png' % (test_dir, self.plot_name)
        mkdir(test_dir)
        image = self.plot.render()
        image.save(fn)

    def setXScaling(self, tpl):
        self.plot.setXScaling(tpl)

    def setYScaling(self, tpl):
        self.plot.setYScaling(tpl)

    def setBottomLabel(self, label):
        self.plot.setBottomLabel(label)

    def setLocation(self, lat, lon):
        self.plot.setLocation(lat, lon)

    def setDayNight(self, flag, daycolor, nightcolor, edgecolor):
        self.plot.setDayNight(flag, daycolor, nightcolor, edgecolor)


class Page(object):
    def __init__(self):
        self.lines = []

    def _append_htmlhead(self, title):
        self.lines.append('<html>')
        self.lines.append('<head><title>%s</title></head>' % title)
        self.lines.append('<body>')

    def _append_htmlfoot(self):
        self.lines.append('</body>')
        self.lines.append('</html>')
        self.lines.append('')

    def _write(self, filename):
        f = None
        try:
            f = open(filename, 'w')
            f.write('\n'.join(self.lines))
        finally:
            if f is not None:
                f.close()

class TestPage(Page):
    def __init__(self, test_name):
        Page.__init__(self)
        self.test_name = test_name
        self.plots = []

    def addPlot(self, plot):
        self.plots.append(plot.plot_name)

    def write(self):
        test_dir = '%s/%s/%s' % (TMP_DIR, SUITE_NAME, self.test_name)
        test_file = '%s/%s.html' % (test_dir, self.test_name)

        self._append_htmlhead(self.test_name)
        for plot in self.plots:
            txt = "<img src='%s.png' alt='%s'/><br/>" % (plot, plot)
            self.lines.append(txt)
        self._append_htmlfoot()

        mkdir(test_dir)
        self._write(test_file)
        # add a link to this page in the suite index
        SPAGE.addLink(self.test_name)

class SuitePage(Page):
    def __init__(self):
        Page.__init__(self)
        self.links = []

    def addLink(self, link):
        self.links.append(link)

    def write(self):
        suite_dir = '%s/%s' % (TMP_DIR, SUITE_NAME)
        suite_file = '%s/%s.html' % (suite_dir, SUITE_NAME)

        self._append_htmlhead(SUITE_NAME)
        for test_name in self.links:
            path = '%s/%s/%s.html' % (suite_dir, test_name, test_name)
            txt = "<a href='%s'>%s</a><br/>" % (path, test_name)
            self.lines.append(txt)
        self._append_htmlfoot()

        mkdir(suite_dir)
        self._write(suite_file)


# the index page with links to all unit tests run in this suite
SPAGE = SuitePage()

class PlotTest(unittest.TestCase):

    @staticmethod
    def vecs_to_tuples(time_vec, data_vec,
                       std_unit_system = None,
                       sql_type = 'outTemp',
                       aggregate_type = None):
        (time_type, time_group) = weewx.units.getStandardUnitType(
            std_unit_system, 'dateTime')
        (data_type, data_group) = weewx.units.getStandardUnitType(
            std_unit_system, sql_type, aggregate_type)
        return (ValueTuple(time_vec, time_type, time_group),
                ValueTuple(data_vec, data_type, data_group))

    @staticmethod
    def get_sinusoid_data(start=None, dur=345600, inc=300):
        """create sinusoidal time-series data"""
        if start is None:
            start = int(time.time())
        time_vec = list()
        data_vec = list()
        j=0
#       for i in range(1356998400,1357171200,300): # start 01jan2013 for 172800s
        for i in range(start, start+dur, inc):
            time_vec.append(i)
            data_vec.append(math.sin(j))
            j+=0.1
        return PlotTest.vecs_to_tuples(time_vec, data_vec)

    @staticmethod
    def get_dir_data(lo=0,hi=360):
        """create random directional data"""
        time_vec = list()
        data_vec = list()
        for i in range(1000):
            time_vec.append(i)
            data_vec.append(random.randint(lo,hi))
        return PlotTest.vecs_to_tuples(time_vec, data_vec, sql_type='winddir')

    @staticmethod
    def get_vector_data(lo_mag=0, hi_mag=5, lo_dir=0, hi_dir=360,
                        start=0, dur=172800, inc=900, chance_none=False):
        """create a series of vectors"""
        time_vec = list()
        data_vec = list()
        j=0
        lastm = random.uniform(lo_mag,hi_mag)
        lastd = random.uniform(lo_dir,hi_dir)
        for i in range(start,start+dur,inc):
            time_vec.append(i)
            m = lastm + random.uniform(-5,5)
            if m < lo_mag:
                m = lo_mag
            if m > hi_mag:
                m = hi_mag
            d = lastd + random.uniform(-15,15)
            a = compass_degree_to_radian(d)
            x = m * math.cos(a)
            y = m * math.sin(a)
            c = complex(x,y)
            if chance_none and random.randint(0,1) == 1:
                c = None
            data_vec.append(c)
            lastm = m
            lastd = d
        return PlotTest.vecs_to_tuples(time_vec, data_vec, sql_type='windvec')

    @staticmethod
    def get_function_data(func_type, func_def, start=0, end=172800, inc=600):
        """generate data using the function definition"""
        (start_t, stop_t, data_t) = weewx.imagegenerator.generatePoints(
            func_type, func_def, start, end, inc)
        return (start_t[0], data_t[0])

    @staticmethod
    def vecmax(vec_t):
        return max(abs(c) for c in filter(lambda v : v is not None, vec_t[0]))

    @staticmethod
    def vector_to_deg(vec):
        data = []
        for x in vec:
            data.append(radian_to_compass_degree(math.atan2(x.imag, x.real)))
        return data

    @staticmethod
    def vector_to_mag(vec):
        data = []
        for x in vec:
            data.append(math.sqrt(x.imag*x.imag + x.real*x.real))
        return data

    @staticmethod
    def mkdaynightplot(test_name, plot_name, label=None,
                       time_vec_t=None, data_vec_t=None, **kwargs):
        """draw a single timeseries plot with daynight bands"""
        lat = kwargs.get('latitude', LATITUDE)
        lon = kwargs.get('longitude', LONGITUDE)
        hour = kwargs.get('hour', 0)
        duration = kwargs.get('duration', 24)
        start_ts = hour*3600 + time_vec_t[0][0]
        plot_options = kwargs.get('plot_options', None)
        popt = {'image_width':700,
                'image_height':150,
                'x_label_format':'%H:%M'}
        if plot_options is not None:
            for k in plot_options.keys():
                popt[k] = plot_options[k]
        daycolor = popt.get('daynight_day_color',
                            weeplot.utilities.tobgr('0xffffff'))
        nightcolor = popt.get('daynight_night_color',
                              weeplot.utilities.tobgr('0xd0d0d0'))
        edgecolor = popt.get('daynight_edge_color',
                             weeplot.utilities.tobgr('0x6f6fff'))
        x_tt = time.gmtime(start_ts)
        y, m, d = x_tt[:3]
        (sunrise_utc, sunset_utc) = weeutil.Sun.sunRiseSet(y, m, d, lon, lat)
        if time_vec_t is None or data_vec_t is None:
            (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()

        plot = TestPlot(test_name, plot_name, plot_options=popt)
        plot.setXScaling((start_ts, start_ts+duration*3600, 10800))
        plot.setYScaling((-2, 2, 0.5))
        if label is None:
            label = '%s hour=%d dur=%d lat=%s lon=%s rise=%.2f set=%.2f' % (
                time.strftime('%y.%m.%d %H:%M', time.gmtime(start_ts)),
                hour, duration, lat, lon, sunrise_utc, sunset_utc)
        plot.setBottomLabel(label)
        plot.setLocation(lat, lon)
        plot.setDayNight(True,
                         daycolor,
                         nightcolor,
                         edgecolor)
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0]))
        return plot

    @staticmethod
    def mkpolarplot(test_name, plot_name, label='polarplot',
                    time_vec_t=None, data_vec_t=None,
                    **kwargs):
        if time_vec_t is None or data_vec_t is None:
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        ymax = PlotTest.vecmax(data_vec_t)
        plot_options = {'image_width':300,
                        'image_height':300,
                        'show_x_axis':False,
                        'show_y_axis':False,
                        'annotate_font_size':40}  # FIXME: size is not working
        plot = TestPlot(test_name, plot_name, plot_options=plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((-ymax,ymax,1))
        plot.setBottomLabel(label)
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar', **kwargs))
        return plot

    @staticmethod
    def mkflagplot(test_name, plot_name, label='flagplot',
                   time_vec_t=None, data_vec_t=None,
                   hour=0, duration=12, **kwargs):
        if time_vec_t is None or data_vec_t is None:
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        plot_options = {'image_width':900,
                        'image_height':150,
                        'x_label_format':'%H:%M'}
        plot = TestPlot(test_name, plot_name, plot_options=plot_options)
        plot.setXScaling((hour*3600,hour*3600+duration*3600,10800))
        plot.setYScaling((0,None,1))
        plot.setBottomLabel(label)
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='flags', **kwargs))
        return plot

    @staticmethod
    def mkpolarhistogram(test_name, plot_name, label='polarhistogram',
                         time_vec_t=None, data_vec_t=None,
                         lo=0, hi=360, **kwargs):
        line_options = {}
        color = kwargs.get('color', None)
        if color is not None:
            line_options['color'] = color
        show_counts = kwargs.get('show_counts', None)
        if line_options is not None:
            line_options['show_counts'] = show_counts
        annotate_color = kwargs.get('annotate_color', None)
        if line_options is not None:
            line_options['annotate_color'] = annotate_color
        plot_options = {'image_width':300,
                        'image_height':300,
                        'show_x_axis':False,
                        'show_y_axis':False}
        chart_background_color = kwargs.get('chart_background_color', None)
        if chart_background_color is not None:
            plot_options['chart_background_color'] = chart_background_color
        image_background_color = kwargs.get('image_background_color', None)
        if image_background_color is not None:
            plot_options['image_background_color'] = image_background_color
        if time_vec_t is None or data_vec_t is None:
            (time_vec_t, data_vec_t) = PlotTest.get_dir_data(lo,hi)
        plot = TestPlot(test_name, plot_name, plot_options=plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((0,10,1))
        plot.setBottomLabel(label)
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar_histogram',
                                              **line_options))
        return plot




    def test_Plot(self):
        """barebones test of a Plot"""
        pass

    def test_TimePlot(self):
        """barebones test of a TimePlot with minimal options"""
        test_dir = get_testdir('test_TimePlot')
        fn = '%s/%s.png' % (test_dir, 'test_TimePlot')
        plot_options = dict()
        plot = weeplot.genplot.TimePlot(plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((0,10,1))
        plot.setBottomLabel('foo')
        mkdir(test_dir)
        image = plot.render()
        image.save(fn)

    def test_PlotLine(self):
        """test the PlotLine object"""
        pass

    # ensure that the gradient happens before and after the actual transition,
    # no matter when the transition occurs on the plot.
    # FIXME: this is current broken - if the rise/set is beyond the plot
    #        bounds then the partial gradients are not rendered.
    def test_daynight_boundaries(self):
        """test daynight boundaries"""
        test_name = 'test_daynight_boundaries'
        page = TestPage(test_name)

        x_tt = time.gmtime(0)
        y, m, d = x_tt[:3]
        (sunrise_utc, sunset_utc) = weeutil.Sun.sunRiseSet(y, m, d,
                                                           LONGITUDE,
                                                           LATITUDE)
        sunrise_ts = int(calendar.timegm(x_tt) + sunrise_utc * 3600.0 + 0.5)
        sunset_ts = int(calendar.timegm(x_tt) + sunset_utc * 3600.0 + 0.5)
        hours = []
        x_tt = time.gmtime(sunrise_ts)
        hours.append(x_tt.tm_hour)
        hours.append(x_tt.tm_hour+1)
        x_tt = time.gmtime(sunset_ts)
        hours.append(x_tt.tm_hour)
        hours.append(x_tt.tm_hour+1)
        (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()
        for h in hours:
            plot = PlotTest.mkdaynightplot(test_name, str(h), label=str(h),
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           hour=h, duration=48)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_daynight_latitudes(self):
        """check behavior at equator, temperate, arctic and latitudes"""
        test_name = 'test_daynight_latitudes'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()
        i=0
        for data in [(80,0),(60,0),(0,0),(-60,0),(-80,0),
                     (80,170),(60,170),(0,170),(-60,170),(-80,170),
                     (80,-170),(60,-170),(0,-170),(-60,-170),(-80,-170),
                     ]:
            plot = PlotTest.mkdaynightplot(test_name, str(i),
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           duration=24,
                                           latitude=data[0], longitude=data[1])
            plot.saveImage()
            page.addPlot(plot)
            i += 1
        for data in [(80,0),(60,0),(0,0),(-60,0),(-80,0),
                     (80,170),(60,170),(0,170),(-60,170),(-80,170),
                     (80,-170),(60,-170),(0,-170),(-60,-170),(-80,-170),
                     ]:
            plot = PlotTest.mkdaynightplot(test_name, str(i),
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           duration=24,
                                           latitude=data[0], longitude=data[1])
            plot.saveImage()
            page.addPlot(plot)
            i += 1
        page.write()

    def test_daynight_range(self):
        """draw a bunch of daynight plots to exercise transitions"""
        test_name = 'test_daynight_range'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()
        for hour in range(0,24,1):
            name = 'by_hour_%s' % hour
            plot = PlotTest.mkdaynightplot(test_name, name,
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           hour=hour, duration=48)
            plot.saveImage()
            page.addPlot(plot)
        for lon in range(-190,200,10):
            name = 'by_lon_%s' % lon
            plot = PlotTest.mkdaynightplot(test_name, name,
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           longitude=lon, duration=48)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_daynight_color(self):
        """draw a bunch of daynight plots to exercise daynight colors"""
        test_name = 'test_daynight_color'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()
        for i,c in enumerate([(0x00ff00,0x0000ff),
                              (0x00ff00,0x000000),
                              (0xffffff,0x000000),
                              (0xff00ff,0x00ff00),
                              (0x00ffff,0xdddddd)]):
            label = 'day=0x%06x night=0x%06x' % (c[0],c[1])
            plot = PlotTest.mkdaynightplot(test_name, str(i), label=label,
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           duration=48, 
                                           plot_options={
                    'daynight_day_color':c[0],
                    'daynight_night_color':c[1]
                    })
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_daynight_gradient(self):
        '''check the widths of the day/night gradients'''
        test_name = 'test_daynight_gradient'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_sinusoid_data()
        for g in [1,10,15,18,20,25,50]:
            plot = PlotTest.mkdaynightplot(test_name, str(g),
                                           time_vec_t=time_vec_t,
                                           data_vec_t=data_vec_t,
                                           plot_options={'daynight_gradient':g})
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_histogram(self):
        """test the polar histogram plot type"""
        test_name = 'test_polar_histogram'
        page = TestPage(test_name)
        for i,(lo,hi) in enumerate([(0,40),(40,60),(90,270),(250,280)]):
            label = 'lo=%d hi=%d' % (lo,hi)
            plot = PlotTest.mkpolarhistogram(test_name, str(i), label=label,
                                             lo=lo,hi=hi)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_histogram_colors(self):
        """test the polar histogram plot colors"""
        test_name = 'test_polar_histogram_colors'
        page = TestPage(test_name)
        for i,data in enumerate([(0,120,0xffff00,0xffffff,0xdddddd),
                                 (0,120,0x00aaff,0x888800,0xdddd00),
                                 (0,120,0x00ff00,0xccff11,0x558800),
                                 (0,40,0xffffff,0x000000,0x000000),
                                 (0,180,0xffffff,0x000000,0x000000),
                                 (0,360,0xffffff,0x000000,0x000000),
                                 (40,60,0x0000ff,0x000000,0x000000),
                                 (0,180,0x0000ff,0x000000,0x000000),
                                 (0,360,0x0000ff,0x000000,0x000000),
                                 (90,270,0x00ff00,0x555555,0xdddddd),
                                 (250,280,0x00ffff,0xdddddd,0x222222)]):
            label = 'color=0x%06x image_bg=0x%06x chart_bg=0x%06x' % (
                data[2],data[3],data[4])
            plot = PlotTest.mkpolarhistogram(test_name, str(i), label=label,
                                             lo=data[0],hi=data[1],
                                             color=data[2],
                                             image_background_color=data[3],
                                             chart_background_color=data[4])
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_histogram_counts(self):
        """test counts on the polar histogram"""
        test_name = 'test_polar_histogram_counts'
        page = TestPage(test_name)
        for i,r in enumerate([(0,360),(30,120),(90,270)]):
            label = 'lo=%d hi=%d' % (r[0],r[1])
            plot = PlotTest.mkpolarhistogram(test_name, str(i), label=label,
                                             lo=r[0], hi=r[1],
                                             show_counts=True,
                                             annotate_color='green')
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar(self):
        """test the polar plot type"""
        test_name = 'test_polar'
        page = TestPage(test_name)
        for x in range(6):
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data(0,1,0,60*x)
            text = 'x=%d' % x
            plot = PlotTest.mkpolarplot(test_name, str(x),
                                        time_vec_t=time_vec_t,
                                        data_vec_t=data_vec_t,
                                        annotate_text=text,
                                        annotate_text_x=40,
                                        annotate_text_y=10)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_none(self):
        """test polar with None in data"""
        test_name = 'test_polar_none'
        page = TestPage(test_name)
        for x in range(6):
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data(0,1,0,60*x,
                                                                chance_none=True)
            text = 'x=%d' % x
            plot = PlotTest.mkpolarplot(test_name, str(x),
                                        time_vec_t=time_vec_t,
                                        data_vec_t=data_vec_t,
                                        annotate_text=text,
                                        annotate_text_x=40,
                                        annotate_text_y=10)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_grid(self):
        '''test grid on polar plots'''
        test_name = 'test_polar_grid'
        page = TestPage(test_name)

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data(lo_mag=10,hi_mag=50)
        ymax = PlotTest.vecmax(data_vec_t)

        plot_options = {'image_width':400,
                        'image_height':400}

        plot = TestPlot(test_name, '1', plot_options=plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((-50,50,10))
        plot.setBottomLabel('grid test')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar',
                                              polar_origin=(10,10),
                                              polar_grid=True,
                                              highlight_latest=True,
                                              latest_color='orange'))
        plot.saveImage()
        page.addPlot(plot)

        plot = TestPlot(test_name, '2', plot_options=plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((-100,100,10))
        plot.setBottomLabel('grid test')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar',
                                              polar_origin=(10,10),
                                              polar_grid=True,
                                              highlight_latest=True,
                                              latest_color='orange'))
        plot.saveImage()
        page.addPlot(plot)
        page.write()

    def test_polar_options(self):
        test_name = 'test_polar_options'
        page = TestPage(test_name)

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        ymax = PlotTest.vecmax(data_vec_t)
        plot_options = {'image_width':400,
                        'image_height':400,
                        'show_x_axis':False,
                        'show_y_axis':False}

        i = 0
        for label,kwargs in [('line width 3',
                              {'width':3}),
                             ('circle markers with vectors',
                              {'line_type':'solid',
                               'marker_size':4,
                               'marker_type':'circle'}),
                             ('box markers',
                              {'line_type':None,
                               'marker_size':4,
                               'marker_type':'box'}),
                             ('box markers with grid',
                              {'polar_grid':True,
                               'line_type':None,
                               'marker_size':4,
                               'marker_type':'box'}),
                             ('grid',
                              {'polar_grid':True}),
                             ('circle markers with grid',
                              {'line_type':'solid',
                               'marker_size':4,
                               'marker_type':'circle',
                               'polar_grid':True})]:
            plot = TestPlot(test_name, str(i), plot_options=plot_options)
            plot.setYScaling((-ymax,ymax,1))
            plot.setBottomLabel(label)
            plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                                  plot_type='polar',
                                                  **kwargs))
            plot.saveImage()
            page.addPlot(plot)
            i += 1

        for label,kwargs in [('multiple origins', {}),
                             ('multiple origins with grid',
                              {'polar_grid':True})]:
            plot = TestPlot(test_name, str(i), plot_options=plot_options)
            plot = PlotTest.mkpolarplot(test_name, str(i), label=label,
                                        time_vec_t=time_vec_t,
                                        data_vec_t=data_vec_t,
                                        **kwargs)
            plot.setYScaling((-2*ymax,2*ymax,1))
            plot.setBottomLabel(label)
            plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                                  plot_type='polar',
                                                  polar_origin=(50,150),
                                                  **kwargs))
            plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                                  plot_type='polar',
                                                  polar_origin=(150,150)))
            plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                                  plot_type='polar',
                                                  polar_origin=(150,50),
                                                  **kwargs))
            plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                                  plot_type='polar',
                                                  polar_origin=(50,50)))
            plot.saveImage()
            page.addPlot(plot)
            i += 1

        page.write()

    # FIXME: highlights not working properly for thinner lines
    def test_polar_highlight(self):
        """test polar highlight"""
        test_name = 'test_polar_highlight'
        page = TestPage(test_name)

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        for i,kwargs in enumerate([{'label':'default'},
                                   {'label':'annotate latest',
                                    'annotate_latest':True},
                                   {'label':'highlight latest',
                                    'highlight_latest':True},
                                   {'label':'highlight latest wide vectors',
                                    'width':3,
                                    'highlight_latest':True},
                                   {'label':'highlight latest yellow',
                                    'width':3,
                                    'highlight_latest':True,
                                    'latest_color':'yellow'},
                                   {'label':'highlight latest yellow wide',
                                    'highlight_latest':True,
                                    'latest_color':'yellow',
                                    'latest_width':4},
                                   {'label':'highlight latest color red',
                                    'highlight_latest':True,
                                    'latest_color':'red'},
                                   {'label':'highlight latest width 10',
                                    'highlight_latest':True,
                                    'latest_color':'purple',
                                    'latest_width':10},
                                   {'label':'highlight latest width 3',
                                    'highlight_latest':True,
                                    'latest_color':'purple',
                                    'latest_width':3,
                                    'annotate_latest':True,
                                    'annotate_color':'green'}]):
            plot = PlotTest.mkpolarplot(test_name, str(i),
                                        time_vec_t=time_vec_t,
                                        data_vec_t=data_vec_t,
                                        **kwargs)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_polar_multi(self):
        """test polar on polar histogram"""
        test_name = 'test_polar_multi'

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        data_angle = PlotTest.vector_to_deg(data_vec_t[0])
        ymax = PlotTest.vecmax(data_vec_t)
        plot_options = {'image_width':300,
                        'image_height':300,
                        'show_x_axis':False,
                        'show_y_axis':False}
        plot = TestPlot(test_name, test_name, plot_options=plot_options)
        plot.setXScaling((0,10,1))
        plot.setYScaling((-ymax,ymax,1))
        plot.setBottomLabel('polar multi')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar',
                                              annotate_latest=False))
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_angle,
                                              plot_type='polar_histogram',
                                              show_counts=True,
                                              annotate_color='red'))
        plot.saveImage()
        page = TestPage(test_name)
        page.addPlot(plot)
        page.write()

    def test_polar_overlay(self):
        """test polar overlaid on time plot"""
        test_name = 'test_polar_overlay'
        page = TestPage(test_name)

        hour=0
        duration=24
        plot_options = {'image_width':700,
                        'image_height':200,
                        'x_label_format':'%H:%M'}

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        data_angle = PlotTest.vector_to_deg(data_vec_t[0])
        plot = TestPlot(test_name, '1', plot_options=plot_options)
        plot.setXScaling((hour*3600,hour*3600+duration*3600,10800))
        plot.setYScaling((0,360,60))
        plot.setBottomLabel('polar overlay')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar'))
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_angle,
                                              plot_type='line',
                                              line_type=None,
                                              marker_size=2,
                                              marker_type='box'))
        plot.saveImage()
        page.addPlot(plot)

        (time_vec_t, data_vec_t) = PlotTest.get_vector_data(lo_dir=0,hi_dir=10)
        data_angle = PlotTest.vector_to_deg(data_vec_t[0])
        plot = TestPlot(test_name, '2', plot_options=plot_options)
        plot.setXScaling((hour*3600,hour*3600+duration*3600,10800))
        plot.setYScaling((0,20,10))
        plot.setBottomLabel('polar overlay')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='polar',
                                              polar_origin=(350,100)))
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_angle,
                                              plot_type='line',
                                              line_type=None,
                                              marker_size=2,
                                              marker_type='box'))
        plot.saveImage()
        page.addPlot(plot)
        page.write()

    def test_flags(self):
        """test the flags plot type"""
        test_name = 'test_flags'
        page = TestPage(test_name)
        for x in range(10):
            minmag = 2*x
            maxmag = 4*x
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data(
                lo_mag=minmag,hi_mag=maxmag,inc=6000)
            label = 'lo=%d hi=%d' % (minmag, maxmag)
            plot = PlotTest.mkflagplot(test_name, str(x),
                                       label=label, duration=48,
                                       time_vec_t=time_vec_t,
                                       data_vec_t=data_vec_t)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_flags_none(self):
        """test the flags plot type with None values"""
        test_name = 'test_flags_none'
        page = TestPage(test_name)
        for x in range(10):
            minmag = 2*x
            maxmag = 4*x
            (time_vec_t, data_vec_t) = PlotTest.get_vector_data(
                lo_mag=minmag,hi_mag=maxmag,inc=6000,chance_none=True)
            label = 'lo=%d hi=%d' % (minmag, maxmag)
            plot = PlotTest.mkflagplot(test_name, str(x),
                                       label=label, duration=48,
                                       time_vec_t=time_vec_t,
                                       data_vec_t=data_vec_t)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_flags_baseline(self):
        """test the flag baseline options"""
        test_name = 'test_flags_baseline'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        for i,kwargs in enumerate([{'label':'default'},
                                   {'label':'flag_baseline=bottom',
                                    'flag_baseline':'bottom'},
                                   {'label':'flag_baseline=middle',
                                    'flag_baseline':'middle'},
                                   {'label':'flag_baseline=top',
                                    'flag_baseline':'top'},
                                   {'label':'flag_baseline=max',
                                    'flag_baseline':'max'},
                                   {'label':'flag_baseline=40%',
                                    'flag_baseline':'40%'},
                                   {'label':'flag_baseline="10"',
                                    'flag_baseline':'10'},
                                   {'label':'flag_baseline=40',
                                    'flag_baseline':40},
                                   {'label':'flag_baseline=-10',
                                    'flag_baseline':40},
                                   {'label':'flag_baseline=140',
                                    'flag_baseline':140}]):
            plot = PlotTest.mkflagplot(test_name, str(i),
                                       time_vec_t=time_vec_t,
                                       data_vec_t=data_vec_t,
                                       **kwargs)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_flags_options(self):
        """test the flags options"""
        test_name = 'test_flags_options'
        page = TestPage(test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        for i,kwargs in enumerate([{'label':'stem length 30',
                                    'flag_baseline':'max',
                                    'flag_stem_length':30},
                                   {'label':'no flags',
                                    'flag_baseline':'max',
                                    'draw_flags':False},
                                   {'label':'stem length 40, flag length 20',
                                    'flag_baseline':'max',
                                    'flag_stem_length':40,
                                    'flag_length':20},
                                   {'label':'stem length 10, flag length 3',
                                    'flag_baseline':'max',
                                    'flag_stem_length':10,
                                    'flag_length':3},
                                   {'label':'dot radius 6',
                                    'flag_baseline':'max',
                                    'flag_dot_radius':6},
                                   ]):
            plot = PlotTest.mkflagplot(test_name, str(i),
                                       time_vec_t=time_vec_t,
                                       data_vec_t=data_vec_t,
                                       **kwargs)
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_flags_overlay(self):
        """test the flags overlay with other lines"""
        test_name = 'test_flags_overlay'
        page = TestPage(test_name)
        plot_options = {'image_width':700,
                        'image_height':200,
                        'x_label_format':'%H:%M'}
        hour=0
        duration=24
        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        data_dir = PlotTest.vector_to_deg(data_vec_t[0])
        data_mag = PlotTest.vector_to_mag(data_vec_t[0])

        # create the direction plot
        plot = TestPlot(test_name, 'direction', plot_options=plot_options)
        plot.setXScaling((hour*3600,hour*3600+duration*3600,10800))
        plot.setYScaling((0,360,60))
        plot.setBottomLabel('flag overlay direction')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='flags',
                                              flag_baseline=100))
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_dir,
                                              plot_type='line',
                                              line_type=None,
                                              marker_size=2,
                                              marker_type='box'))
        plot.saveImage()
        page.addPlot(plot)

        # create the magnitude plot
        plot = TestPlot(test_name, 'magnitude', plot_options=plot_options)
        plot.setXScaling((hour*3600,hour*3600+duration*3600,10800))
        plot.setYScaling((0,None,None))
        plot.setBottomLabel('flag overlay magnitude')
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='flags'))
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_mag,
                                              plot_type='line'))
        plot.saveImage()
        page.addPlot(plot)

        page.write()

    def test_annotations(self):
        """test the plot annotations"""
        test_name = 'test_annotations'
        page = TestPage(test_name)
        start = 0
        span = 345600
        inc = 19200
        plot_options = {'image_width':700,
                        'image_height':200,
                        'x_label_format':'%H:%M'}
        (time_t, data_t) = PlotTest.get_sinusoid_data(start,span)
        for i,kwargs in enumerate([{'label':'lo',
                                    'annotate_low':True},
                                   {'label':'hi',
                                    'annotate_high':True},
                                   {'label':'hi/lo',
                                    'annotate_high':True,
                                    'annotate_low':True},
                                   {'label':'hi/lo color',
                                    'annotate_low':True,
                                    'annotate_low_color':'#8888ff',
                                    'annotate_high':True,
                                    'annotate_high_color':'#ff8888'},
                                   {'label':'hi/lo size',
                                    'annotate_low':True,
                                    'annotate_low_font_size':30,
                                    'annotate_high':True,
                                    'annotate_high_font_size':50},
                                   {'label':'latest',
                                    'annotate_latest':True},
                                   {'label':'text',
                                    'annotate_text':'hello world'},
                                   {'label':'positioned text',
                                    'annotate_text':'hello world',
                                    'annotate_text_x':250,
                                    'annotate_text_y':15},
                                   {'label':'positioned colored text',
                                    'annotate_text':'hello world',
                                    'annotate_color':'yellow',
                                    'annotate_text_x':50,
                                    'annotate_text_y':15},
                                   {'label':'text size',
                                    'annotate_text':'hello world',
                                    'annotate_color':'purple',
                                    'annotate_text_x':50,
                                    'annotate_text_y':15,
                                    'annotate_font_size':30}]):
            plot = TestPlot(test_name, str(i), plot_options=plot_options)
            plot.setXScaling((start,start+span,inc))
            plot.setYScaling((-2,2,0.5))
            plot.setBottomLabel(kwargs.get('label','noname'))
            plot.addLine(weeplot.genplot.PlotLine(time_t[0], data_t[0],
                                                  plot_type='line',
                                                  **kwargs))
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_functions(self):
        """test plot functions"""
        test_name = 'test_functions'
        page = TestPage(test_name)
        plot_options = {'image_width':700,
                        'image_height':200,
                        'x_label_format':'%H:%M'}
        for i,f in enumerate(['32','90','-10','0.001 * x','80*math.sin(0.01*x*3.14159/180)']):
            plot = TestPlot(test_name, str(i), plot_options=plot_options)
            plot.setXScaling((0,24*3600,10800))
            plot.setYScaling((-20,100,10))
            plot.setBottomLabel('y = %s' % f)
            (time_t, data_t) = PlotTest.get_function_data('outTemp', f)
            plot.addLine(weeplot.genplot.PlotLine(
                time_t, data_t, plot_type='line'))
            plot.saveImage()
            page.addPlot(plot)
        page.write()

    def test_functions_multi(self):
        """verify multiple functions in a single plot"""
        test_name = 'test_functions_multi'

        plot = TestPlot(test_name, test_name, plot_options={
                'image_width':700,
                'image_height':200,
                'x_label_format':'%H:%M'
                })

        plot.setXScaling((0,24*3600,10800))
        plot.setYScaling((-20,100,10))
        plot.setBottomLabel('multi')

        (time_t, data_t) = PlotTest.get_function_data('outTemp', '32')
        plot.addLine(weeplot.genplot.PlotLine(
            time_t, data_t, plot_type='line'))
        (time_t, data_t) = PlotTest.get_function_data('outTemp', '55')
        plot.addLine(weeplot.genplot.PlotLine(
            time_t, data_t, plot_type='line'))
        (time_t, data_t) = PlotTest.get_function_data('outTemp', '80')
        plot.addLine(weeplot.genplot.PlotLine(
            time_t, data_t, plot_type='line',
            line_type=None,
            marker_size=2,
            marker_type='box'))
        (time_t, data_t) = PlotTest.get_function_data(
            'outTemp', '0.0005 * x')
        plot.addLine(weeplot.genplot.PlotLine(
            time_t, data_t, plot_type='line',
            line_type=None,
            marker_size=2,
            marker_type='box'))
        plot.saveImage()
        page = TestPage(test_name)
        page.addPlot(plot)
        page.write()

    # these test the baseline graph behavior for weewx 2.5.
    # we must maintain backward compatibility with these.

    def test_line_graph(self):
        '''verify line graph behavior'''
        test_name = 'test_line_graph'
        plot = TestPlot(test_name, test_name)
        (time_t, data_t) = PlotTest.get_sinusoid_data()
        plot.addLine(weeplot.genplot.PlotLine(time_t[0], data_t[0],
                                              plot_type='line'))
        plot.saveImage()
        page = TestPage(test_name)
        page.addPlot(plot)
        page.write()

    def xtest_bar_graph(self):
        '''verify bar graph behavior'''
        test_name = 'test_bar_graph'
        plot = TestPlot(test_name, test_name)
        (time_t, data_t) = PlotTest.get_sinusoid_data()
        plot.addLine(weeplot.genplot.PlotLine(time_t[0], data_t[0],
                                              plot_type='bar'))
        plot.saveImage()
        page = TestPage(test_name)
        page.addPlot(plot)
        page.write()

    def test_vector_graph(self):
        '''verify vector graph behavior'''
        test_name = 'test_vector_graph'
        plot = TestPlot(test_name, test_name)
        (time_vec_t, data_vec_t) = PlotTest.get_vector_data()
        plot.addLine(weeplot.genplot.PlotLine(time_vec_t[0], data_vec_t[0],
                                              plot_type='vector'))
        plot.saveImage()
        page = TestPage(test_name)
        page.addPlot(plot)
        page.write()


    def test_zzzzzzzzzz(self):
        # spit out the index page with links to all tests that were run
        SPAGE.write()
        

# use this to run individual tests while debugging
def suite(testname):
    tests = [testname]
    return unittest.TestSuite(map(PlotTest, tests))
            
# use '--test test_name' to specify a single test
if __name__ == '__main__':
    testname = None
    if len(sys.argv) == 3 and sys.argv[1] == '--test':
        testname = sys.argv[2]
    if testname is not None:
        unittest.TextTestRunner(verbosity=2).run(suite(testname))
        SPAGE.write()
    else:
        unittest.main()
