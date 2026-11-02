#!/usr/bin/env python3
#    Copyright (c) 2026 Manuel Hilgert
#    Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#
"""Write the forecast file the Horizon skin reads.

The Horizon skin reads the file data/forecast.json under the HTML_ROOT of its
report. Where the file exists, no reader's browser asks a third party for the
forecast. Where the file does not exist, each reader's browser asks Open-Meteo,
unless browser_fetch is false. This script asks Open-Meteo once, and writes the
file for every reader:

    python3 forecast-fetch.py --lat 47.801 --lon 11.011 \\
        --out /var/www/html/weewx/horizon/data/forecast.json

Once an hour is often enough, because the browser keeps a forecast for an hour.
The following crontab line runs the script at seven minutes past every hour.
Replace '...' with the options shown above:

    7 * * * * python3 /etc/weewx/skins/Horizon/forecast-fetch.py ...

The script uses Open-Meteo because Open-Meteo needs no key and covers the whole
world. The file is in the skin's own format, not in Open-Meteo's, and
to_horizon() documents that format. Any program that writes the same format can
take the place of this script.

The script imports nothing from WeeWX, so that it also runs on a machine without
WeeWX, e.g., the web server that serves the pages.
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

# The fields to_horizon() reads. forecast.js asks Open-Meteo for the same fields.
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,"
         "precipitation_probability_max,wind_speed_10m_max")
HOURLY = "weather_code,temperature_2m,precipitation_probability"


def fetch(lat, lon, days, timeout):
    """Ask Open-Meteo for a forecast.

    Args:
        lat (float): The station latitude, in degrees north.
        lon (float): The station longitude, in degrees east.
        days (int): How many days to ask for.
        timeout (float): How long to wait for the answer, in seconds.

    Returns:
        dict: Open-Meteo's answer, decoded from JSON.

    Raises:
        OSError: If the request fails or times out. urllib.error.URLError is an
            OSError.
        ValueError: If the answer is not JSON.
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
    """Convert Open-Meteo's answer into the format of forecast.json.

    forecast.js reads this format, and fromOpenMeteo() in forecast.js converts an
    answer from Open-Meteo into the same format. The format, in full:

        {"source": str,             the name of the source, for information
         "run":    str|null,        when the model ran, ISO 8601, if known
         "units":  {"temperature": str, "wind": str},
         "days":   [{"date": "YYYY-MM-DD", "code": int,
                     "high": float, "low": float,
                     "rain": int|null,     chance of rain, in per cent
                     "wind": float|null}],
         "hours":  [{"time": "YYYY-MM-DDTHH:MM", "code": int,
                     "temperature": float, "rain": int|null}]}

    Dates and times are the station's local time, without a time zone.
    Temperatures are in degrees Celsius. 'wind' is the highest wind speed of the
    day, in km/h. 'units' names both units, but the skin does not read 'units'.
    The page shows 'run', so that a reader can tell a stale forecast from a
    current one.

    'code' is a WMO 4677 present-weather code. The skin has icons and texts for
    these codes only, so a source that uses other codes must convert them.

    'hours' may be empty. Where 'days' is empty, the forecast panel stays hidden.

    Args:
        said (dict): Open-Meteo's answer, as fetch() returns it.

    Returns:
        dict: The forecast, in the format above.
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
        # Open-Meteo does not say when its model ran.
        'run': None,
        'units': {
            'temperature': units.get('temperature_2m_max', '°C'),
            'wind': units.get('wind_speed_10m_max', 'km/h'),
        },
        'days': days,
        'hours': hours,
    }


def write(payload, path):
    """Write payload to path as JSON, replacing the file in one step.

    A browser that fetches the file at the same moment gets the previous file or
    the new one, never a partly written one.

    Args:
        payload (dict): The forecast, as to_horizon() returns it.
        path (str): The file to write.
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
    # mkstemp() creates the file readable by its owner only, and the web server
    # usually runs as another user.
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
        # A file written before stays in place, because an old forecast is better
        # than none.
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
