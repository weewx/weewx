# JSON data files

The JSON generator (`weewx.jsongenerator.JSONGenerator`) creates JSON time
series and metadata designed for browser-based charting and interactive
dashboards, such as the *Horizon* skin. This section documents the format used
by the files.

All files are written to `<HTML_ROOT>/<json_dest_dir>`, where `<json_dest_dir>`
defaults to `./data`.

## Directory layout

```
data/
├── meta.json
└── archive/
    ├── index.json
    ├── daynight-2026.json
    ├── barometer-2026-10-03.json
    ├── barometer-2026-10.json
    ├── barometer-2026.json
    ├── tempdew-2026-10-03.json
    ├── wind-2026-10-03.json
    ├── windvec-2026-10-03.json
    └── ...
```

Summary of generated files:

| File                                                        | Purpose                                                                                                       | Update frequency                                                                     |
|:------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|
| [`meta.json`](#metajson)                                    | Unit systems, unit groups and conversion arithmetic.                                                          | Generated once on first report run (or when missing).                                |
| [`archive/index.json`](#archiveindexjson)                   | Master catalog of available plot groups, archive tiers, date coverage, and aggregation intervals.             | Updated every report cycle.                                                          |
| [`archive/<group>-<date>.json`](#archive-data-files)        | Time series data for one plot group over a single calendar day, month, or year.                               | Finished timespans are written once; the current timespan is updated incrementally.  |
| [`archive/daynight-<YYYY>.json`](#archivedaynight-yyyyjson) | Sunrise, sunset, and civil twilight timestamps for chart background shading.                                  | Generated once per calendar year (requires `pyephem` and `include_daynight = True`). |

---

## `meta.json`

The file `meta.json` contains static metadata required by client-side JavaScript
to handle unit conversions dynamically without requesting additional data from
the server. It says nothing about how to show the readings. A skin that draws
charts keeps that in a file of its own. The file `display.json` of the *Horizon*
skin is an example. See [`display.json`](#displayjson). Because this
configuration is static for a given skin, `meta.json` is written only on the
first report run (or if the file does not exist on disk).

### Structure

The top-level JSON object contains one key, **`units`** (*object*), with the
unit definitions and conversion tables:

* **`groups`** (*object*): Maps each observation type (e.g. `outTemp`,
  `barometer`, `windSpeed`) to its WeeWX unit group (e.g.
  `group_temperature`, `group_pressure`, `group_speed`).
* **`systems`** (*object*): Maps each standard unit system name (`US`,
  `METRIC`, `METRICWX`) to a dictionary, which maps unit groups (e.g.,
  `group_temperature`) to its
  corresponding unit in that system (e.g., `degree_C`).
* **`convert`** (*object*): Map that given a `from_unit` and a `to_unit`
  supplies a `[factor, offset]`. The client then converts a value
  using the formula: `to_value` = `from_value` * `factor` + `offset`.

### Example `meta.json`

```json
{
  "units": {
    "groups": {
      "outTemp": "group_temperature",
      "dewpoint": "group_temperature",
      "barometer": "group_pressure",
      "windSpeed": "group_speed",
      "windGust": "group_speed",
      "rain": "group_rain",
      "UV": "group_uv"
    },
    "systems": {
      "US": {
        "group_temperature": "degree_F",
        "group_pressure": "inHg",
        "group_speed": "mile_per_hour",
        "group_rain": "inch"
      },
      "METRIC": {
        "group_temperature": "degree_C",
        "group_pressure": "mbar",
        "group_speed": "km_per_hour",
        "group_rain": "cm"
      },
      "METRICWX": {
        "group_temperature": "degree_C",
        "group_pressure": "mbar",
        "group_speed": "meter_per_second",
        "group_rain": "mm"
      }
    },
    "convert": {
      "degree_F": {
        "degree_C": [
          0.555555555556,
          -17.777777777778
        ]
      },
      "degree_C": {
        "degree_F": [
          1.8,
          32.0
        ]
      },
      "inHg": {
        "mbar": [
          33.8639,
          0.0
        ],
        "hPa": [
          33.8639,
          0.0
        ]
      },
      "mile_per_hour": {
        "km_per_hour": [
          1.609344,
          0.0
        ],
        "knot": [
          0.86897624,
          0.0
        ],
        "meter_per_second": [
          0.44704,
          0.0
        ]
      }
    }
  }
}
```

---

## `archive/index.json`

The file `archive/index.json` acts as the master directory of all available
historical data files in the `archive/` folder. The client-side JavaScript reads
this index to determine available date ranges, plot groups, and aggregation
resolutions across all tiers.

### Structure

* **`first`** (*integer*): Unix epoch timestamp of the earliest record in the
  database.
* **`last`** (*integer*): Unix epoch timestamp of the latest record in the
  database.
* **`rebuilt`** (*integer | null*): Unix epoch timestamp when the archive files
  were last rebuilt, or `null`.
* **`groups`** (*array of objects*): List of available plot groups (the
  subsections of `[[JSONFiles]]` that have files). Each group object contains:
    * **`name`** (*string*): The plot group identifier (e.g., `"barometer"`,
      `"tempdew"`, `"wind"`, `"rain"`).
    * **`years`** (*object*): Map of year string (`"YYYY"`) to the `newest`
      timestamp (epoch seconds) recorded in that year's archive file.
    * **`year_intervals`** (*object*): Map of year string (`"YYYY"`) to the
      aggregation interval in seconds (e.g., `3600` or `14400`).
    * **`months`** (*object*): Map of month string (`"YYYY-MM"`) to the `newest`
      timestamp in that month's archive file.
    * **`month_intervals`** (*object*): Map of month string (`"YYYY-MM"`) to the
      aggregation interval in seconds (e.g., `900`).
    * **`days`** (*object*): Map of day string (`"YYYY-MM-DD"`) to the `newest`
      timestamp in that day's archive file.
    * **`day_intervals`** (*object*): Map of day string (`"YYYY-MM-DD"`) to the
      archive interval in seconds (e.g., `60` or `300`).

### Example `archive/index.json`

```json
{
  "first": 1788890520,
  "last": 1791053520,
  "rebuilt": null,
  "groups": [
    {
      "name": "tempdew",
      "years": {
        "2026": 1791050400
      },
      "year_intervals": {
        "2026": 3600
      },
      "months": {
        "2026-10": 1791053100,
        "2026-09": 1790838000
      },
      "month_intervals": {
        "2026-10": 900,
        "2026-09": 900
      },
      "days": {
        "2026-10-03": 1791053520,
        "2026-10-02": 1791010800,
        "2026-10-01": 1790924400,
        "2026-09-30": 1790838000
      },
      "day_intervals": {
        "2026-10-03": 60,
        "2026-10-02": 60,
        "2026-10-01": 60,
        "2026-09-30": 60
      }
    }
  ]
}
```

---

## Archive data files

Archive JSON data files store time series observations for one plot group over a
specific calendar span.

### The three tiers

The JSON database is divided into three levels of detail (tiers):

1. **Day tier (`<group>-YYYY-MM-DD.json`)**: Covers recent days (default: last
   30 days) at the station's archive interval (e.g., 5 minutes). Old
   day files beyond the retention limit are automatically purged.
2. **Month tier (`<group>-YYYY-MM.json`)**: Covers recent months (default: last
   2 months) at an intermediate aggregation interval (default: 15 minutes / 900
   seconds).
3. **Year tier (`<group>-YYYY.json`)**: Covers entire calendar years. Recent
   years (default: last 2 years) use `year_resolution` (default: 1 hour / 3600
   seconds), while older years use `old_year_resolution` (default: 4 hours /
   14400 seconds).

### Compact representation & timestamps

To keep file sizes small and downloads fast:

* Timestamps are not stored per data point.
* Instead, timestamps are implicit: the `i`-th entry in `values` represents the
  aggregation interval beginning at:  `timestamp_i = start + i * interval`.
* If no observation exists for an aggregation interval, `null` is written.

### Top-level properties

| Property   | Type               | Description                                                                                    |
|:-----------|:-------------------|:-----------------------------------------------------------------------------------------------|
| `name`     | *string*           | Plot group name (e.g., `"tempdew"`, `"barometer"`, `"wind"`).                                  |
| `start`    | *integer*          | Epoch timestamp of the start of the first aggregation interval in the file.                    |
| `interval` | *integer*          | Aggregation interval of the file in seconds (e.g., `60`, `900`, `3600`).                       |
| `count`    | *integer*          | Total number of intervals/entries in each series array (`(stop - start) / interval`).          |
| `newest`   | *integer*          | Epoch timestamp up to which data is complete in this file.                                     |
| `unit`     | *string*           | Unit name for all values in this plot group (e.g., `"degree_F"`, `"inHg"`, `"mile_per_hour"`). |
| `series`   | *array of objects* | Array of series objects defining each line, bar, or vector on the plot.                        |

### Series object properties

Each object in the `series` array contains:

| Property             | Type      | Presence | Description                                                                                                                                                                                               |
|:---------------------|:----------|:---------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `obs_type`           | *string*  | Required | Observation type name (e.g., `"outTemp"`, `"dewpoint"`, `"windSpeed"`, `"rain"`).                                                                                                                         |
| `aggregate_type`     | *string*  | Required | Aggregation function applied (e.g., `"avg"`, `"sum"`, `"min"`, `"max"`, `"vecdir"`).                                                                                                                      |
| `values`             | *array*   | Required | Array of length `count` containing numeric values or `null`. For vector plots, contains speed magnitudes.                                                                                                 |
| `aggregate_interval` | *integer* | Optional | Present on a series whose aggregation interval is coarser than the file interval (e.g., hourly totals on a 1-minute file). Aggregated values appear at every `n`-th index with `null`s in between.       |
| `min`                | *array*   | Optional | Array of length `count` containing the interval minimums. Present when `obs_type` is listed in `extremes` (e.g., `windSpeed`, `windGust`, `rainRate`, `UV`) and the series is aggregated.                 |
| `max`                | *array*   | Optional | Array of length `count` containing the interval maximums. Present when `obs_type` is listed in `extremes`.                                                                                                |
| `vector_x`           | *array*   | Optional | Real component of wind vector (for the types `windvec` and `windgustvec`).                                                                                                                                |
| `vector_y`           | *array*   | Optional | Imaginary component of wind vector (for the types `windvec` and `windgustvec`).                                                                                                                           |
| `directions`         | *array*   | Optional | Wind direction / compass bearing in degrees from `0⁰` to `360⁰` (for the types `windvec` and `windgustvec`).                                                                                              |

---

### Archive file examples

#### 1. Multi-line plot (`tempdew-2026-10-03.json`)

```json
{
  "name": "tempdew",
  "start": 1791010800,
  "interval": 60,
  "count": 713,
  "newest": 1791053520,
  "unit": "degree_F",
  "series": [
    {
      "obs_type": "outTemp",
      "aggregate_type": "avg",
      "values": [
        55.5,
        55.4,
        55.2,
        null,
        55.1,
        55.0
      ]
    },
    {
      "obs_type": "dewpoint",
      "aggregate_type": "avg",
      "values": [
        51.38,
        51.28,
        51.09,
        null,
        51.4,
        51.3
      ]
    }
  ]
}
```

#### 2. Totals over a longer interval (`rain-2026-10-03.json`)

For series with `aggregate_interval` greater than the file's `interval` (for
example, hourly rain totals on a 1-minute day file), values are placed at
every `n`-th index (e.g., every 60 intervals for 1-hour totals on 60-second
resolution) with `null`s filling the remaining slots:

```json
{
  "name": "rain",
  "start": 1791010800,
  "interval": 60,
  "count": 713,
  "newest": 1791053520,
  "unit": "inch",
  "series": [
    {
      "obs_type": "rain",
      "aggregate_type": "sum",
      "aggregate_interval": 3600,
      "values": [
        0.05,
        null,
        null,
        null,
        0.12,
        null,
        null
      ]
    }
  ]
}
```

#### 3. Plot with extremes (`wind-2026.json`)

Observation types included in the `extremes` setting (default: `windGust`,
`windSpeed`, `rainRate`, `UV`) include `min` and `max` arrays alongside the
aggregate `values`:

```json
{
  "name": "wind",
  "start": 1788890400,
  "interval": 3600,
  "count": 601,
  "newest": 1791050400,
  "unit": "mile_per_hour",
  "series": [
    {
      "obs_type": "windSpeed",
      "aggregate_type": "avg",
      "values": [
        1.37,
        2.02,
        2.27,
        1.88
      ],
      "min": [
        0.0,
        0.5,
        1.1,
        0.2
      ],
      "max": [
        3.4,
        4.8,
        5.2,
        4.1
      ]
    },
    {
      "obs_type": "windGust",
      "aggregate_type": "avg",
      "values": [
        3.2,
        5.1,
        6.4,
        4.8
      ],
      "min": [
        1.2,
        2.0,
        3.1,
        1.5
      ],
      "max": [
        7.5,
        10.2,
        12.0,
        8.4
      ]
    }
  ]
}
```

#### 4. Vector plot (`windvec-2026-10-03.json`)

Wind vector series (of the types `windvec` and `windgustvec`) contain directional
and cartesian components for rendering wind arrows:

```json
{
  "name": "windvec",
  "start": 1791010800,
  "interval": 60,
  "count": 713,
  "newest": 1791053520,
  "unit": "mile_per_hour",
  "series": [
    {
      "obs_type": "windvec",
      "aggregate_type": "avg",
      "values": [
        4.2,
        5.0,
        3.8
      ],
      "vector_x": [
        0.0,
        3.54,
        -2.69
      ],
      "vector_y": [
        4.2,
        3.54,
        2.69
      ],
      "directions": [
        0.0,
        45.0,
        315.0
      ]
    }
  ]
}
```

---

## `archive/daynight-<YYYY>.json`

When `include_daynight = True` (default) and `pyephem` is installed, the JSON
generator writes one `daynight-<YYYY>.json` file per calendar year. This file
contains the times of sunrise, sunset, and civil twilight for the station's
latitude and longitude, allowing browser charts to render daytime and nighttime
background shading.

### Structure

* **`first`** (*string*): `"day"` or `"night"`, indicating the solar state at
  the start of the year (January 1, 00:00:00 local time).
* **`start`** (*integer*): Epoch timestamp of the start of the year.
* **`transitions`** (*array of integers*): Sorted array of epoch timestamps
  marking alternating sunrise and sunset events throughout the year.
* **`twilight`** (*array of objects*): Chronological list of civil twilight
  periods:
    * **`from`** (*integer*): Start timestamp of the twilight period.
    * **`to`** (*integer*): End timestamp of the twilight period.
    * **`dir`** (*string*): `"dawn"` (morning twilight from civil dawn to
      sunrise) or `"dusk"` (evening twilight from sunset to civil dusk).

### Example `archive/daynight-2026.json`

```json
{
  "first": "night",
  "start": 1767254400,
  "transitions": [
    1767282364,
    1767314164,
    1767368768,
    1767400617
  ],
  "twilight": [
    {
      "from": 1767280353,
      "to": 1767282364,
      "dir": "dawn"
    },
    {
      "from": 1767314164,
      "to": 1767316175,
      "dir": "dusk"
    }
  ]
}
```

---

## `display.json`

The *Horizon* skin writes the file `display.json` into its `HTML_ROOT`, not into
the directory of the JSON generator. It is not part of the generator's output:
it holds how Horizon shows the readings, and `weewx-json.js` reads it with them.
The template `display.json.tmpl` writes it from the options in
[`[DisplayOptions]`](../custom/horizon-skin.md#changing-what-a-chart-shows), on
every report. A report in another language has a `display.json` of its own, with
the labels in that language.

* **`periods`** (*array of strings*): The time spans on offer, e.g.,
  `["day", "week", "month", "year"]`.
* **`time_lengths`** (*object*): The length in seconds of the live view of each
  time span.
* **`plot_groups`**, **`telemetry_plot_groups`** (*array of strings*): The plot
  groups for charts on the front page and telemetry page.
* **`charts`** (*object*): Maps each plot group to its options: `plot_type`
  (`"line"`, `"bar"`, or `"vector"`), `yscale`
  (`[minimum, maximum, step]`, where each value can be `null`), `vector_rotate`
  (degrees), and `overrides`. The key `overrides` captures any overrides in the
  `[[Charts]]` subsection, typically `label`, `plot_type`, and
  `vector_rotate`. If absent, then unit group defaults are used.
* **`labels`** (*object*): Maps each observation type to its generic label.
* **`units`** (*object*): Contains the unit information that `meta.json` omits:
  `report` (the unit used by the report for each unit group), `labels` (the
  label for each unit, e.g., `"degree_C": "°C"`), and `formats` (the `printf`
  format for each unit, e.g., `"degree_F": "%.1f"`).

```json
{
  "periods": ["day", "week"],
  "time_lengths": {"day": 97200, "week": 604800},
  "plot_groups": ["tempdew", "rain"],
  "telemetry_plot_groups": ["rx"],
  "charts": {
    "rain": {
      "plot_type": "bar",
      "yscale": [null, null, null],
      "vector_rotate": 90.0,
      "series": {"rain": {"label": "Rain (hourly total)"}}
    }
  },
  "labels": {"outTemp": "Outside Temperature", "rain": "Rain"},
  "units": {
    "report": {"group_temperature": "degree_F"},
    "labels": {"degree_F": "°F"},
    "formats": {"degree_F": "%.1f"}
  }
}
```
