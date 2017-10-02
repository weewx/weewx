#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#    Copyright (c) 2017-2019 Kevin Locke <kevin@kevinlocke.name>
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate JSON data files for plotly.js plots for up to an effective date.
Based on weewx.imagegenerator.ImageGenerator."""

from __future__ import with_statement

import cmath
from datetime import datetime
import errno
import itertools
import json
import locale
import math
import os.path
import syslog
import time

import weeplot.genplot
import weeplot.utilities
import weeutil.weeutil
import weewx.reportengine
import weewx.units
from weeutil.weeutil import to_bool, to_int, to_float
from weewx.units import ValueTuple

# =============================================================================
#                    Class PlotlyJSONGenerator
# =============================================================================

class PlotlyJSONGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the plotly.js JSON generator."""

    # Map weeWX marker type to most similar plotly marker type
    _plotly_marker_types = {
        'box': 'square-open',
        'circle': 'circle-open',
        'cross': 'cross',
        'x': 'x',
        }

    def run(self):
        self.setup()
        self.gen_report(self.gen_ts)

    def setup(self):
        """Initialize and configure this instance of PlotlyJSONGenerator"""
        try:
            d = self.skin_dict['Labels']['Generic']
        except KeyError:
            d = {}
        self.title_dict = weeutil.weeutil.KeyDict(d)
        self.report_dict = self.skin_dict['ImageGenerator']
        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)
        # ensure that the skin_dir is in the report_dict
        self.report_dict['skin_dir'] = os.path.join(
            self.config_dict['WEEWX_ROOT'],
            self.skin_dict['SKIN_ROOT'],
            self.skin_dict['skin'])

    def gen_report(self, gen_ts):
        """Generate plotly JSON files."""
        log_success = to_bool(self.report_dict.get('log_success', True))
        if log_success:
            run_start_ts = time.time()
            ngen = 0

        # Loop over each time span class (day, week, month, etc.):
        for timespan in self.report_dict.sections:
            timespan_dict = self.report_dict[timespan]

            # Now, loop over all plot names in this time span class:
            for plot_name in timespan_dict.sections:

                plot_options = timespan_dict[plot_name]
                # Accumulate all options from parent nodes:
                plot_options_acc = weeutil.weeutil.accumulateLeaves(plot_options)
                # Include line sections with accumulated options:
                for line_name in plot_options.sections:
                    plot_options_acc[line_name] = plot_options[line_name]

                # Generate the plot
                if self._gen_plot(plot_name, plot_options_acc, self.gen_ts):
                    ngen += 1

        if log_success:
            run_end_ts = time.time()
            syslog.syslog(
                syslog.LOG_INFO,
                "plotlygenerator: Generated %d images for %s in %.2f seconds" % (
                    ngen,
                    self.skin_dict['REPORT_NAME'],
                    run_end_ts - run_start_ts))


    def _gen_plot(self, plot_name, plot_options, plotgen_ts=None):
        """Generate plotly JSON file for given options and time, if outdated.

        The time scales will be chosen to include the given timestamp, with
        nice beginning and ending times.

        Args:
            plot_name (str): File basename of plot to generate.
            plot_options (dict): Options for the plot to generate.
            plotgen_ts (int, optional): Timestamp at which plots are to be
                generated.  This will also be used as the bottom label in the
                plots.  [optional. Default is to use the time of the last
                record in the database.]

        Returns:
            bool: True if a plot was generated, False otherwise.
        """

        if not plotgen_ts:
            binding = plot_options['data_binding']
            archive = self.db_binder.get_manager(binding)
            plotgen_ts = archive.lastGoodStamp()
            if not plotgen_ts:
                plotgen_ts = time.time()

        # Get the path that the file is going to be saved to:
        html_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                 plot_options['HTML_ROOT'])
        plot_path = os.path.join(html_root, plot_name + '.plotly.json')

        aggregate_interval = to_int(plot_options.get('aggregate_interval'))
        # Check whether this plot needs to be done at all:
        if skipThisPlot(plotgen_ts, aggregate_interval, plot_path):
            return False

        # skip image files that are fresh, but only if staleness is defined
        stale = to_int(plot_options.get('stale_age'))
        if stale is not None:
            t_now = time.time()
            try:
                last_mod = os.path.getmtime(plot_path)
                if t_now - last_mod < stale:
                    syslog.syslog(
                        syslog.LOG_DEBUG,
                        "plotlygenerator: Skip '%s': last_mod=%s age=%s stale=%s" % (
                            plot_path, last_mod, t_now - last_mod, stale))
                    return False
            except os.error:
                pass

        try:
            self._gen_plot_file(plot_path, plot_options, plotgen_ts)
        except IOError as exc:
            syslog.syslog(
                syslog.LOG_CRIT,
                "plotlygenerator: Unable to save to file '%s': %s" % (plot_path, exc))
            return False

        return True


    def _gen_plot_file(self, plot_path, plot_options, plotgen_ts):
        """Generate plotly JSON file for given options and time."""

        json_data = self._gen_plot_data(plot_options, plotgen_ts)

        try:
            json_file = open(plot_path, 'wb')
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                # Parent dir didn't exist.  Create it, then retry.
                os.makedirs(os.path.dirname(plot_path))
                json_file = open(plot_path, 'wb')
            else:
                # Unhandled open error
                raise

        with json_file:
            json.dump(
                json_data,
                json_file,
                # Use separators without spaces to reduce file size
                separators=(',', ':'))


    def _gen_plot_data(self, plot_options, plotgen_ts):
        """Generate plotly JSON data for given options and time."""

        # Create a new instance of a time plot to get option defaults
        plot = weeplot.genplot.TimePlot(plot_options)

        # Calculate a suitable min, max time for the requested time.
        time_length = int(plot_options.get('time_length', 86400))
        minstamp, maxstamp, timeinc = weeplot.utilities.scaletime(
            plotgen_ts - time_length,
            plotgen_ts)
        timerange = minstamp, maxstamp
        # Override the x interval if the user has given an explicit interval:
        timeinc_user = to_int(plot_options.get('x_interval'))
        if timeinc_user is not None:
            timeinc = timeinc_user

        # Set the y-scaling, using any user-supplied hints:
        miny, maxy, incy = weeutil.weeutil.convertToFloat(
            plot_options.get('yscale', ['None', 'None', 'None']))

        top_label_font_family = plot_options.get('top_label_font_family')

        # Get a suitable bottom label:
        bottom_label_format = plot_options.get('bottom_label_format', '%m/%d/%y %H:%M')
        bottom_label = time.strftime(
            bottom_label_format,
            time.localtime(plotgen_ts))

        padding = plot.padding / plot.anti_alias
        # plotly padding overlaps margins.
        # Add padding for consistency with ImageGenerator.
        lmargin = plot.lmargin / plot.anti_alias + padding
        rmargin = plot.rmargin / plot.anti_alias + padding
        bmargin = plot.bmargin / plot.anti_alias + padding
        tmargin = plot.tmargin / plot.anti_alias + padding

        plot_w = plot.image_width // plot.anti_alias - lmargin - rmargin
        plot_h = plot.image_height // plot.anti_alias - lmargin - rmargin
        plotsize = plot_w, plot_h

        last_vector_options = None
        last_vector_line_num = 0

        # Initialize variables used after loop
        line_options = None

        # Loop over each line to be added to the plot.
        data = []
        for line_num, line_name in enumerate(plot_options.sections):

            line_options = plot_options[line_name]
            # Accumulate options from parent nodes.
            line_options = weeutil.weeutil.accumulateLeaves(line_options)
            # accumulateLeaves does not preserve .name
            line_options.name = line_name

            data += self._gen_line_data(plot, line_options, line_num, timerange, plotsize)

            if line_options.get('plot_type') == 'vector':
                last_vector_line_num = line_num
                last_vector_options = line_options

        unit_label = None
        if line_options is not None:
            unit_label = self._get_y_label(line_options)

        # Offset (in px) from plot area to top bar
        tb_off = padding + float(plot.tmargin - plot.tbandht) / plot.anti_alias
        # Title y position in paper coordinates
        title_y = 1 + tb_off / plot_h

        x_label_format = plot.x_label_format
        if x_label_format is None:
            x_label_format = _get_time_format(minstamp, maxstamp)

        shapes = []
        annotations = []

        layout = {
            'height': plot.image_height / plot.anti_alias,
            'width': plot.image_width / plot.anti_alias,
            'showlegend': False,
            'legend': {
                'bgcolor': _bgr_to_css(plot.chart_background_color),
                'font': {
                    'family': top_label_font_family,
                    'size': plot.top_label_font_size / plot.anti_alias,
                    },
                'orientation': 'h',
                'x': 0.5,
                'xanchor': 'center',
                'y': title_y,
                'yanchor': 'bottom',
                },
            'paper_bgcolor': _bgr_to_css(plot.image_background_color),
            'plot_bgcolor': _bgr_to_css(plot.chart_background_color),
            'titlefont': {
                'family': top_label_font_family,
                'size': plot.top_label_font_size / plot.anti_alias,
                },
            'xaxis': {
                'range': [_time_to_iso(minstamp), _time_to_iso(maxstamp)],
                # Note: Linear doesn't change on zoom, use auto.
                #'tickmode': 'linear',
                #'tick0': _time_to_iso(minstamp),
                #'dtick': timeinc * 1000,
                'tickmode': 'auto',
                'nticks': plot.x_nticks,
                'tickfont': {
                    'family': plot_options.get('axis_label_font_family'),
                    'size': plot.axis_label_font_size / plot.anti_alias,
                    'color': _bgr_to_css(plot.axis_label_font_color),
                    },
                'tickformat': x_label_format,
                'title': bottom_label,
                'titlefont': {
                    'family': plot_options.get('bottom_label_font_family'),
                    'size': plot.bottom_label_font_size / plot.anti_alias,
                    'color': _bgr_to_css(plot.bottom_label_font_color),
                    },
                'gridcolor': _bgr_to_css(plot.chart_gridline_color),
                },
            'yaxis': {
                'tickmode': 'auto',
                'nticks': plot.y_nticks,
                'tickformat': plot.y_label_format,
                'tickfont': {
                    'family': plot_options.get('axis_label_font_family'),
                    'size': plot.axis_label_font_size / plot.anti_alias,
                    'color': _bgr_to_css(plot.axis_label_font_color),
                    },
                'title': unit_label,
                'titlefont': {
                    'family': plot_options.get('unit_label_font_family'),
                    'size': plot.unit_label_font_size / plot.anti_alias,
                    'color': _bgr_to_css(plot.unit_label_font_color),
                    },
                'gridcolor': _bgr_to_css(plot.chart_gridline_color),
                },
            'margin': {
                'l': lmargin,
                'r': rmargin,
                'b': bmargin,
                't': tmargin,
                'pad': padding,
                },
            'shapes': shapes,
            'annotations': annotations,
            }

        if miny is not None and maxy is not None:
            layout['yaxis']['range'] = [miny, maxy]

        if plot.image_background_color != plot.chart_background_color:
            # Add top bar with chart bg color to match ImageGenerator
            shapes.append({
                'type': 'rect',
                'layer': 'below',
                'fillcolor': _bgr_to_css(plot.chart_background_color),
                'line': {
                    'width': 0
                },
                'xref': 'paper',
                'x0': -1,
                'x1': 2,
                'yref': 'paper',
                'y0': title_y,
                'y1': 2,
                })

        if plot.show_daynight:
            shapes += self._gen_daynight(plot, timerange)

        # Draw compass rose if there is a vector line
        # Note: Must be after daynight to render above daynight
        if last_vector_options is not None:
            # Compass rose color and rotation affected by last vector line
            rose_rotate = -to_float(last_vector_options.get('vector_rotate', 0))
            rose_color = plot.rose_color
            if rose_color is None:
                rose_color = last_vector_options.get('color')
                if rose_color is not None:
                    rose_color = weeplot.utilities.tobgr(rose_color)
                else:
                    rose_color = plot.chart_line_colors[
                        last_vector_line_num % len(plot.chart_line_colors)]
            # genplot hard-codes rose_position 5 from left plot edge
            # add one from bottom edge to separate 0/180 rose from edge
            rose_offset = 5, 1

            rose_shapes = _make_rose_shapes(
                plot.rose_height,
                plot.rose_diameter,
                # genplot hard-codes barb_width/barb_height of 3
                3,
                rose_color)
            if rose_rotate:
                rose_shapes = _rotate_shapes(rose_shapes, rose_rotate)
            rose_shapes = _translate_shapes(
                rose_shapes,
                plot.rose_width / 2.0 + rose_offset[0],
                plot.rose_height / 2.0 + rose_offset[1])
            rose_shapes = _scale_shapes(rose_shapes, 1.0 / plot_w, 1.0 / plot_h)
            shapes += rose_shapes

            annotations.append({
                'text': plot.rose_label,
                # Size of text box in pixels.
                # Text is aligned in center/middle of box by default.
                'width': plot.rose_width,
                'height': plot.rose_height,
                'borderpad': 0,
                'borderwidth': 0,
                'font': {
                    'family': plot_options.get('rose_label_font_family'),
                    'size': plot.rose_label_font_size,
                    'color': _bgr_to_css(plot.rose_label_font_color),
                    },
                'showarrow': False,
                'xref': 'paper',
                'yref': 'paper',
                'x': float(rose_offset[0]) / plot_w,
                'y': float(rose_offset[1]) / plot_h,
                })

        # Add legend-as-title annotations
        titles = [
            {
                'text': line_data['name'],
                'font': {
                    'family': top_label_font_family,
                    'size': plot.top_label_font_size / plot.anti_alias,
                    'color':
                        line_data['line']['color'] if 'line' in line_data
                        else line_data['marker']['line']['color'],
                    },
                'showarrow': False,
                'xref': 'paper',
                'yref': 'paper',
                'x': 0.5,
                'y': title_y,
                'xanchor': 'center',
                'yanchor': 'bottom',
                'borderpad': 0,
                'borderwidth': 0,
                # Default SVG <text> height is larger than genplot sizing
                # Constrain height to get same y positioning of text
                'height': plot.tbandht / plot.anti_alias,
            }
            for line_data in data if line_data.get('showlegend', True)]
        # Calculate the x bounds of the plot in paper coordinates
        paper_xmin = float(-lmargin) / plot_w
        paper_xmax = 1.0 + float(rmargin) / plot_w
        paper_xrange = paper_xmax - paper_xmin
        # Space the center of the titles evenly across the paper xrange
        for i, title in enumerate(titles):
            title['x'] = paper_xmin + paper_xrange * (i + 1.0) / (len(titles) + 1.0)

        annotations += titles

        # Send list of fonts to facilitate pre-loading, with FontFace schema:
        # https://drafts.csswg.org/css-font-loading/#fontface
        font_families = set((
            top_label_font_family,
            plot_options.get('axis_label_font_family'),
            plot_options.get('bottom_label_font_family'),
            plot_options.get('unit_label_font_family'),
            ))
        if last_vector_options is not None:
            font_families.add(plot_options.get('rose_label_font_family'))
        font_families.remove(None)
        fonts = [{'family': family} for family in font_families]

        return {'data': data, 'fonts': fonts, 'layout': layout}


    def _gen_line_data(self, plot, line_options, line_num, timerange, plotsize):
        # See what SQL variable type to use for this line. By
        # default, use the section name.
        var_type = line_options.get('data_type', line_options.name)

        # Look for aggregation type:
        aggregate_type = line_options.get('aggregate_type')
        if aggregate_type in (None, '', 'None', 'none'):
            # No aggregation specified.
            aggregate_type = aggregate_interval = None
        else:
            try:
                # Aggregation specified. Get the interval.
                aggregate_interval = line_options.as_int('aggregate_interval')
            except KeyError:
                syslog.syslog(
                    syslog.LOG_ERR,
                    "plotlygenerator: aggregate interval required "
                    "for aggregate type %s" % aggregate_type)
                syslog.syslog(
                    syslog.LOG_ERR,
                    "plotlygenerator: line type %s skipped" % var_type)
                return ()

        # Now its time to find and hit the database:
        binding = line_options['data_binding']
        archive = self.db_binder.get_manager(binding)
        start_vec_t, stop_vec_t, data_vec_t = archive.getSqlVectors(
            timerange,
            var_type,
            aggregate_type=aggregate_type,
            aggregate_interval=aggregate_interval)

        if weewx.debug:
            assert len(start_vec_t) == len(stop_vec_t) == len(data_vec_t)

        # Get the type of plot ('bar', 'line', or 'vector')
        plot_type = line_options.get('plot_type', 'line')

        if aggregate_type and \
            aggregate_type.lower() in ('avg', 'max', 'min') and \
            plot_type != 'bar':
            # Put the point in the middle of the aggregate_interval
            start_vec_t = ValueTuple(
                [x - aggregate_interval / 2.0 for x in start_vec_t[0]],
                start_vec_t[1],
                start_vec_t[2])
            stop_vec_t = ValueTuple(
                [x - aggregate_interval / 2.0 for x in stop_vec_t[0]],
                stop_vec_t[1],
                stop_vec_t[2])

        # Do any necessary unit conversions:
        new_start_vec_t = self.converter.convert(start_vec_t)
        new_stop_vec_t = self.converter.convert(stop_vec_t)
        new_data_vec_t = self.converter.convert(data_vec_t)

        # Remove missing data, for the following reasons:
        # - Avoids checks during conversion/scaling.
        # - Reduces JSON file size.
        # - Does not cause line breaks in line plots.
        new_data_values = new_data_vec_t[0]
        if None in new_data_values:
            new_start_vec_t = ValueTuple(
                [v for i, v in enumerate(new_start_vec_t[0])
                 if new_data_values[i] is not None],
                new_start_vec_t[1],
                new_start_vec_t[2]
                )
            new_stop_vec_t = ValueTuple(
                [v for i, v in enumerate(new_stop_vec_t[0])
                 if new_data_values[i] is not None],
                new_stop_vec_t[1],
                new_stop_vec_t[2]
                )
            new_data_vec_t = ValueTuple(
                [v for v in new_data_values if v is not None],
                new_data_vec_t[1],
                new_data_vec_t[2]
                )

        # See if a line label has been explicitly requested:
        label = line_options.get('label')
        if not label:
            # No explicit label. Look up a generic one. NB: title_dict is a KeyDict which
            # will substitute the key if the value is not in the dictionary.
            label = self.title_dict[var_type]

        # See if a color has been explicitly requested.
        color = line_options.get('color')
        if color is not None:
            color = weeplot.utilities.tobgr(color)
        else:
            color = plot.chart_line_colors[
                line_num % len(plot.chart_line_colors)]

        fill_color = line_options.get('fill_color')
        if fill_color is not None:
            fill_color = weeplot.utilities.tobgr(fill_color)
        else:
            fill_color = plot.chart_fill_colors[
                line_num % len(plot.chart_fill_colors)]

        # Get the line width, if explicitly requested.
        width = to_int(line_options.get('width'))
        if width is None:
            width = plot.chart_line_widths[
                line_num % len(plot.chart_line_widths)]

        # Store x and y values in vars for possible modification
        x = new_stop_vec_t[0]
        y = new_data_vec_t[0]

        interval_vec = None

        # Some plot types require special treatments:
        if plot_type == 'vector':
            vector_rotate = -to_float(line_options.get('vector_rotate', 0))
            if vector_rotate:
                vector_rotate_rad = math.radians(vector_rotate)
                vector_rotate_mul = complex(math.cos(vector_rotate_rad),
                                            math.sin(vector_rotate_rad))
                rotated = [d * vector_rotate_mul if d is not None else None
                           for d in new_data_vec_t[0]]
            else:
                rotated = new_data_vec_t[0]
            y = [d.imag for d in rotated]
            z = [d.real for d in rotated]
        else:
            gap_fraction = None
            if plot_type == 'bar':
                interval_vec = [
                    x1 - x0
                    for x0, x1
                    in zip(new_start_vec_t[0], new_stop_vec_t[0])]
            elif plot_type == 'line':
                gap_fraction = to_float(line_options.get('line_gap_fraction'))
            if gap_fraction is not None:
                if not 0 < gap_fraction < 1:
                    syslog.syslog(
                        syslog.LOG_ERR,
                        "plotlygenerator: Gap fraction %5.3f outside range 0 "
                        "to 1. Ignored." % gap_fraction)
                    gap_fraction = None
            if gap_fraction is not None:
                maxdx = (timerange[1] - timerange[0]) * gap_fraction
                x, y = _add_gaps(x, y, maxdx)

        # Get the type of line (only 'solid' or 'none' for now)
        line_type = line_options.get('line_type', 'solid')
        if line_type.strip().lower() in ['', 'none']:
            line_type = None

        marker_type = line_options.get('marker_type')
        if marker_type is not None:
            marker_type = marker_type.lower()
            if marker_type == 'none':
                marker_type = None
        marker_size = to_int(line_options.get('marker_size', 8))

        if line_type is not None:
            if marker_type is not None:
                line_mode = 'lines+markers'
            else:
                line_mode = 'lines'
        elif marker_type is not None:
            line_mode = 'markers'
        else:
            line_mode = 'none'

        # Add the line to the emerging plot:
        line_data = {
            'name': label,
            'x': [_time_to_iso(t) for t in x],
            'y': y,
        }
        if not y:
            # If there are no data points, Plotly.js ignores xaxis.range and
            # shows values from -100% to 600%.  Add data point to avoid this.
            # See https://github.com/plotly/plotly.js/issues/3487
            line_data['x'] = [_time_to_iso(timerange[0])]
            line_data['y'] = [None]
        if plot_type == 'line':
            if marker_type:
                symbol = PlotlyJSONGenerator._plotly_marker_types[marker_type]
            else:
                symbol = None
            line_data.update({
                'type': 'scatter',
                'mode': line_mode,
                'connectgaps': False,
                'fillcolor': _bgr_to_css(fill_color),
                'line': {
                    'color': _bgr_to_css(color),
                    'dash': line_type,
                    'width': width,
                    },
                'marker': {
                    'symbol': symbol,
                    'size': marker_size,
                    },
                })
            return line_data,
        elif plot_type == 'bar':
            # Uniform widths can be a single value to reduce space
            # x1000 since plotly.js works in ms not seconds
            if _is_uniform(interval_vec):
                bar_width = interval_vec[0] * 1000
            else:
                bar_width = [i * 1000 for i in interval_vec]
            line_data.update({
                'type': 'bar',
                'width': bar_width,
                'marker': {
                    'color': _bgr_to_css(fill_color),
                    'line': {
                        'color': _bgr_to_css(color),
                        'width': width,
                        },
                    },
                })
            return line_data,
        elif plot_type == 'vector':
            line_data.update({
                'type': 'scatter',
                # Note: genplot doesn't draw markers for vector.
                'mode': 'lines',
                # Hide x/y hoverinfo since values are misleading
                'hoverinfo': 'text',
                })
            if line_type is not None:
                line_data['line'] = {
                    'color': _bgr_to_css(color),
                    'dash': line_type,
                    'width': width,
                    }
            # If there are no data points, return line data for use in legend
            if not y:
                return line_data,
            # Hide legend entries for lines by default un-hide last line only
            line_data['showlegend'] = False
            xscale = float(timerange[1] - timerange[0]) / plotsize[0]
            miny, maxy, incy = weeutil.weeutil.convertToFloat(
                line_options.get('yscale', ['None', 'None', 'None']))
            if miny is not None and maxy is not None:
                yrange = maxy - miny
            else:
                yrange = max(y) - min(y)
            yscale = float(yrange) / plotsize[1]
            xyscale = xscale / yscale
            polar = [cmath.polar(d) for d in new_data_vec_t[0]]
            x_label_format = plot.x_label_format
            if x_label_format is None:
                x_label_format = _get_time_format(*timerange)
            unit_label = self._get_y_label(line_options)
            lines = []
            for x0, y0, z0, (r, phi) in zip(x, y, z, polar):
                line = line_data.copy()
                line['x'] = [
                    _time_to_iso(x0),
                    _time_to_iso(x0 + z0 * xyscale)
                    ]
                line['y'] = [0, y0]
                x0_str = time.strftime(x_label_format, time.localtime(x0))
                # Inverse of complex conversion in getSqlVectors
                deg = (90 - math.degrees(phi)) % 360
                # Use 360 for non-zero North wind by convention
                deg = 360 if r > 0.001 and deg < 1 else deg
                line['text'] = locale.format_string(
                    u"%s: %.03f %s %d\u00B0",
                    (x0_str, r, unit_label, deg))
                lines.append(line)
            # Show one line in legend
            del lines[-1]['showlegend']
            return lines
        else:
            raise AssertionError("Unrecognized plot type '%s'" % plot_type)


    def _gen_daynight(self, plot, timerange):
        """Generate background shapes for day/night display"""
        daynight_day_color = _bgr_to_css(plot.daynight_day_color)
        daynight_night_color = _bgr_to_css(plot.daynight_night_color)
        daynight_edge_color = _bgr_to_css(plot.daynight_edge_color)

        first, transitions = weeutil.weeutil.getDayNightTransitions(
            timerange[0],
            timerange[1],
            self.stn_info.latitude_f,
            self.stn_info.longitude_f)
        transitions.insert(0, timerange[0])
        transitions.append(timerange[1])
        transitions = [_time_to_iso(t) for t in transitions]
        is_days = itertools.cycle((first == 'day', first != 'day'))
        # Note: daynight edge line must be separate shape due to
        # top/bottom of rect.  Hide rect line.
        # FIXME: Plotly.js doesn't support gradient for daynight_gradient
        daynight_line = {'width': 0}
        daynight_shapes = [
            {
                'type': 'rect',
                'layer': 'below',
                'fillcolor':
                    daynight_day_color if is_day else daynight_night_color,
                'line': daynight_line,
                'xref': 'x',
                'x0': x0,
                'x1': x1,
                'yref': 'paper',
                'y0': 0,
                'y1': 1,
            }
            for is_day, x0, x1
            in zip(is_days, transitions, transitions[1:])]

        if (daynight_edge_color != daynight_day_color and
                daynight_edge_color != daynight_night_color):
            # Note: riseset must be after daynight to draw above.
            riseset_line = {'color': daynight_edge_color}
            daynight_shapes += (
                {
                    'type': 'line',
                    'layer': 'below',
                    'line': riseset_line,
                    'xref': 'x',
                    'x0': x,
                    'x1': x,
                    'yref': 'paper',
                    'y0': 0,
                    'y1': 1,
                }
                for x in transitions[1:-1])

        return daynight_shapes


    def _get_y_label(self, line_options):
        """Gets the y-axis label for a line with given options"""
        y_label = line_options.get('y_label')
        if y_label is None:
            var_type = line_options.get('data_type', line_options.name)
            y_label = weewx.units.get_label_string(
                self.formatter,
                self.converter,
                var_type)
        return y_label.strip()


def _add_gaps(x, y, maxdx):
    """Creates lists of x and y values with additional None-valued points to
    create gaps for x steps larger than maxdx.

    More precisely: For consecutive points (x0, y0) and (x1, y1), adds
    (avg(x0, x1), None) if y0 and y1 are not None and x1 - x0 > maxdx."""
    gx = []
    gy = []
    x0 = None
    for x1, y1 in zip(x, y):
        if x0 is not None and y1 is not None:
            dx = x1 - x0
            if dx > maxdx:
                gx.append(x1 - dx / 2)
                gy.append(None)
        gx.append(x1)
        gy.append(y1)
        x0 = None if y1 is None else x1
    return gx, gy


def _bgr_to_css(bgr):
    """Gets a CSS color for a given little-endian integer color value."""
    blue = (bgr & 0xFF0000) >> 16
    green = (bgr & 0x00FF00) >> 8
    red = (bgr & 0x0000FF)
    return "#%02x%02x%02x" % (red, green, blue)


def _get_time_format(minstamp, maxstamp):
    """Gets a locale format string for time values in a given range."""
    # FIXME: Duplicated with TimePlot._calcXLabelFormat
    delta = maxstamp - minstamp
    if delta > 30 * 24 * 3600:
        return u"%x"
    if delta > 24 * 3600:
        return u"%x %X"
    return u"%X"


def _is_uniform(iterable):
    """Tests if all values in an iterable are equal."""
    iterator = iter(iterable)
    first = iterator.next()
    for val in iterator:
        if val != first:
            return False
    return True


def _make_rose_shapes(length, diameter, barb_size, color):
    """Creates plotly shapes for a compass rose centered at the origin pointing
    along the positive y axis."""
    line = {
        'color': _bgr_to_css(color),
        'width': 1
        }
    half_diam = diameter / 2.0
    half_length = length / 2.0
    shaft = {
        'type': 'line',
        'xref': 'paper',
        'yref': 'paper',
        'x0': 0,
        'y0': -half_length,
        'x1': 0,
        'y1': half_length,
        'line': line,
        }
    barb1 = {
        'type': 'line',
        'xref': 'paper',
        'yref': 'paper',
        'x0': -barb_size,
        'y0': half_length - barb_size,
        'x1': 0,
        'y1': half_length,
        'line': line,
        }
    barb2 = {
        'type': 'line',
        'xref': 'paper',
        'yref': 'paper',
        'x0': barb_size,
        'y0': half_length - barb_size,
        'x1': 0,
        'y1': half_length,
        'line': line,
        }
    circle = {
        'type': 'circle',
        'xref': 'paper',
        'yref': 'paper',
        'x0': -half_diam,
        'y0': -half_diam,
        'x1': half_diam,
        'y1': half_diam,
        'line': line,
        }

    return shaft, barb1, barb2, circle


def _rotate_shapes(shapes, rotation):
    """Rotate shapes around the origin by a given angle in degrees."""
    if rotation:
        rotation = math.radians(rotation)
        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        for shape in shapes:
            for xname, yname in ('x0', 'y0'), ('x1', 'y1'):
                x = shape[xname]
                y = shape[yname]
                shape[xname] = x * cos_r - y * sin_r
                shape[yname] = x * sin_r + y * cos_r
    return shapes


def _scale_shapes(shapes, sx, sy):
    """Scale shapes by a given x and y scale factor."""
    if sx != 1 or sy != 1:
        for shape in shapes:
            for xname, yname in ('x0', 'y0'), ('x1', 'y1'):
                shape[xname] *= sx
                shape[yname] *= sy
    return shapes


def _translate_shapes(shapes, dx, dy):
    """Translate (move) shapes by a given x and y distance."""
    if dx or dy:
        for shape in shapes:
            for xname, yname in ('x0', 'y0'), ('x1', 'y1'):
                shape[xname] += dx
                shape[yname] += dy

    return shapes


def _time_to_iso(time_ts):
    """Converts a timestamp (seconds since epoch) to the RFC 3339 profile of
    the ISO 8601 format in the local timezone."""
    local_dt = datetime.fromtimestamp(time_ts)
    utc_dt = datetime.utcfromtimestamp(time_ts)
    offset_sec = (local_dt - utc_dt).total_seconds()
    (offset_hr, offset_min) = divmod(offset_sec // 60, 60)
    return local_dt.isoformat() + ('%+03d:%02d' % (offset_hr, offset_min))


def skipThisPlot(time_ts, aggregate_interval, plot_path):
    """A plot can be skipped if it was generated recently and has not changed.
    This happens if the time since the plot was generated is less than the
    aggregation interval."""

    # JSON without an aggregation interval have to be plotted every time.
    if aggregate_interval is None:
        return False

    try:
        plot_stat = os.stat(plot_path)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            # The file definitely has to be generated if it doesn't exist.
            return False
        raise

    # If its a very old file, then it has to be regenerated
    if time_ts - plot_stat.st_mtime >= aggregate_interval:
        return False

    # Finally, if we're on an aggregation boundary, regenerate.
    time_dt = datetime.fromtimestamp(time_ts)
    tdiff = time_dt -  time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return abs(tdiff.seconds % aggregate_interval) > 1
