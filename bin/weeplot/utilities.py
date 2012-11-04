#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Various utilities used by the plot package.

"""
import ImageFont
import datetime
import time
import math

import weeplot
    
def scale(fmn, fmx, prescale = (None, None, None), nsteps = 10):
    """Calculates an appropriate min, max, and step size for scaling axes on a plot.
    
    The origin (zero) is guaranteed to be on an interval boundary.
    
    fmn: The minimum data value
    
    fmx: The maximum data value. Must be greater than or equal to fmn.

    prescale: A 3-way tuple. A non-None min or max value (positions 0 and 1, 
    respectively) will be fixed to that value. A non-None interval (position 2)
    be at least as big as that value. Default = (None, None, None) 
    
    nsteps: The nominal number of desired steps. Default = 10
    
    Returns: a three-way tuple. First value is the lowest scale value, second the highest.
    The third value is the step (increment) between them.

    Examples:
    >>> print scale(1.1, 12.3)
    (0.0, 14.0, 2.0)
    >>> print scale(-1.1, 12.3)
    (-2.0, 14.0, 2.0)
    >>> print scale(-12.1, -5.3)
    (-13.0, -5.0, 1.0)
    >>> print scale(10.0, 10.0)
    (10.0, 10.1, 0.01)
    >>> print "(%.4f, %.4f, %.5f)" % scale(10.0, 10.001)
    (10.0000, 10.0010, 0.00010)
    >>> print scale(10.0, 10.0+1e-8)
    (10.0, 10.1, 0.01)
    >>> print scale(0.0, 0.05, (None, None, .1), 10)
    (0.0, 1.0, 0.1)
    >>> print scale(0.0, 0.21, (None, None, .02))
    (0.0, 0.22, 0.02)
    
    """
    
    if all(x is not None for x in prescale):
        return prescale

    (minscale, maxscale, min_interval) = prescale
    
    # Make sure fmn and fmx are float values, in case a user passed
    # in integers:
    fmn = float(fmn)
    fmx = float(fmx)

    if fmx < fmn :
        raise weeplot.ViolatedPrecondition, "scale() called with max value less than min value"

    if _rel_approx_equal(fmn, fmx) :
        if fmn == 0.0 :
            fmx = 1.0
        else :
            fmx = fmn + .01*abs(fmn)

    frange = fmx - fmn
    steps = frange / nsteps
    
    mag = math.floor(math.log10(steps))
    magPow = math.pow(10.0, mag)
    magMsd = math.floor(steps/magPow + 0.5)
    
    if magMsd > 5.0:
        magMsd = 10.0
    elif magMsd > 2.0:
        magMsd = 5.0
    else : # magMsd > 1.0
        magMsd = 2

    # This will be the nominal interval size
    interval = magMsd * magPow
    
    # Test it against the desired minimum, if any
    if min_interval is None or interval >= min_interval:
        # Either no min interval was specified, or its safely
        # less than the chosen interval. 
        if minscale is None:
            minscale = interval * math.floor(fmn / interval)
    
        if maxscale is None:
            maxscale = interval * math.ceil(fmx / interval)

    else:
    
        # The request for a minimum interval has kicked in.
        # Sometimes this can make for a plot with just one or
        # two intervals in it. Adjust the min and max values
        # to get a nice plot
        interval = min_interval

        if minscale is None:
            if maxscale is None:
                # Both can float. Pick values so the range is near the bottom
                # of the scale:
                minscale = interval * math.floor(fmn / interval)
                maxscale = minscale + interval * nsteps
            else:
                # Only minscale can float
                minscale = maxscale - interval * nsteps
        else:
            if maxscale is None:
                # Only maxscale can float
                maxscale = minscale + interval * nsteps
            else:
                # Both are fixed --- nothing to be done
                pass

    return (minscale, maxscale, interval)


def scaletime(tmin_ts, tmax_ts) :
    """Picks a time scaling suitable for a time plot.
    
    tmin_ts, tmax_ts: The time stamps in epoch time around which the times will be picked.
    
    Returns a scaling 3-tuple. First element is the start time, second the stop
    time, third the increment. All are in seconds (epoch time in the case of the 
    first two).    """
    if tmax_ts <= tmin_ts :
        raise weeplot.ViolatedPrecondition, "scaletime called with tmax <= tmin"
    
    tdelta = tmax_ts - tmin_ts
    
    tmin_dt = datetime.datetime.fromtimestamp(tmin_ts)
    tmax_dt = datetime.datetime.fromtimestamp(tmax_ts)
    
    
    # How big a time delta are we talking about? 
    if tdelta <= 27 * 3600 :
        # A day plot is wanted. A time increment of 3 hours is appropriate
        
        # h is the hour of tmin_dt
        h = tmin_dt.timetuple()[3]
        # Subtract off enough to get to the lower 3-hour boundary, 
        # zeroing out everything else
        start_dt = tmin_dt.replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours = h % 3)

        # Now figure the upper time boundary, which is a bit more complicated if tmax_dt lies
        # near the 3-hour boundary
        tmax_tt = tmax_dt.timetuple()
        # stop_dt is the lower 3-hour boundary from tmax_dt
        stop_dt = tmax_dt.replace(minute=0, second=0, microsecond=0)
        # If the tmax_dt was close to the 3-hour boundary, we're done. Otherwise, go up to
        # the next 3-hour boundary.
        if tmax_tt[3] % 3 != 0 or tmax_tt[4] != 0 :
            stop_dt += datetime.timedelta(hours = 3 - tmax_tt[3] % 3)
            
        interval = 3 * 3600
    
    elif tdelta > 27 * 3600 and tdelta <= 31 * 24 * 3600 :
        # The time scale is between a day and a month. A time increment of one day is appropriate
        start_dt = tmin_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        stop_dt  = tmax_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        tmax_tt = tmax_dt.timetuple()
        if tmax_tt[3]!=0 or tmax_tt[4]!=0 :
            stop_dt += datetime.timedelta(days=1)
            
        interval = 24 * 3600
    else :
        # The time scale is more than a month. A time increment of a month is appropriate
        start_dt = tmin_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        (year , mon, day) = tmax_dt.timetuple()[0:3]
        if day != 1 :
            mon += 1
            if mon==13 :
                mon = 1
                year += 1
        stop_dt = datetime.datetime(year, mon, 1)
        # Average month length:
        interval = 365.25/12 * 24 * 3600
    # Convert to epoch time stamps
    start_ts = int(time.mktime(start_dt.timetuple()))
    stop_ts  = int(time.mktime(stop_dt.timetuple()))

    return (start_ts, stop_ts, interval)
    

class ScaledDraw(object):
    """Like an ImageDraw object, but lines are scaled.
    
    """
    def __init__(self, draw, imagebox, scaledbox):
        """Initialize a ScaledDraw object.
        
        Example:
        scaledraw = ScaledDraw(draw, ((10, 10), (118, 246)), ((0.0, 0.0), (10.0, 1.0)))
        
        would create a scaled drawing where the upper-left image coordinate (10, 10) would
        correspond to the scaled coordinate( 0.0, 1.0). The lower-left image coordinate
        would correspond to the scaled coordinate (10.0, 0.0).
        
        draw: an instance of ImageDraw
        
        imagebox: a 2-tuple of the box coordinates on the image ((ulx, uly), (lrx, lry))
        
        scaledbox: a 2-tuple of the box coordinates of the scaled plot ((llx, lly), (urx, ury))
        
        """
        uli = imagebox[0]
        lri = imagebox[1]
        lls = scaledbox[0]
        urs = scaledbox[1]
        if urs[1] == lls[1]:
            pass
        self.xscale =  float(lri[0] - uli[0]) / float(urs[0] - lls[0])
        self.yscale = -float(lri[1] - uli[1]) / float(urs[1] - lls[1]) 
        self.xoffset = int(lri[0] - urs[0] * self.xscale + 0.5)
        self.yoffset = int(uli[1] - urs[1] * self.yscale + 0.5)

        self.draw    = draw
        
    def line(self, x, y, line_type='solid', marker_type=None, marker_size=8, **options) :
        """Draw a scaled line on the instance's ImageDraw object.
        
        x: sequence of x coordinates
        
        y: sequence of y coordinates, some of which are possibly null (value of None)
        
        line_type: 'solid' for line that connect the coordinates
              None for no line
        
        marker_type: None or 'none' for no marker.
                     'cross' for a cross
                     'circle' for a circle
                     'box' for a box
                     'x' for an X

        For a scatter plot, set line_type to None and marker_type to something other than None.
        """
        # Break the line up around any nulls
        for xy_seq in xy_seq_line(x, y):
        # Create a list with the scaled coordinates...
            xy_seq_scaled = [(self.xtranslate(xc), self.ytranslate(yc)) for (xc,yc) in xy_seq]
            if line_type == 'solid':
                # Now pick the appropriate drawing function, depending on the length of the line:
                if len(xy_seq) == 1 :
                    self.draw.point(xy_seq_scaled, fill=options['fill'])
                else :
                    self.draw.line(xy_seq_scaled, **options)
            if marker_type and marker_type.lower().strip() not in ['none', '']:
                self.marker(xy_seq_scaled, marker_type, marker_size=marker_size, **options)
        
    def marker(self, xy_seq, marker_type, marker_size=10, **options):
        half_size = marker_size/2
        marker=marker_type.lower()
        for x, y in xy_seq:
            if marker == 'cross':
                self.draw.line([(x-half_size, y), (x+half_size, y)], **options)
                self.draw.line([(x, y-half_size), (x, y+half_size)], **options)
            elif marker == 'x':
                self.draw.line([(x-half_size, y-half_size), (x+half_size, y+half_size)], **options)
                self.draw.line([(x-half_size, y+half_size), (x+half_size, y-half_size)], **options)
            elif marker == 'circle':
                self.draw.ellipse([(x-half_size, y-half_size), 
                                   (x+half_size, y+half_size)], outline=options['fill'])
            elif marker == 'box':
                self.draw.line([(x-half_size, y-half_size), 
                                (x+half_size, y-half_size),
                                (x+half_size, y+half_size),
                                (x-half_size, y+half_size),
                                (x-half_size, y-half_size)], **options)
                 
        
    def rectangle(self, box, **options) :
        """Draw a scaled rectangle.
        
        box: A pair of 2-way tuples, containing coordinates of opposing corners
        of the box.
        
        options: passed on to draw.rectangle. Usually contains 'fill' (the color)
        """
        box_scaled = [(coord[0]*self.xscale + self.xoffset + 0.5, coord[1]*self.yscale + self.yoffset + 0.5) for coord in box]
        self.draw.rectangle(box_scaled, **options)
        
    def vector(self, x, vec, vector_rotate, **options):
        
        if vec is None: 
            return
        xstart_scaled = self.xtranslate(x)
        ystart_scaled = self.ytranslate(0)
        
        vecinc_scaled = vec * self.yscale
        
        if vector_rotate:
            vecinc_scaled *= complex(math.cos(math.radians(vector_rotate)),
                                     math.sin(math.radians(vector_rotate)))
        
        # Subtract off the x increment because the x-axis
        # *increases* to the right, unlike y, which increases
        # downwards
        xend_scaled = xstart_scaled - vecinc_scaled.real
        yend_scaled = ystart_scaled + vecinc_scaled.imag
        
        self.draw.line(((xstart_scaled, ystart_scaled), (xend_scaled, yend_scaled)), **options)
        
    def xtranslate(self, x):
        return int(x * self.xscale + self.xoffset + 0.5)
                   
    def ytranslate(self, y):
        return int(y * self.yscale + self.yoffset + 0.5)
    
                   
def xy_seq_line(x, y):
    """Generator function that breaks a line up into individual segments around any nulls held in y.
    
    x: iterable sequence of x coordinates. All values must be non-null
    
    y: iterable sequence of y coordinates, possibly with some embedded 
    nulls (that is, their value==None)
    
    yields: Lists of (x,y) coordinates
    
    Example 1
    >>> x=[ 1,  2,  3]
    >>> y=[10, 20, 30]
    >>> for xy_seq in xy_seq_line(x,y):
    ...     print xy_seq
    [(1, 10), (2, 20), (3, 30)]
    
    Example 2
    >>> x=[None, 0,  1,    2,  3,    4,    5,  6,  7,   8,    9]
    >>> y=[None, 0, 10, None, 30, None, None, 60, 70,  80, None]
    >>> for xy_seq in xy_seq_line(x,y):
    ...     print xy_seq
    [(0, 0), (1, 10)]
    [(3, 30)]
    [(6, 60), (7, 70), (8, 80)]
    
    Example 3
    >>> x=[  0 ]
    >>> y=[None]
    >>> for xy_seq in xy_seq_line(x,y):
    ...     print xy_seq
    
    Example 4
    >>> x=[   0,    1,    2]
    >>> y=[None, None, None]
    >>> for xy_seq in xy_seq_line(x,y):
    ...     print xy_seq
    
    """
    
    line = []
    for xy in zip(x, y):
        # If the y coordinate is None, that marks a break
        if xy[1] is None:
            # If the length of the line is non-zero, yield it
            if len(line):
                yield line
                line = []
        else:
            line.append(xy)
    if len(line):
        yield line

def pickLabelFormat(increment):
    """Pick an appropriate label format for the given increment.
    
    Examples:
    >>> print pickLabelFormat(1)
    %.0f
    >>> print pickLabelFormat(20)
    %.0f
    >>> print pickLabelFormat(.2)
    %.1f
    >>> print pickLabelFormat(.01)
    %.2f
    """

    i_log = math.log10(increment)
    if i_log < 0 :
        i_log = abs(i_log)
        decimal_places = int(i_log)
        if i_log != decimal_places :
            decimal_places += 1
    else :
        decimal_places = 0
        
    return "%%.%df" % decimal_places

def get_font_handle(fontpath, *args):
    
    font = None
    if fontpath is not None :
        try :
            if fontpath.endswith('.ttf'):
                font = ImageFont.truetype(fontpath, *args)
            else :
                font = ImageFont.load_path(fontpath)
        except IOError :
            pass
    
    if font is None :
        font = ImageFont.load_default()
        
    return font 

def _rel_approx_equal(x, y, rel=1e-7):
    """Relative test for equality.
    
    Example 
    >>> _rel_approx_equal(1.23456, 1.23457)
    False
    >>> _rel_approx_equal(1.2345678, 1.2345679)
    True
    >>> _rel_approx_equal(0.0, 0.0)
    True
    >>> _rel_approx_equal(0.0, 0.1)
    False
    >>> _rel_approx_equal(0.0, 1e-9)
    False
    >>> _rel_approx_equal(1.0, 1.0+1e-9)
    True
    >>> _rel_approx_equal(1e8, 1e8+1e-3)
    True
    """
    return abs(x-y) <= rel*max(abs(x), abs(y))
    
if __name__ == "__main__":
    import doctest

    if not doctest.testmod().failed:
        print "PASSED"
    