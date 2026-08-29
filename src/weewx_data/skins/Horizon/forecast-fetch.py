#!/usr/bin/env python3
#    Copyright (c) 2026 Manuel Hilgert
#    Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#
"""Write the forecast file the Horizon skin reads.

The skin looks for 'forecast.json' beside its other data. If it is there, the
page uses it and nothing leaves the reader's browser; if it is not, the page
asks Open-Meteo itself, once per reader. This script is the other half of that
choice: run it on the station and the model is fetched once for everybody.

    forecast-fetch.py --lat 47.801 --lon 11.011 \\
                      --out /var/www/html/weewx/data/forecast.json

Hourly is often enough. From cron:

    7 * * * * /usr/share/weewx/skins/Horizon/forecast-fetch.py \\
              --lat 47.801 --lon 11.011 --out .../data/forecast.json

It writes through a temporary file in the same directory and renames it into
place, so a page fetching the file never catches it half written.

Open-Meteo is the source here because it needs no key and covers the world. The
format it is written in is the skin's, not Open-Meteo's -- see the docstring of
'to_horizon' below. Anything that can produce that shape will do: weewx-dwd for
Germany's MOSMIX, weewx-forecast for the American services, a script of your own
against whatever your country's weather service publishes.

Nothing here imports WeeWX. It is a plain script on purpose: it can run from
cron, from a systemd timer, or by hand, and it does not care whether WeeWX is
installed on the same machine as the web server.
"""

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.open-meteo.com/v1/forecast"

DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,"
         "precipitation_probability_max,wind_speed_10m_max")
HOURLY = "weather_code,temperature_2m,precipitation_probability"


def fetch(lat, lon, days, timeout):
    """Ask Open-Meteo, and return what it says.

    Args:
        lat (float): The station latitude, in degrees north.
        lon (float): Its longitude, in degrees east.
        days (int): How many days to ask for.
        timeout (int): How long to wait for an answer, in seconds.
    """
    query = urllib.parse.urlencode({
        'latitude': lat,
        'longitude': lon,
        'daily': DAILY,
        'hourly': HOURLY,
        'timezone': 'auto',
        'forecast_days': days,
    })
    request = urllib.request.Request(
        "%s?%s" % (API, query),
        headers={'User-Agent': 'weewx-horizon-forecast/1.0'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def to_horizon(said):
    """Open-Meteo's answer in the shape the skin reads.

    The format, in full:

        {"source": str,             where it came from, for the record
         "run":    str|null,        when the model ran, ISO 8601, if known
         "units":  {"temperature": str, "wind": str},
         "days":   [{"date": "YYYY-MM-DD", "code": int,
                     "high": float, "low": float,
                     "rain": int|null,     per cent
                     "wind": float|null}],
         "hours":  [{"time": "YYYY-MM-DDTHH:MM", "code": int,
                     "temperature": float, "rain": int|null}]}

    'code' is a WMO 4677 present-weather code. The skin knows that vocabulary
    and nothing else, so a source that speaks its own dialect has to translate
    on the way in rather than inventing a code of its own.

    'days' and 'hours' may be empty; the panel shows what it is given and hides
    itself when that is nothing.

    Args:
        said (dict[str, Any]): Open-Meteo's answer, as it came back.
    """
    daily = said.get('daily') or {}
    hourly = said.get('hourly') or {}
    units = said.get('daily_units') or {}

    def column(source, name, index):
        values = source.get(name) or []
        return values[index] if index < len(values) else None

    days = [{
        'date': when,
        'code': column(daily, 'weather_code', i),
        'high': column(daily, 'temperature_2m_max', i),
        'low': column(daily, 'temperature_2m_min', i),
        'rain': column(daily, 'precipitation_probability_max', i),
        'wind': column(daily, 'wind_speed_10m_max', i),
    } for i, when in enumerate(daily.get('time') or [])]

    hours = [{
        'time': when,
        'code': column(hourly, 'weather_code', i),
        'temperature': column(hourly, 'temperature_2m', i),
        'rain': column(hourly, 'precipitation_probability', i),
    } for i, when in enumerate(hourly.get('time') or [])]

    return {
        'source': 'open-meteo',
        # Open-Meteo does not say which run this is. A source that does should
        # put it here: the page shows it, and a forecast without a time on it
        # cannot be told from a stale one.
        'run': None,
        'units': {
            'temperature': units.get('temperature_2m_max', '°C'),
            'wind': units.get('wind_speed_10m_max', 'km/h'),
        },
        'days': days,
        'hours': hours,
    }


def write(payload, path):
    """Into place in one step, so a reader never sees half a file.

    Args:
        payload (dict[str, Any]): What to write.
        path (str): Where to write it.
    """
    folder = os.path.dirname(os.path.abspath(path)) or '.'
    handle, temporary = tempfile.mkstemp(dir=folder, suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as fd:
            json.dump(payload, fd, ensure_ascii=False)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    # mkstemp makes it readable by its owner alone, which a web server is not.
    os.chmod(path, 0o644)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--lat', type=float, required=True,
                        help="latitude, degrees north")
    parser.add_argument('--lon', type=float, required=True,
                        help="longitude, degrees east")
    parser.add_argument('--out', required=True,
                        help="where to write forecast.json")
    parser.add_argument('--days', type=int, default=7,
                        help="how many days ahead (default: 7)")
    parser.add_argument('--timeout', type=float, default=20.0,
                        help="seconds to wait for the API (default: 20)")
    args = parser.parse_args(argv)

    try:
        said = fetch(args.lat, args.lon, args.days, args.timeout)
    except (urllib.error.URLError, OSError, ValueError) as e:
        # An old forecast is better than none: leave whatever is there and say
        # why. From cron this reaches the log, and the page carries on with the
        # file it already has.
        print("forecast: %s" % e, file=sys.stderr)
        return 1

    payload = to_horizon(said)
    if not payload['days']:
        print("forecast: nothing usable in the answer", file=sys.stderr)
        return 1

    write(payload, args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
