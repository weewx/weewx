#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Generate images for up to an effective date. 
Needs to be refactored into smaller functions.

"""

import time
import datetime
import syslog
import os.path

import weeplot.genplot
import weeplot.utilities
import weeutil.weeutil
import weewx.archive
import weewx.reportengine
import weewx.units

#===============================================================================
#                    Class ImageGenerator
#===============================================================================

class ImageGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the image generator."""

    def run(self):
        
        self.setup()
        
        # Open up the main database archive
        archiveFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                       self.config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
    
        stop_ts = archive.lastGoodStamp() if self.gen_ts is None else self.gen_ts

        # Generate any images
        self.genImages(archive, stop_ts)
        
    def setup(self):
        
        self.weewx_root = self.config_dict['Station']['WEEWX_ROOT']
        self.image_dict = self.skin_dict['ImageGenerator']
        self.title_dict = self.skin_dict['Labels']['Generic']
        self.unit_info  = weewx.units.UnitInfo.fromSkinDict(self.skin_dict)
        self.unit_label_dict  = self.unit_info.getObsLabelDict()
        
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

        if not time_ts:
            time_ts = archive.lastGoodStamp()
            if not time_ts:
                time_ts = time.time()

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.image_dict.sections :
            
            # Now, loop over all plot names in this time span class:
            for plotname in self.image_dict[timespan].sections :
                
                # Accumulate all options from parent nodes:
                plot_options = weeutil.weeutil.accumulateLeaves(self.image_dict[timespan][plotname])

                image_root = os.path.join(self.weewx_root, plot_options['HTML_ROOT'])
                # Get the path of the file that the image is going to be saved to:
                img_file = os.path.join(image_root, '%s.png' % plotname)
                
                # Check whether this plot needs to be done at all:
                ai = plot_options.as_int('aggregate_interval') if plot_options.has_key('aggregate_interval') else None
                if skipThisPlot(time_ts, ai, img_file) :
                    continue
                
                # Create the subdirectory that the image is to be put in.
                # Wrap in a try block in case it already does.
                try:
                    os.makedirs(os.path.dirname(img_file))
                except:
                    pass
                
                # Calculate a suitable min, max time for the requested time span
                (minstamp, maxstamp, timeinc) = weeplot.utilities.scaletime(time_ts - plot_options.as_int('time_length'), time_ts)
                
                # Create a new instance of a time plot and start adding to it
                plot = weeplot.genplot.TimePlot(plot_options)
                
                # Set the min, max time axis
                plot.setXScaling((minstamp, maxstamp, timeinc))
                
                # Set the y-scaling, using any user-supplied hints: 
                plot.setYScaling(weeutil.weeutil.convertToFloat(plot_options.get('yscale')))
                
                # Get a suitable bottom label:
                bottom_label_format = plot_options.get('bottom_label_format', '%m/%d/%y %H:%M')
                bottom_label = time.strftime(bottom_label_format, time.localtime(time_ts))
                plot.setBottomLabel(bottom_label)
        
                # Loop over each line to be added to the plot.
                for line_name in self.image_dict[timespan][plotname].sections:

                    # Accumulate options from parent nodes. 
                    line_options = weeutil.weeutil.accumulateLeaves(self.image_dict[timespan][plotname][line_name])
                    
                    # See what SQL variable type to use for this line. By default,
                    # use the section name.
                    var_type = line_options.get('data_type', line_name)

                    # Add a unit label. NB: all will get overwritten except the last.
                    # Get the label from the configuration dictionary. 
                    # TODO: Allow multiple unit labels, one for each plot line?
                    unit_label = self.unit_label_dict.get(var_type, '')
                    # PIL cannot handle UTF-8. So, convert to Latin1. Also, strip off
                    # any leading and trailing whitespace so it's easy to center
                    unit_label = weeutil.weeutil.utf8_to_latin1(unit_label).strip()
                    plot.setUnitLabel(unit_label)
                    
                    # See if a line label has been explicitly requested:
                    label = line_options.get('label')
                    if not label:
                        # No explicit label. Is there a generic one? 
                        # If not, then the SQL type will be used instead
                        label = self.title_dict.get(var_type, var_type)
                    # Convert to Latin-1
                    label = weeutil.weeutil.utf8_to_latin1(label)
    
                    # See if a color has been explicitly requested.
                    color_str = line_options.get('color')
                    color = int(color_str,0) if color_str is not None else None
                    
                    # Get the line width, if explicitly requested.
                    width_str = line_options.get('width')
                    width = int(width_str) if width_str is not None else None
                    
                    # Get the type of line ("bar', 'line', or 'vector')
                    line_type = line_options.get('plot_type', 'line')
                    
                    if line_type == 'vector':
                        vector_rotate_str = line_options.get('vector_rotate')
                        vector_rotate = -float(vector_rotate_str) if vector_rotate_str is not None else None
                    else:
                        vector_rotate = None
                    
                    # Look for aggregation type:
                    aggregate_type = line_options.get('aggregate_type')
                    if aggregate_type in (None, '', 'None', 'none'):
                        # No aggregation specified.
                        aggregate_type     = None
                        aggregate_interval = None
                    else :
                        try:
                            # Aggregation specified. Get the interval.
                            aggregate_interval = line_options.as_int('aggregate_interval')
                        except KeyError:
                            syslog.syslog(syslog.LOG_ERR, "genimages: aggregate interval required for aggregate type %s" % aggregate_type)
                            syslog.syslog(syslog.LOG_ERR, "genimages: line type %s skipped" % var_type)
                            continue

                    # Get the time and data vectors from the database:
                    (time_vec_t, data_vec_t) = archive.getSqlVectorsExtended(var_type, minstamp, maxstamp, 
                                                                         aggregate_interval, aggregate_type)

                    new_time_vec_t = self.unit_info.convert(time_vec_t)
                    new_data_vec_t = self.unit_info.convert(data_vec_t)
                    # Add the line to the emerging plot:
                    plot.addLine(weeplot.genplot.PlotLine(new_time_vec_t[0], new_data_vec_t[0],
                                                          label         = label, 
                                                          color         = color,
                                                          width         = width,
                                                          line_type     = line_type, 
                                                          interval      = aggregate_interval,
                                                          vector_rotate = vector_rotate))
                    
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
