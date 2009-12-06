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
        self.image_background_color = int(config_dict.get('image_background_color', '0xf5f5f5'), 0)

        self.chart_background_color = int(config_dict.get('chart_background_color', '0xd8d8d8'), 0)
        self.chart_gridline_color   = int(config_dict.get('chart_gridline_color',   '0xa0a0a0'), 0)
        color_list                  = config_dict.get('chart_line_colors', [0xff0000, 0x00ff00, 0x0000ff])
        width_list                  = config_dict.get('chart_line_width',  [1, 1, 1])
        self.chart_line_colors      = [int(v,0) for v in color_list]
        self.chart_line_widths      = [int(v) for v in width_list]

        
        self.top_label_font_path    = config_dict.get('top_label_font_path')
        self.top_label_font_size    = int(config_dict.get('top_label_font_size', 10))

        self.unit_label = None
        self.unit_label_font_path   = config_dict.get('unit_label_font_path')
        self.unit_label_font_color  = int(config_dict.get('unit_label_font_color', '0x000000'), 0)
        self.unit_label_font_size   = int(config_dict.get('unit_label_font_size', 10))
        self.unit_label_position    = (10, 0)
        
        self.bottom_label_font_path = config_dict.get('bottom_label_font_path')
        self.bottom_label_font_color= int(config_dict.get('bottom_label_font_color', '0x000000'), 0)
        self.bottom_label_font_size = int(config_dict.get('bottom_label_font_size', 10))

        self.axis_label_font_path   = config_dict.get('axis_label_font_path')
        self.axis_label_font_color  = int(config_dict.get('axis_label_font_color', '0x000000'), 0)
        self.axis_label_font_size   = int(config_dict.get('axis_label_font_size', 10))

        self.x_label_format         = config_dict.get('x_label_format', None)
        self.y_label_format         = config_dict.get('y_label_format', None)
        
        self.render_rose            = False
        # Rose width and height are hardwired to 21x21:
        self.rose_width             = 21
        self.rose_height            = 21
        self.rose_position          = (self.lmargin + self.padding + 5, self.image_height - self.bmargin - self.padding - self.rose_height)
        self.rose_rotation          = None
        self.rose_label             = config_dict.get('rose_label', 'N')
        self.rose_label_font_path   = config_dict.get('rose_label_font_path', self.bottom_label_font_path)
        self.rose_label_font_size   = int(config_dict.get('rose_label_font_size', 10))  
        self.rose_label_font_color  = int(config_dict.get('rose_label_font_color', '0x000000'), 0)
        self.rose_color             = config_dict.get('rose_color')
        if self.rose_color is not None:
            self.rose_color = int(self.rose_color, 0)

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
        """
        self.xscale = xscale
        
    def setYScaling(self, yscale):
        """Set the Y scaling.
        
        yscale: A 3-way tuple (ymin, ymax, yinc)
        """
        self.yscale = yscale
        
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
        if self.render_rose:
            self._renderRose(image, draw)

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

            if self.line_list[iline].line_type == 'line' :
                sdraw.line(self.line_list[iline].x, 
                           self.line_list[iline].y, 
                           fill  = color,
                           width = width)
            elif self.line_list[iline].line_type == 'bar' :
                interval = self.line_list[iline].interval
                for ibox in xrange(len(self.line_list[iline].x)):
                    x = self.line_list[iline].x[ibox]
                    y = self.line_list[iline].y[ibox]
                    if y is None :
                        continue
                    if ibox > 0:
                        xleft = self.line_list[iline].x[ibox-1]
                    else:
                        xleft = x - interval
                    sdraw.rectangle(((xleft, self.yscale[0]), (x, y)), fill=color, outline=color)
            elif self.line_list[iline].line_type == 'vector' :
                for (x, vec) in zip(self.line_list[iline].x, self.line_list[iline].y):
                    sdraw.vector(x, vec,
                                 vector_rotate = self.line_list[iline].vector_rotate,
                                 fill  = color,
                                 width = width)
                self.render_rose = True
                self.rose_rotation = self.line_list[iline].vector_rotate
                if self.rose_color is None:
                    self.rose_color = color

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
            draw.text(self.unit_label_position,
                      self.unit_label,
                      fill=self.unit_label_font_color, font=unit_label_font)

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

    def _renderRose(self, image, draw):
        """Draw a compass rose."""
        
        # Internal function used to add an opaque alpha channel to an integer RGB value
        def add_alpha(i):
            r = i & 0xff
            g = (i >> 8)  & 0xff
            b = (i >> 16) & 0xff
            a = 0xff    # Opaque alpha
            return (r,g,b,a)

        rose_center_x = self.rose_width/2  + 1
        rose_center_y = self.rose_height/2 + 1
        barb_width  = 3
        barb_height = 3
        # The background is all white with a zero alpha (totally transparent)
        rose_image = Image.new("RGBA", (self.rose_width, self.rose_height), (0x00, 0x00, 0x00, 0x00))
        rose_draw = ImageDraw.Draw(rose_image)
 
        fill_color = add_alpha(self.rose_color)
        # Draw the arrow straight up (North). First the shaft:
        rose_draw.line( ((rose_center_x, 0), (rose_center_x, self.rose_height)), width = 1, fill = fill_color)
        # Now the left barb:
        rose_draw.line( ((rose_center_x - barb_width, barb_height), (rose_center_x, 0)), width = 1, fill = fill_color)
        # And the right barb:
        rose_draw.line( ((rose_center_x, 0), (rose_center_x + barb_width, barb_height)), width = 1, fill = fill_color)
        
        rose_draw.ellipse(((rose_center_x - 4, rose_center_y - 4), (rose_center_x + 4, rose_center_y + 4)), outline = fill_color)

        # Rotate if necessary:
        if self.rose_rotation:
            rose_image = rose_image.rotate(self.rose_rotation)
            rose_draw = ImageDraw.Draw(rose_image)
        
        # Calculate the position of the "N" label:
        rose_label_font = weeutil.weeutil.get_font_handle(self.rose_label_font_path, self.rose_label_font_size)
        rose_label_size = draw.textsize(self.rose_label, font=rose_label_font)
        
        # Draw the label in the middle of the (possibly) rotated arrow
        rose_draw.text((rose_center_x - rose_label_size[0]/2, 
                        rose_center_y - rose_label_size[1]/2),
                        self.rose_label,
                        fill = add_alpha(self.rose_label_font_color),
                        font = rose_label_font)

        # Paste the image of the arrow on to the main plot. The alpha
        # channel of the image will be used as the mask.
        # This will cause the arrow to overlay the background plot
        image.paste(rose_image, self.rose_position, rose_image)
        

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
        # The try block is necessary because min of an empty list throws a
        # ValueError exception.
        ymin = ymax = None
        for line in self.line_list:
            if line.line_type == 'vector':
                try:
                    yline_max = max(abs(c) for c in filter(lambda v : v is not None, line.y))
                except ValueError:
                    pass
                yline_min = - yline_max if yline_max is not None else None
            else:
                try :
                    yline_min = min(filter(lambda v : v is not None, line.y))
                except ValueError:
                    pass
                try :
                    yline_max = max(filter(lambda v : v is not None, line.y))
                except ValueError:
                    pass
            ymin = min(yline_min, ymin) if ymin is not None else yline_min
            ymax = max(yline_max, ymax) if ymax is not None else yline_max

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
    def __init__(self, x, y, label='', color=None, width=None, line_type='line', interval=None, vector_rotate = None):
        self.x         = x
        self.y         = y
        self.label     = label
        self.line_type = line_type
        self.color     = color
        self.width     = width
        self.interval  = interval
        self.vector_rotate = vector_rotate

