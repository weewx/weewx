#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Render the current conditions as an image.

WeeWX has always been able to draw a time series. It has never been able to draw the
*numbers* -- and a picture of the current readings is what people actually paste into a
forum post, a signature or a chat window. A screenshot goes stale the moment it is taken;
a file at a fixed URL stays current on its own.

The output is one PNG, redrawn each report cycle:

    [SummaryImageGenerator]
        enable = true
        filename = current.png
        observations = outTemp, windSpeed, rain, barometer

Everything else -- fonts, colours, sizes -- has a default and can be overridden. Labels,
units and formatting come from the skin, so the image says the same thing in the same
language as the page beside it.
"""

import logging
import os
import time

from PIL import Image, ImageDraw, ImageFont

import weeutil.logger
import weeutil.weeutil
import weewx.reportengine
import weewx.tags
import weewx.units
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_bool, to_int, to_float

log = logging.getLogger(__name__)

DEFAULTS = {
    'filename': 'current.png',
    'width': 900,
    'columns': 2,
    'scale': 2,                      # render at 2x, then downsample
    'background_color': '#ffffff',
    'title_color': '#16222e',
    'label_color': '#8397a7',
    'value_color': '#16222e',
    'sub_color': '#55666f',
    'rule_color': '#dbe4ec',
    'title_font_size': 21,
    'label_font_size': 11,
    'value_font_size': 34,
    'sub_font_size': 12,
    'stamp_font_size': 12,
    'padding': 26,
    'title_font_path': 'font/OpenSans-Bold.ttf',
    'value_font_path': 'font/OpenSans-Bold.ttf',
    'label_font_path': 'font/OpenSans-Regular.ttf',
}


def _as_list(option):
    """Coerce an option to a list of names.

    ConfigObj already splits "a, b, c" into a list, but the option may also arrive as a
    plain string -- from a hand-built dictionary, or a single-item value.
    """
    if isinstance(option, str):
        return [x.strip() for x in option.split(',') if x.strip()]
    return [str(x).strip() for x in weeutil.weeutil.option_as_list(option) if str(x).strip()]


def _text(draw, xy, string, font, fill):
    """Draw a string, in as much of it as the font can encode.

    PIL's own bitmap font encodes to latin-1 and raises on anything else. A station
    called Ζάκυνθος should cost its accents, not the whole picture. Pillow 10.1 and
    later hand back a FreeType font instead, which draws everything.
    """
    if not isinstance(font, ImageFont.FreeTypeFont):
        string = string.encode('latin-1', 'replace').decode('latin-1')
    draw.text(xy, string, font=font, fill=fill)


class SummaryImageGenerator(weewx.reportengine.ReportGenerator):
    """Draw the current readings into a single, linkable PNG."""

    def run(self):
        gen_dict = self.skin_dict.get('SummaryImageGenerator')
        if gen_dict is None or not to_bool(gen_dict.get('enable', False)):
            return

        t1 = time.time()
        opts = dict(DEFAULTS)
        opts.update(accumulateLeaves(gen_dict))

        observations = _as_list(
            gen_dict.get('observations', ['outTemp', 'windSpeed', 'rain', 'barometer']))

        try:
            payload = self._collect(observations)
        except Exception as e:
            log.error("Could not gather current conditions: %s", e)
            return
        if not payload:
            log.debug("Nothing to draw: no observation has data.")
            return

        try:
            image = self._draw(payload, opts)
        except Exception as e:
            log.error("Could not render summary image: %s", e)
            return

        html_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                 search_up(self.skin_dict, 'HTML_ROOT', 'public_html'))
        path = os.path.join(html_root, opts['filename'])
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            image.save(path)
        except OSError as e:
            log.error("Unable to save '%s': %s", path, e)
            return

        if to_bool(search_up(gen_dict, 'log_success', True)):
            log.info("Generated summary image for report %s in %.2f seconds",
                     self.skin_dict['REPORT_NAME'], time.time() - t1)

    # ------------------------------------------------------------------ data

    def _collect(self, observations):
        """Read the current values through the same tags a template would use."""
        formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        converter = weewx.units.Converter.fromSkinDict(self.skin_dict)
        labels = self.skin_dict.get('Labels', {}).get('Generic', {})

        binding = search_up(self.skin_dict, 'data_binding', 'wx_binding')
        stop_ts = self.gen_ts or self.db_binder.get_manager(binding).lastGoodStamp()
        if not stop_ts:
            return None

        # The same binders a template gets, so labels, units and formatting match the
        # page this image sits next to. $current comes from a RecordBinder, the daily
        # min/max from a TimeBinder.
        db_lookup = self.db_binder.bind_default(binding)

        current = weewx.tags.RecordBinder(db_lookup, stop_ts,
                                          formatter, converter,
                                          record=self.record).current()

        day = weewx.tags.TimeBinder(
            db_lookup,
            stop_ts,
            formatter=formatter,
            converter=converter,
            week_start=self.stn_info.week_start,
            rain_year_start=self.stn_info.rain_year_start,
            lat=self.stn_info.latitude_f,
            lon=self.stn_info.longitude_f,
            skin_dict=self.skin_dict).day()

        cards = []
        for obs in observations:
            # A station that lacks a type must cost that one reading, not the image.
            # weewx raises several different things for an unknown type depending on
            # where it is asked, so catch broadly and move on.
            try:
                value = getattr(current, obs)
                if value.raw is None:
                    continue
            except Exception:
                log.debug("No current value for '%s'. Skipped.", obs)
                continue

            sub = ''
            try:
                if obs in ('rain', 'ET', 'lightning_strike_count'):
                    value = getattr(day, obs).sum
                else:
                    lo = getattr(day, obs).min
                    hi = getattr(day, obs).max
                    if lo.raw is not None and hi.raw is not None:
                        sub = '%s / %s' % (lo.format(add_label=False), hi.format())
            except Exception:
                pass

            cards.append({
                'label': labels.get(obs, obs),
                'value': str(value),
                'sub': sub,
            })

        if not cards:
            return None

        return {
            'location': self.stn_info.location,
            'stamp': str(current.dateTime),
            'cards': cards,
        }

    # --------------------------------------------------------------- drawing

    def _font(self, opts, key, size, scale):
        """Load a font from the skin, falling back to PIL's own if it is missing."""
        path = opts.get(key)
        if path:
            candidate = os.path.join(self.config_dict['WEEWX_ROOT'],
                                     self.skin_dict['SKIN_ROOT'],
                                     self.skin_dict['skin'],
                                     path)
            try:
                return ImageFont.truetype(candidate, int(size * scale))
            except (OSError, ValueError):
                log.debug("Font '%s' unavailable; using the default.", candidate)
        try:
            # Pillow 10.1 and later size their default font, and it draws anything.
            return ImageFont.load_default(int(size * scale))
        except TypeError:
            # Older ones hand back a bitmap font: one size, latin-1 only.
            return ImageFont.load_default()

    def _draw(self, payload, opts):
        scale = max(1, to_int(opts['scale']))
        width = to_int(opts['width']) * scale
        pad = to_int(opts['padding']) * scale
        columns = max(1, to_int(opts['columns']))

        f_title = self._font(opts, 'title_font_path', to_float(opts['title_font_size']), scale)
        f_label = self._font(opts, 'label_font_path', to_float(opts['label_font_size']), scale)
        f_value = self._font(opts, 'value_font_path', to_float(opts['value_font_size']), scale)
        f_sub = self._font(opts, 'label_font_path', to_float(opts['sub_font_size']), scale)
        f_stamp = self._font(opts, 'label_font_path', to_float(opts['stamp_font_size']), scale)

        cards = payload['cards']
        rows = (len(cards) + columns - 1) // columns

        line_h = int(to_float(opts['title_font_size']) * scale * 1.35)
        stamp_h = int(to_float(opts['stamp_font_size']) * scale * 1.6)

        # Height of one reading, plus a gap so rows do not run into each other.
        label_h = int(to_float(opts['label_font_size']) * 1.7 * scale)
        value_h = int(to_float(opts['value_font_size']) * 1.3 * scale)
        sub_h = int(to_float(opts['sub_font_size']) * 1.5 * scale)
        gap = int(pad * 0.75)
        card_h = label_h + value_h + sub_h + gap

        height = pad + line_h + stamp_h + int(pad * 0.7) + rows * card_h - gap + pad

        image = Image.new('RGB', (width, height), opts['background_color'])
        draw = ImageDraw.Draw(image)

        y = pad
        _text(draw, (pad, y), payload['location'], f_title, opts['title_color'])
        y += line_h
        _text(draw, (pad, y), payload['stamp'], f_stamp, opts['label_color'])
        y += stamp_h

        draw.line([(pad, y), (width - pad, y)], fill=opts['rule_color'], width=scale)
        y += int(pad * 0.7)

        col_w = (width - 2 * pad) // columns
        for index, card in enumerate(cards):
            cx = pad + (index % columns) * col_w
            cy = y + (index // columns) * card_h

            _text(draw, (cx, cy), card['label'].upper(), f_label, opts['label_color'])
            cy += label_h

            _text(draw, (cx, cy), card['value'], f_value, opts['value_color'])
            cy += value_h

            if card['sub']:
                _text(draw, (cx, cy), card['sub'], f_sub, opts['sub_color'])

        if scale > 1:
            image = image.resize((width // scale, height // scale), Image.LANCZOS)
        return image
