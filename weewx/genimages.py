#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    Revision: $Rev$
#    Author:   $Author$
#    Date:     $Date$
#
"""Generate images for up to an effective date. 
Needs to be refactored into smaller functions.

"""

import time
import datetime
import syslog
import os.path
import weeutil.weeutil
import weeplot.genplot
import weeplot.utilities

class GenImages(object):
    """Generate plots of the weather data.
    
    This class generates all the images specified in the ['Images'] section
    of the given configuration dictionary. Typically, this is daily, weekly,
    monthly, and yearly time plots.
    
    """
    
    def __init__(self, config_dict):
        """    config_dict: An instance of ConfigObj. It must have sections ['Station'] (for key
        'WEEWX_ROOT'), ['Archive'] (for key 'archive_file'), and a section ['Images'] (containing
        the images to be generated.)
        The generated images will be put in the directory specified by ['Images']['image_root']
        """    
    
        self.image_dict  = config_dict['Images']
        self.label_dict  = config_dict['Labels']
        self.image_root  = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                        config_dict['Images']['image_root'])
    def genImages(self, archive, time_ts):
        """Generate the images.
        
        The time scales will be chosen to include the given timestamp, with nice beginning
        and ending times.
    
        time_ts: The time around which plots are to be generated. This will also be used as
        the bottom label in the plots. [optional. Default is to use the time of the last record
        in the archive database.]
        """
        t1 = time.time()
        ngen = 0

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.image_dict.sections :
            
            # Now, loop over all plot names in this time span class:
            for plotname in self.image_dict[timespan].sections :
                
                # Accumulate all options from parent nodes:
                plot_options = weeutil.weeutil.accumulatescalars(self.image_dict[timespan][plotname])
                
                # Get the name of the file that the image is going to be saved to:
                img_file = os.path.join(self.image_root, '%s.png' % plotname)
    
                # Check whether this plot needs to be done:
                s = plot_options.get('aggregate_interval')
                ai = int(s) if s is not None else None 
                if skipThisPlot(time_ts, ai, img_file) :
                    continue
                
                # Calculate a suitable min, max time for the requested time span
                (minstamp, maxstamp, timeinc) = weeplot.utilities.scaletime(time_ts - plot_options.as_int('time_length'), time_ts)
    
                sql_list = []
                line_options = {}
                line_type_list = self.image_dict[timespan][plotname].sections
                # Gather the data necessary for this plot.
                # Loop over each line type ('outTemp', 'rain', etc.) within the plot.
                for line_type in line_type_list:
                    # Accumulate options from parent nodes. 
                    line_options[line_type] = weeutil.weeutil.accumulatescalars(self.image_dict[timespan][plotname][line_type])
                    
                    # Look for aggregation type:
                    aggregate_type = line_options[line_type].get('aggregate_type')
                    if aggregate_type is None or aggregate_type=='' or aggregate_type == 'none':
                        # No aggregation specified.
                        aggregate_type = None
                        aggregate_interval = None
                        sql_list.append(line_type)
                    else :
                        # Aggregation specified. Get the interval.
                        # TODO: Assumes that all lines use the same aggregation interval.
                        aggregate_interval = line_options[line_type].as_int('aggregate_interval')
                        # Form the SQL aggregation of this variable. 
                        # Results will look like 'max(windGust)', etc.
                        # Then append it to the list of desired variables.
                        sql_list.append("%s(%s)" % (aggregate_type, line_type))
                    
                # We've accumulated all the variable types necessary for this plot.
                # Go get them.
                (timevec, yvals) = archive.getSqlVectorsTS(sql_list, minstamp, maxstamp, aggregate_interval)
                
                # Create a new instance of a time plot and start adding to it
                plot = weeplot.genplot.TimePlot(plot_options)
                
                # Set the min, max time axis here.
                plot.setXScaling((minstamp, maxstamp, timeinc))
                
                # Get a suitable bottom label:
                bottom_label_format = plot_options.get('bottom_label_format', '%m/%d/%y %H:%M')
                bottom_label = time.strftime(bottom_label_format, time.localtime(time_ts))
                plot.setBottomLabel(bottom_label)
        
                # Go through each line, adding it to the plot with suitable label, color, and width
                for i, line_type in enumerate(line_type_list):
                    
                    # See if a line label has been explicitly requested:
                    label = self.image_dict[timespan][plotname][line_type].get('label')
                    if not label:
                        # No explicit label. Is there a generic one in the config dict?
                        label = self.label_dict['Generic'].get(line_type)
                        if not label:
                            # Nope. Just use the SQL type
                            label=line_type
    
                    # See if a color has been explicitly requested.
                    color_str = self.image_dict[timespan][plotname][line_type].get('color')
                    color = int(color_str,0) if color_str is not None else None
                    
                    # Get the line width, if explicitly requested.
                    width_str = line_options[line_type].get('width')
                    width = int(width_str) if width_str is not None else None
                    
                    # Get the type of line ("bar', or 'line')
                    type = line_options[line_type].get('plot_type', 'line')
                    
                    aggregate_interval = line_options[line_type].as_int('aggregate_interval') if type != 'line' else None
                    
                    # Add the data to the emerging plot:
                    plot.addLine(weeplot.genplot.PlotLine(timevec, yvals[i], 
                                                          label    = label, 
                                                          color    = color,
                                                          width    = width,
                                                          type     = type, 
                                                          interval = aggregate_interval))
                    
                    # Add a unit label. NB: all will get overwritten except the last.
                    # TODO: Allow multiple unit labels, one for each plot line?
                    # Get the label from the configuration dictionary. 
                    unit_label = self.label_dict['ImperialUnits'].get(line_type, '')
                    # Because it is likely to use escaped characters, decode it.
                    unit_label = unit_label.decode('string_escape')
                    plot.setUnitLabel(unit_label)
                    
                # OK, the plot is ready. Render it onto an image
                image = plot.render()
                
                # Now save the image
                image.save(img_file)
                ngen += 1
        t2 = time.time()
        
        syslog.syslog(syslog.LOG_INFO, "genimages: Generated %d images in %.2f seconds" % (ngen, t2 - t1))


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
