#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Various utilities used by the plot package.

"""
import datetime
import time
import math
import weeplot
    
def scale(fmn, fmx, prescale = None):
    """Calculates an appropriate min, max, and step size for scaling axes on a plot.
    
    Reference: 2003 Pharmasug 2003 by Don Li "Tired of Defining Axis Scale for
    SAAS Graphs? A Solution with Automatic Optimizing Approach."
    http://www.lexjansen.com/pharmasug/2003/coderscorner/cc024.pdf
    
    fmn: The minimum data value
    
    fmx: The maximum data value. Must be greater than or equal to fmn.
    
    prescale: One or more of the results may be preset. [optional]
    
    Returns: a three-way tuple. First value is the lowest scale value, second the highest.
    The third value is the step (increment) between them.
    """
    minscale = maxscale = interval = None
    if prescale is not None :
        minscale = prescale[0]
        maxscale = prescale[1]
        interval= prescale[2]
        
    if fmx < fmn :
        raise weeplot.ViolatedPrecondition, "scale() called with max value less than min value"

    if minscale is not None :
        fmn = minscale
    if maxscale is not None :
        fmx = maxscale
        
    if fmx == fmn :
        if fmn == 0.0 :
            fmx = 1.0
        else :
            fmx = fmn + .01*abs(fmn)
    amin = math.floor(fmn)
    amax = math.ceil(fmx)
    range = amax-amin
    
    unit = range/10.0
    
    grade = math.floor(math.log10(unit))
    sunit = unit / math.pow(10.0, grade)

    if interval is None :

        if sunit < math.sqrt(2.0) :
            interval = math.pow(10.0, grade)
        elif sunit < math.sqrt(10.0) :
            interval = math.pow(10.0, grade) * 2.0
        elif sunit < math.sqrt(50.0) :
            interval = math.pow(10.0, grade) * 5.0
        else :
            interval = pow(10.0, grade+1)
    if maxscale is None :
        maxscale = math.ceil(amax/interval) * interval
    if minscale is None :
        minscale = math.floor(amin/interval) * interval
    
    return (minscale, maxscale, interval)


def scaletime(tmin_ts, tmax_ts) :
    """Picks a time scaling suitable for a time plot.
    
    tmin_ts, tmax_ts: The time stamps in epoch time around which the times will be picked.
    
    Returns a scaling 3-tuple. First element is the start time, second the stop
    time, third the increment. All are in seconds (epoch time in the case of the 
    first two).

    """
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
    start_ts = time.mktime(start_dt.timetuple())
    stop_ts  = time.mktime(stop_dt.timetuple())

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
        
        self.xscale = (lri[0] - uli[0]) / (urs[0] - lls[0])
        self.yscale = -(lri[1] - uli[1]) / (urs[1] - lls[1]) 
        self.xoffset = lri[0] - urs[0] * self.xscale
        self.yoffset = uli[1] - urs[1] * self.yscale

        self.draw    = draw
        
    def line(self, x, y, **options) :
        """Draw a scaled line on the instance's ImageDraw object.
        
        x: sequence of x coordinates
        
        y: sequence of y coordinates, some of which are possibly null (value of None)
        
        """
        # Break the line up around any nulls
        for (x_seq, y_seq) in seq_line(x, y):
            # Scale it
            xy_seq_scaled = zip([self.xtranslate(x) for x in x_seq], 
                                [self.ytranslate(y) for y in y_seq])
             # Draw it:
            if len(xy_seq_scaled) == 1 :
                self.draw.point(xy_seq_scaled, fill = options['fill'])
            else :
                self.draw.line(xy_seq_scaled, **options)
                   
    def rectangle(self, box, **options) :
        """Draw a scaled rectangle.
        
        box: A pair of 2-way tuples, containing coordinates of opposing corners
        of the box.
        
        options: passed on to draw.rectangle. Usually contains 'fill' (the color)
        """
        box_scaled = [(coord[0]*self.xscale + self.xoffset + 0.5, coord[1]*self.yscale + self.yoffset + 0.5) for coord in box]
        self.draw.rectangle(box_scaled, **options)
        
    def xtranslate(self, x):
        return int(x * self.xscale + self.xoffset + 0.5)
                   
    def ytranslate(self, y):
        return int(y * self.yscale + self.yoffset + 0.5)
    
                   
def seq_line(x, y):
    """Generator function that breaks a line up into individual segments around any nulls held in y.
    
    Example: if x=[0,   1,    2,  3,    4,  5,  6,    7]
                y=[10, 20, None, 40, None, 60, 70, None]
    then
        seq_line(x,y) yields
            ([0,1], [10,20])
            ([3], [40])
            ([5,6], [60,70])
    
    x: iterable sequence of x coordinates. All values must be non-null
    
    y: iterable sequence of y coordinates, possibly with some embedded 
    nulls (that is, their value==None)
    
    yields: tuples, first value of which is a list of x-coordinates, and second value a list of y-coordinates,
    of a contiguous line
    
    """
    istart = iend = 0
    
    while iend < len(y):
        if y[iend] is None:
            if istart != iend :
                yield (x[istart:iend], y[istart:iend])
            istart = iend + 1
            while istart < len(y) :
                if y[istart] is not None :
                    break
                istart += 1
            iend = istart
        iend += 1
    
    if istart < len(y) :
        yield (x[istart:iend], y[istart:iend])
           

def pickLabelFormat(increment):

    i_log = math.log10(increment)
    if i_log < 0 :
        i_log = abs(i_log)
        decimal_places = int(i_log)
        if i_log != decimal_places :
            decimal_places += 1
    else :
        decimal_places = 0
        
    return "%%.%df" % decimal_places



 
if __name__ == '__main__' :
    import time
    # Unit test:
    assert(scale(1.1, 12.3) == (1.0, 13.0, 1.0))
    assert(scale(-1.1, 12.3) == (-2.0, 14.0, 2.0))
    assert(scale(-12.1, -5.3) == (-13.0, -5.0, 1.0))
    
    t= time.time()
    scaletime(t - 24*3600 - 20, t)
    
    assert(pickLabelFormat(1) == "%.0f")
    assert(pickLabelFormat(20) == "%.0f")
    assert(pickLabelFormat(.2) == "%.1f")
    assert(pickLabelFormat(.1) == "%.1f")
    
    print "test successful"
