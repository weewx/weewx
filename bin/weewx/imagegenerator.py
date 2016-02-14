#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate images for up to an effective date. 
Needs to be refactored into smaller functions."""

from __future__ import with_statement
import time
import datetime
import syslog
import os.path

import weeplot.genplot
import weeplot.utilities
import weeutil.weeutil
import weewx.reportengine
import weewx.units
from weeutil.weeutil import to_bool, to_int, to_float

#===============================================================================
#                    Class ImageGenerator
#===============================================================================

class ImageGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the image generator."""
    
    def run(self):
        self.setup()
        self.genImages(self.gen_ts)
        
    def setup(self):
        self.image_dict = self.skin_dict['ImageGenerator']
        self.title_dict = self.skin_dict.get('Labels', {}).get('Generic', {})
        self.formatter  = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter  = weewx.units.Converter.fromSkinDict(self.skin_dict)
        # determine how much logging is desired
        self.log_success = to_bool(self.image_dict.get('log_success', True))

    def genImages(self, gen_ts):
        """Generate the images.
        
        The time scales will be chosen to include the given timestamp, with
        nice beginning and ending times.
    
        gen_ts: The time around which plots are to be generated. This will
        also be used as the bottom label in the plots. [optional. Default is
        to use the time of the last record in the database.]
        """
        t1 = time.time()
        ngen = 0

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.image_dict.sections :
            
            # Now, loop over all plot names in this time span class:
            for plotname in self.image_dict[timespan].sections :
                
                # Accumulate all options from parent nodes:
                plot_options = weeutil.weeutil.accumulateLeaves(
                    self.image_dict[timespan][plotname])

                plotgen_ts = gen_ts
                if not plotgen_ts:
                    binding = plot_options['data_binding']
                    archive = self.db_binder.get_manager(binding)
                    plotgen_ts = archive.lastGoodStamp()
                    if not plotgen_ts:
                        plotgen_ts = time.time()

                image_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                          plot_options['HTML_ROOT'])
                # Get the path that the image is going to be saved to:
                img_file = os.path.join(image_root, '%s.png' % plotname)
                
                # Check whether this plot needs to be done at all:
                ai = plot_options.as_int('aggregate_interval') if plot_options.has_key('aggregate_interval') else None
                if skipThisPlot(plotgen_ts, ai, img_file) :
                    continue
                
                # Create the subdirectory that the image is to be put in.
                # Wrap in a try block in case it already exists.
                try:
                    os.makedirs(os.path.dirname(img_file))
                except OSError:
                    pass
                
                # Create a new instance of a time plot and start adding to it
                plot = weeplot.genplot.TimePlot(plot_options)
                
                # Calculate a suitable min, max time for the requested time
                # span and set it
                (minstamp, maxstamp, timeinc) = weeplot.utilities.scaletime(plotgen_ts - int(plot_options.get('time_length', 86400)), plotgen_ts)
                plot.setXScaling((minstamp, maxstamp, timeinc))
                
                # Set the y-scaling, using any user-supplied hints: 
                plot.setYScaling(weeutil.weeutil.convertToFloat(plot_options.get('yscale', ['None', 'None', 'None'])))
                
                # Get a suitable bottom label:
                bottom_label_format = plot_options.get('bottom_label_format', '%m/%d/%y %H:%M')
                bottom_label = time.strftime(bottom_label_format, time.localtime(plotgen_ts))
                plot.setBottomLabel(bottom_label)

                # Set day/night display
                plot.setLocation(self.stn_info.latitude_f, self.stn_info.longitude_f)
                plot.setDayNight(to_bool(plot_options.get('show_daynight', False)),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_day_color', '0xffffff')),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_night_color', '0xf0f0f0')),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_edge_color', '0xefefef')))

                # Loop over each line to be added to the plot.
                for line_name in self.image_dict[timespan][plotname].sections:

                    # Accumulate options from parent nodes. 
                    line_options = weeutil.weeutil.accumulateLeaves(self.image_dict[timespan][plotname][line_name])
                    
                    # See what SQL variable type to use for this line. By
                    # default, use the section name.
                    var_type = line_options.get('data_type', line_name)

                    # Look for aggregation type:
                    aggregate_type = line_options.get('aggregate_type')
                    if aggregate_type in (None, '', 'None', 'none'):
                        # No aggregation specified.
                        aggregate_type = aggregate_interval = None
                    else :
                        try:
                            # Aggregation specified. Get the interval.
                            aggregate_interval = line_options.as_int('aggregate_interval')
                        except KeyError:
                            syslog.syslog(syslog.LOG_ERR, "genimages: aggregate interval required for aggregate type %s" % aggregate_type)
                            syslog.syslog(syslog.LOG_ERR, "genimages: line type %s skipped" % var_type)
                            continue

                    # Now its time to find and hit the database:
                    binding = line_options['data_binding']
                    archive = self.db_binder.get_manager(binding)
                    (start_vec_t, stop_vec_t, data_vec_t) = \
                            archive.getSqlVectors((minstamp, maxstamp), var_type, aggregate_type=aggregate_type,
                                                  aggregate_interval=aggregate_interval)

                    if weewx.debug:
                        assert(len(start_vec_t) == len(stop_vec_t))

                    # Do any necessary unit conversions:
                    new_start_vec_t = self.converter.convert(start_vec_t)
                    new_stop_vec_t  = self.converter.convert(stop_vec_t)
                    new_data_vec_t = self.converter.convert(data_vec_t)

                    # Add a unit label. NB: all will get overwritten except the
                    # last. Get the label from the configuration dictionary. 
                    # TODO: Allow multiple unit labels, one for each plot line?
                    unit_label = line_options.get('y_label', weewx.units.get_label_string(self.formatter, self.converter, var_type))
                    # Strip off any leading and trailing whitespace so it's
                    # easy to center
                    plot.setUnitLabel(unit_label.strip())
                    
                    # See if a line label has been explicitly requested:
                    label = line_options.get('label')
                    if not label:
                        # No explicit label. Is there a generic one? 
                        # If not, then the SQL type will be used instead
                        label = self.title_dict.get(var_type, var_type)
    
                    # See if a color has been explicitly requested.
                    color = line_options.get('color')
                    if color is not None: color = weeplot.utilities.tobgr(color)
                    
                    # Get the line width, if explicitly requested.
                    width = to_int(line_options.get('width'))
                    
                    # Get the type of plot ("bar', 'line', or 'vector')
                    plot_type = line_options.get('plot_type', 'line')

                    interval_vec = None                        

                    # Some plot types require special treatments:
                    if plot_type == 'vector':
                        vector_rotate_str = line_options.get('vector_rotate')
                        vector_rotate = -float(vector_rotate_str) if vector_rotate_str is not None else None
                    else:
                        vector_rotate = None

                        gap_fraction = None
                        if plot_type == 'bar':
                            interval_vec = [x[1] - x[0]for x in zip(new_start_vec_t.value, new_stop_vec_t.value)]
                        elif plot_type == 'line':
                            gap_fraction = to_float(line_options.get('line_gap_fraction'))
                        if gap_fraction is not None:
                            if not 0 < gap_fraction < 1:
                                syslog.syslog(syslog.LOG_ERR, "genimages: Gap fraction %5.3f outside range 0 to 1. Ignored." % gap_fraction)
                                gap_fraction = None

                    # Get the type of line (only 'solid' or 'none' for now)
                    line_type = line_options.get('line_type', 'solid')
                    if line_type.strip().lower() in ['', 'none']:
                        line_type = None
                        
                    marker_type = line_options.get('marker_type')
                    marker_size = to_int(line_options.get('marker_size', 8))
                    
                    # Add the line to the emerging plot:
                    plot.addLine(weeplot.genplot.PlotLine(
                        new_stop_vec_t[0], new_data_vec_t[0],
                        label         = label, 
                        color         = color,
                        width         = width,
                        plot_type     = plot_type,
                        line_type     = line_type,
                        marker_type   = marker_type,
                        marker_size   = marker_size,
                        bar_width     = interval_vec,
                        vector_rotate = vector_rotate,
                        gap_fraction  = gap_fraction))

                # OK, the plot is ready. Render it onto an image
                image = plot.render()
                
                try:
                    # Now save the image
                    image.save(img_file)
                    ngen += 1
                except IOError, e:
                    syslog.syslog(syslog.LOG_CRIT, "genimages: Unable to save to file '%s' %s:" % (img_file, e))
        t2 = time.time()

        if self.log_success:
            syslog.syslog(syslog.LOG_INFO, "genimages: Generated %d images for %s in %.2f seconds" % (ngen, self.skin_dict['REPORT_NAME'], t2 - t1))

def skipThisPlot(time_ts, aggregate_interval, img_file):
    """A plot can be skipped if it was generated recently and has not changed.
    This happens if the time since the plot was generated is less than the
    aggregation interval."""
    
    # Images without an aggregation interval have to be plotted every time.
    # Also, the image definitely has to be generated if it doesn't exist.
    if aggregate_interval is None or not os.path.exists(img_file):
        return False

    # If its a very old image, then it has to be regenerated
    if time_ts - os.stat(img_file).st_mtime >= aggregate_interval:
        return False
    
    # Finally, if we're on an aggregation boundary, regenerate.
    time_dt = datetime.datetime.fromtimestamp(time_ts)
    tdiff = time_dt -  time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return abs(tdiff.seconds % aggregate_interval) > 1
