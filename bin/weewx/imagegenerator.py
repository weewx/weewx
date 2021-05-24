#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate images for up to an effective date.
Should probably be refactored into smaller functions."""

from __future__ import absolute_import
from __future__ import with_statement

import datetime
import logging
import os.path
import time

from six.moves import zip

import weeplot.genplot
import weeplot.utilities
import weeutil.logger
import weeutil.weeutil
import weewx.reportengine
import weewx.units
import weewx.xtypes
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_bool, to_int, to_float, TimeSpan
from weewx.units import ValueTuple

log = logging.getLogger(__name__)


# =============================================================================
#                    Class ImageGenerator
# =============================================================================

class ImageGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the image generator."""

    def run(self):
        self.setup()
        self.genImages(self.gen_ts)

    def setup(self):
        try:
            g = self.skin_dict['Labels']['Generic']
        except KeyError:
            g = {}
        try:
            t = self.skin_dict['Texts']['Images']
        except KeyError:
            t = {}
        # generic_dict will contain "generic" labels, such as "Outside Temperature"
        self.generic_dict = weeutil.weeutil.KeyDict(g)
        # text_dict contains translated text strings
        self.text_dict = weeutil.weeutil.KeyDict(t)
        self.image_dict = self.skin_dict['ImageGenerator']
        self.formatter  = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter  = weewx.units.Converter.fromSkinDict(self.skin_dict)
        # ensure that the skin_dir is in the image_dict
        self.image_dict['skin_dir'] = os.path.join(
            self.config_dict['WEEWX_ROOT'],
            self.skin_dict['SKIN_ROOT'],
            self.skin_dict['skin'])
        # ensure that we are in a consistent right location
        os.chdir(self.image_dict['skin_dir'])

    def genImages(self, gen_ts):
        """Generate the images.

        The time scales will be chosen to include the given timestamp, with nice beginning and
        ending times.

        Args:
            gen_ts (int): The time around which plots are to be generated. This will also be used
                as the bottom label in the plots. [optional. Default is to use the time of the last
                record in the database.]
        """
        t1 = time.time()
        ngen = 0

        # determine how much logging is desired
        log_success = to_bool(search_up(self.image_dict, 'log_success', True))

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.image_dict.sections:

            # Now, loop over all plot names in this time span class:
            for plotname in self.image_dict[timespan].sections:

                # Accumulate all options from parent nodes:
                plot_options = accumulateLeaves(self.image_dict[timespan][plotname])

                plotgen_ts = gen_ts
                if not plotgen_ts:
                    binding = plot_options['data_binding']
                    db_manager = self.db_binder.get_manager(binding)
                    plotgen_ts = db_manager.lastGoodStamp()
                    if not plotgen_ts:
                        plotgen_ts = time.time()

                image_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                          plot_options['HTML_ROOT'])
                # Get the path that the image is going to be saved to:
                img_file = os.path.join(image_root, '%s.png' % plotname)

                # Convert from string to an integer:
                ai = weeutil.weeutil.nominal_spans(plot_options.get('aggregate_interval'))
                # Check whether this plot needs to be done at all:
                if skipThisPlot(plotgen_ts, ai, img_file):
                    continue

                # skip image files that are fresh, but only if staleness is defined
                stale = to_int(plot_options.get('stale_age'))
                if stale:
                    t_now = time.time()
                    try:
                        last_mod = os.path.getmtime(img_file)
                        if t_now - last_mod < stale:
                            log.debug("Skip '%s': last_mod=%s age=%s stale=%s",
                                      img_file, last_mod, t_now - last_mod, stale)
                            continue
                    except os.error:
                        pass

                # Create the subdirectory that the image is to be put in. Wrap in a try block in
                # case it already exists.
                try:
                    os.makedirs(os.path.dirname(img_file))
                except OSError:
                    pass

                # Create a new instance of a time plot and start adding to it
                plot = weeplot.genplot.TimePlot(plot_options)

                # Calculate a suitable min, max time for the requested time.
                minstamp, maxstamp, timeinc = weeplot.utilities.scaletime(
                    plotgen_ts - int(plot_options.get('time_length', 86400)), plotgen_ts)
                # Override the x interval if the user has given an explicit interval:
                timeinc_user = to_int(plot_options.get('x_interval'))
                if timeinc_user is not None:
                    timeinc = timeinc_user
                plot.setXScaling((minstamp, maxstamp, timeinc))

                # Set the y-scaling, using any user-supplied hints:
                yscale = plot_options.get('yscale', ['None', 'None', 'None'])
                plot.setYScaling(weeutil.weeutil.convertToFloat(yscale))

                # Get a suitable bottom label:
                bottom_label_format = plot_options.get('bottom_label_format', '%m/%d/%y %H:%M')
                bottom_label = time.strftime(bottom_label_format, time.localtime(plotgen_ts))
                plot.setBottomLabel(bottom_label)

                # Set day/night display
                plot.setLocation(self.stn_info.latitude_f, self.stn_info.longitude_f)
                plot.setDayNight(to_bool(plot_options.get('show_daynight', False)),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_day_color',
                                                                          '0xffffff')),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_night_color',
                                                                          '0xf0f0f0')),
                                 weeplot.utilities.tobgr(plot_options.get('daynight_edge_color',
                                                                          '0xefefef')))

                # Loop over each line to be added to the plot.
                for line_name in self.image_dict[timespan][plotname].sections:

                    # Accumulate options from parent nodes.
                    line_options = accumulateLeaves(self.image_dict[timespan][plotname][line_name])

                    # See what observation type to use for this line. By default, use the section
                    # name.
                    var_type = line_options.get('data_type', line_name)

                    # Look for aggregation type:
                    aggregate_type = line_options.get('aggregate_type')
                    if aggregate_type in (None, '', 'None', 'none'):
                        # No aggregation specified.
                        aggregate_type = aggregate_interval = None
                    else:
                        try:
                            # Aggregation specified. Get the interval.
                            aggregate_interval = weeutil.weeutil.nominal_spans(
                                line_options['aggregate_interval'])
                        except KeyError:
                            log.error("Aggregate interval required for aggregate type %s",
                                      aggregate_type)
                            log.error("Line type %s skipped", var_type)
                            continue

                    # Now its time to find and hit the database:
                    binding = line_options['data_binding']
                    db_manager = self.db_binder.get_manager(binding)
                    # we need to pass the line options and plotgen_ts to our xtype
                    # first get a copy of line_options
                    option_dict = dict(line_options)
                    # but we need to pop off aggregate_type and
                    # aggregate_interval as they are used as explicit arguments
                    # in our xtypes call
                    option_dict.pop('aggregate_type', None)
                    option_dict.pop('aggregate_interval', None)
                    # then add plotgen_ts
                    option_dict['plotgen_ts'] = plotgen_ts
                    start_vec_t, stop_vec_t ,data_vec_t = weewx.xtypes.get_series(
                        var_type,
                        TimeSpan(minstamp, maxstamp),
                        db_manager,
                        aggregate_type=aggregate_type,
                        aggregate_interval=aggregate_interval,
                        **option_dict)

                    # Get the type of plot ("bar', 'line', or 'vector')
                    plot_type = line_options.get('plot_type', 'line').lower()

                    if aggregate_type and plot_type != 'bar':
                        # If aggregating, put the point in the middle of the interval
                        start_vec_t = ValueTuple(
                            [x - aggregate_interval / 2.0 for x in start_vec_t[0]], # Value
                            start_vec_t[1],                                         # Unit
                            start_vec_t[2])                                         # Unit group
                        stop_vec_t = ValueTuple(
                            [x - aggregate_interval / 2.0 for x in stop_vec_t[0]],  # Velue
                            stop_vec_t[1],                                          # Unit
                            stop_vec_t[2])                                          # Unit group

                    # Convert the data to the requested units
                    new_data_vec_t = self.converter.convert(data_vec_t)

                    # Add a unit label. NB: all will get overwritten except the last. Get the label
                    # from the configuration dictionary.
                    unit_label = line_options.get(
                        'y_label', self.formatter.get_label_string(new_data_vec_t[1]))
                    # Strip off any leading and trailing whitespace so it's easy to center
                    plot.setUnitLabel(unit_label.strip())

                    # See if a line label has been explicitly requested:
                    label = line_options.get('label')
                    if label:
                        # Yes. Get the text translation
                        label = self.text_dict[label]
                    else:
                        # No explicit label. Look up a generic one.
                        # NB: generic_dict is a KeyDict which will substitute the key
                        # if the value is not in the dictionary.
                        label = self.generic_dict[var_type]

                    # See if a color has been explicitly requested.
                    color = line_options.get('color')
                    if color is not None: color = weeplot.utilities.tobgr(color)
                    fill_color = line_options.get('fill_color')
                    if fill_color is not None: fill_color = weeplot.utilities.tobgr(fill_color)

                    # Get the line width, if explicitly requested.
                    width = to_int(line_options.get('width'))

                    interval_vec = None
                    gap_fraction = None
                    vector_rotate = None

                    # Some plot types require special treatments:
                    if plot_type == 'vector':
                        vector_rotate_str = line_options.get('vector_rotate')
                        vector_rotate = -float(vector_rotate_str) \
                            if vector_rotate_str is not None else None
                    elif plot_type == 'bar':
                        interval_vec = [x[1] - x[0] for x in
                                        zip(start_vec_t.value, stop_vec_t.value)]
                    elif plot_type == 'line':
                        gap_fraction = to_float(line_options.get('line_gap_fraction'))
                        if gap_fraction is not None and not 0 < gap_fraction < 1:
                                log.error("Gap fraction %5.3f outside range 0 to 1. Ignored.",
                                          gap_fraction)
                                gap_fraction = None
                    else:
                        log.error("Unknown plot type '%s'. Ignored", plot_type)
                        continue

                    # Get the type of line (only 'solid' or 'none' for now)
                    line_type = line_options.get('line_type', 'solid')
                    if line_type.strip().lower() in ['', 'none']:
                        line_type = None

                    marker_type = line_options.get('marker_type')
                    marker_size = to_int(line_options.get('marker_size', 8))
                    
                    # Add the line to the emerging plot:
                    plot.addLine(weeplot.genplot.PlotLine(
                        stop_vec_t[0], new_data_vec_t[0],
                        label         = label,
                        color         = color,
                        fill_color    = fill_color,
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
                except IOError as e:
                    log.error("Unable to save to file '%s' %s:", img_file, e)
        t2 = time.time()

        if log_success:
            log.info("Generated %d images for report %s in %.2f seconds",
                     ngen,
                     self.skin_dict['REPORT_NAME'], t2 - t1)


def skipThisPlot(time_ts, aggregate_interval, img_file):
    """A plot can be skipped if it was generated recently and has not changed. This happens if the
    time since the plot was generated is less than the aggregation interval."""

    # Images without an aggregation interval have to be plotted every time. Also, the image
    # definitely has to be generated if it doesn't exist.
    if aggregate_interval is None or not os.path.exists(img_file):
        return False

    # If its a very old image, then it has to be regenerated
    if time_ts - os.stat(img_file).st_mtime >= aggregate_interval:
        return False

    # Finally, if we're on an aggregation boundary, regenerate.
    time_dt = datetime.datetime.fromtimestamp(time_ts)
    tdiff = time_dt -  time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return abs(tdiff.seconds % aggregate_interval) > 1
