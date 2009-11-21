#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Routines for generating image plots.
"""
import time
import Image
import ImageDraw
import ImageFont
import weeplot
import weeplot.utilities
import weeutil.weeutil
        

class GeneralPlot(object):
    """Holds various parameters necessary for a plot. It should be specialized by the type of plot.
    
    """
    def __init__(self, config_dict):
        """Initialize an instance of GeneralPlot.
        
        config_dict: an instance of ConfigObj, or something that looks like it.
        
        """
        
        self.line_list = []
        
        self.xscale = None
        self.yscale = None
        
        self.lmargin = 35
        self.rmargin = 20
        self.bmargin = 30
        self.tmargin = 20
        self.tbandht = 12
        self.padding =  3

        self.image_width            = int(config_dict.get('image_width',  300))
        self.image_height           = int(config_dict.get('image_height', 180))
        self.image_background_color = int(config_dict.get('image_background_color', 0xf5f5f5), 0)

        self.chart_background_color = int(config_dict.get('chart_background_color', 0xd8d8d8), 0)
        self.chart_gridline_color   = int(config_dict.get('chart_gridline_color',   0xa0a0a0), 0)
        color_list                  = config_dict.get('chart_line_colors', [0xff0000, 0x00ff00, 0x0000ff])
        width_list                  = config_dict.get('chart_line_width',  [1, 1, 1])
        self.chart_line_colors      = [int(v,0) for v in color_list]
        self.chart_line_widths      = [int(v) for v in width_list]

        
        self.top_label_font_path    = config_dict.get('top_label_font_path')
        self.top_label_font_size    = int(config_dict.get('top_label_font_size', 10))

        self.unit_label = None
        self.unit_label_font_path   = config_dict.get('unit_label_font_path')
        self.unit_label_font_color  = int(config_dict.get('unit_label_font_color', 0x000000), 0)
        self.unit_label_font_size   = int(config_dict.get('unit_label_font_size', 10))
        
        self.bottom_label_font_path = config_dict.get('bottom_label_font_path')
        self.bottom_label_font_color= int(config_dict.get('bottom_label_font_color', 0x000000), 0)
        self.bottom_label_font_size = int(config_dict.get('bottom_label_font_size', 10))

        self.axis_label_font_path   = config_dict.get('axis_label_font_path')
        self.axis_label_font_color  = int(config_dict.get('axis_label_font_color', 0x000000), 0)
        self.axis_label_font_size   = int(config_dict.get('axis_label_font_size', 10))

        self.x_label_format         = config_dict.get('x_label_format', None)
        self.y_label_format         = config_dict.get('y_label_format', None)
    def setBottomLabel(self, bottom_label):
        """Set the label to be put at the bottom of the plot.
        
        """
        self.bottom_label = bottom_label
        
    def setUnitLabel(self, unit_label):
        """Set the label to be used to show the units of the plot.
        
        """
        self.unit_label = unit_label
        
    def setXScaling(self, xscale):
        """Set the X scaling.
        
        xscale: A 3-way tuple (xmin, xmax, xinc)
        
        returns: The old scaling
        """
        old = self.xscale
        self.xscale = xscale
        return old
        
    def setYScaling(self, yscale):
        """Set the Y scaling.
        
        yscale: A 3-way tuple (ymin, ymax, yinc)
        
        returns: The old scaling
        """
        old = self.yscale
        self.yscale = yscale
        return old
        
    def addLine(self, line):
        """Add a line to be plotted.
        
        line: an instance of PlotLine
        
        """
        if line.x.count(None) != 0 :
            raise weeplot.ViolatedPrecondition, "X vector cannot have any values 'None' "
        self.line_list.append(line)
        

    def render(self):
        """Traverses the universe of things that have to be plotted in this image, rendering
        them and returning the results as a new Image object.
        
        """

        # NB: In what follows the variable 'draw' is an instance of an ImageDraw object and is in pixel units.
        # The variable 'sdraw' is an instance of ScaledDraw and its units are in the "scaled" units of the plot
        # (e.g., the horizontal scaling might be for seconds, the vertical for degrees Fahrenheit.)
        image = Image.new("RGB", (self.image_width, self.image_height), self.image_background_color)
        draw = self._getImageDraw(image)
        draw.rectangle(((self.lmargin,self.tmargin), 
                        (self.image_width - self.rmargin, self.image_height - self.bmargin)), 
                        fill=self.chart_background_color)
        
        self._renderBottom(draw)
        self._renderTopBand(draw)
        
        self._calcXScaling()
        self._calcYScaling()
        self._calcXLabelFormat()
        self._calcYLabelFormat()
        
        sdraw = self._getScaledDraw(draw)
        self._renderXAxes(sdraw)
        self._renderYAxes(sdraw)
        self._renderPlotLines(sdraw)

        return image
    
    def _getImageDraw(self, image):
        """Returns an instance of ImageDraw with the proper dimensions and background color"""
        draw = ImageDraw.Draw(image)
        return draw
    
    def _getScaledDraw(self, draw):
        """Returns an instance of ScaledDraw, with the appropriate scaling.
        
        draw: An instance of ImageDraw
        """
        sdraw = weeplot.utilities.ScaledDraw(draw, ((self.lmargin + self.padding, self.tmargin + self.padding),
                                                    (self.image_width - self.rmargin - self.padding, self.image_height - self.bmargin - self.padding)),
                                                    ((self.xscale[0], self.yscale[0]), (self.xscale[1], self.yscale[1])))
        return sdraw
        
    def _renderXAxes(self, sdraw):
        """Draws the x axis and vertical constant-x lines, as well as the labels.
        
        """

        axis_label_font = weeutil.weeutil.get_font_handle(self.axis_label_font_path,
                                                          self.axis_label_font_size)

        drawlabel = False
        for x in weeutil.weeutil.stampgen(self.xscale[0], self.xscale[1], self.xscale[2]) :
            sdraw.line((x, x), (self.yscale[0], self.yscale[1]), fill=self.chart_gridline_color)
            drawlabel = not drawlabel
            if drawlabel:
                xlabel = self._genXLabel(x)
                axis_label_size = sdraw.draw.textsize(xlabel, font=axis_label_font)
                xpos = sdraw.xtranslate(x)
                sdraw.draw.text((xpos - axis_label_size[0]/2, self.image_height - self.bmargin + 2),
                                xlabel, fill=self.axis_label_font_color, font=axis_label_font)
                

    def _renderYAxes(self, sdraw):
        """Draws the y axis and horizontal constant-y lines, as well as the labels.
        Should be sufficient for most purposes.
        
        """
        nygridlines     = int((self.yscale[1] - self.yscale[0]) / self.yscale[2] + 1.5)
        axis_label_font = weeutil.weeutil.get_font_handle(self.axis_label_font_path,
                                                                self.axis_label_font_size)
        
        # Draw the (constant y) grid lines 
        for i in xrange(nygridlines) :
            y = self.yscale[0] + i * self.yscale[2]
            sdraw.line((self.xscale[0], self.xscale[1]), (y, y), fill=self.chart_gridline_color)
            # Draw a bel on every other line:
            if i%2 == 0 :
                ylabel = self._genYLabel(y)
                axis_label_size = sdraw.draw.textsize(ylabel, font=axis_label_font)
                ypos = sdraw.ytranslate(y)
                sdraw.draw.text((self.lmargin - axis_label_size[0] - 2, ypos - axis_label_size[1]/2),
                                ylabel, fill=self.axis_label_font_color, font=axis_label_font)
            
    def _renderPlotLines(self, sdraw):
        """Draw the collection of lines, using a different color for each one. Because there is
        a limited set of colors, they need to be recycled if there are very many lines.
        
        """
        nlines = len(self.line_list)
        # Draw them in reverse order, so the first line comes out on top of the image
        for iline in xrange(nlines-1, -1, -1):
            color = self.line_list[iline].color
            if color is None :
                color = self.chart_line_colors[iline%nlines]
            width = self.line_list[iline].width
            if width is None :
                width = self.chart_line_widths[iline%nlines]

            if self.line_list[iline].type == 'line' :
                sdraw.line(self.line_list[iline].x, 
                           self.line_list[iline].y, 
                           fill  = color,
                           width = width)
            elif self.line_list[iline].type == 'bar' :
                interval = self.line_list[iline].interval
                for ibox in xrange(len(self.line_list[iline].x)):
                    x = self.line_list[iline].x[ibox]
                    y = self.line_list[iline].y[ibox]
                    if y is None :
                        continue
                    xleft = x - interval
                    if ibox > 0:
                        xleft = max(xleft, self.line_list[iline].x[ibox-1])
                    sdraw.rectangle(((xleft, self.yscale[0]), (x, y)), fill=color, outline=color)
        
    def _renderBottom(self, draw):
        """Draw anything at the bottom (just some text right now).
        
        """
        bottom_label_font = weeutil.weeutil.get_font_handle(self.bottom_label_font_path, self.bottom_label_font_size)
        bottom_label_size = draw.textsize(self.bottom_label, font=bottom_label_font)
        
        draw.text(((self.image_width - bottom_label_size[0])/2, self.image_height - bottom_label_size[1] - 3),
                  self.bottom_label, 
                  fill=self.bottom_label_font_color,
                  font=bottom_label_font)
        
        
        
    def _renderTopBand(self, draw):
        """Draw the top band and any text in it.
        
        """
        # Draw the top band rectangle
        draw.rectangle(((0,0), 
                        (self.image_width, self.tbandht)), 
                        fill = self.chart_background_color)

        # Put the units in the upper left corner
        unit_label_font = weeutil.weeutil.get_font_handle(self.unit_label_font_path, self.unit_label_font_size)
        if self.unit_label:
            draw.text((0,0), self.unit_label, fill=self.unit_label_font_color, font=unit_label_font)

        top_label_font = weeutil.weeutil.get_font_handle(self.top_label_font_path, self.top_label_font_size)
        
        # The top label is the appended label_list. However, it has to be drawn in segments 
        # because each label may be in a different color. For now, append them together to get
        # the total width
        top_label = ' '.join([line.label for line in self.line_list])
        top_label_size = draw.textsize(top_label, font=top_label_font)
        
        x = (self.image_width - top_label_size[0])/2
        y = 0
        nlabels = len(self.line_list)
        
        for i in xrange(nlabels) :
            color = self.line_list[i].color
            if color is None :
                color = self.chart_line_colors[i%nlabels]
            # Draw a label
            draw.text( (x,y), self.line_list[i].label, fill = color, font = top_label_font)
            # Now advance the width of the label we just drew, plus a space:
            label_size = draw.textsize(self.line_list[i].label + ' ', font= top_label_font)
            x += label_size[0]

    def _calcXScaling(self):
        """Calculates the x scaling. It will probably be specialized by
        plots where the x-axis represents time.
        
        """
        if self.xscale is None :
            (xmin, xmax) = self._calcXMinMax()
                
            self.xscale = weeplot.utilities.scale(xmin, xmax)
            
    def _calcYScaling(self):
        """Calculates y scaling. Can be used 'as-is' for most purposes.
        
        """
        # The filter is necessary because unfortunately the value 'None' is not
        # excluded from min and max (i.e., min(None, x) is not necessarily x). 
        # Plus, min of an empty list throws a ValueError exception.
        ymin = ymax = None
        for line in self.line_list:
            try :
                yline_min = min(filter(lambda v : v is not None, line.y))
                ymin = min(yline_min, ymin) if ymin is not None else yline_min
            except ValueError:
                pass
            try :
                yline_max = max(filter(lambda v : v is not None, line.y))
                ymax = max(yline_max, ymax) if ymax is not None else yline_max
            except ValueError:
                pass
        
        if ymin is None and ymax is None :
            # No valid data. Pick an arbitrary scaling
            self.yscale=(0.0, 1.0, 0.2)
        else:
            self.yscale = weeplot.utilities.scale(ymin, ymax, self.yscale)

    def _calcXLabelFormat(self):
        if self.x_label_format is None:
            self.x_label_format = weeplot.utilities.pickLabelFormat(self.xscale[2])

    def _calcYLabelFormat(self):
        if self.y_label_format is None:
            self.y_label_format = weeplot.utilities.pickLabelFormat(self.yscale[2])
        
    def _genXLabel(self, x):
        xlabel = self.x_label_format % x
        return xlabel
    
    def _genYLabel(self, y):
        ylabel = self.y_label_format % y
        return ylabel
    
    def _calcXMinMax(self):
        xmin = None
        xmax = None
        for line in self.line_list:
            xlinemin = min(line.x)
            xlinemax = max(line.x)
            assert(xlinemin is not None and xlinemax is not None)
            # If the line represents a bar chart (interval not None),
            # then the actual minimum has to be adjusted for the
            # interval length
            if line.interval is not None:
                xlinemin = xlinemin - line.interval
            xmin = min(xlinemin, xmin) if xmin is not None else xlinemin
            xmax = max(xlinemax, xmax) if xmax is not None else xlinemax
        return (xmin, xmax)
    
class TimePlot(GeneralPlot) :
    """Class that specializes GeneralPlot for plots where the x-axis is time.
    
    """
    
    def _calcXScaling(self):
        """Specialized version for time plots.
        
        """
        if self.xscale is None :
            (xmin, xmax) = self._calcXMinMax()
                
            self.xscale = weeplot.utilities.scaletime(xmin, xmax)
        
    def _genXLabel(self, x):
        time_tuple = time.localtime(x)
        xlabel = time.strftime(self.x_label_format, time_tuple)
        return xlabel
    
class PlotLine(object):
    """Represents a single line (or bar) in a plot.
    
    """
    def __init__(self, x, y, label='', color=None, width=None, type='line', interval=None):
        self.x        = x
        self.y        = y
        self.label    = label
        self.type     = type
        self.color    = color
        self.width    = width
        self.interval = interval
