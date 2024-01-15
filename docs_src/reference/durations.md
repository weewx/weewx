# Durations

Rather than give a value in seconds, many durations can be expressed using a shorthand notation.
For example, in a skin configuration file `skin.conf`, a value for `aggregate_interval` can be 
given as either

    aggregate_interval = 3600

or

    aggregate_interval = 1h

The same notation can be used in trends. For example:

    <p>Barometer trend over the last 2 hours: $trend(time_delta='2h').barometer</p>

Here is a summary of the notation:

| Example | Meaning            |
|---------|--------------------|
| `10800` | 3 hours            |
| `3h`    | 3 hours            |
| `1d`    | 1 day              |
| `2w`    | 2 weeks            |
| `1m`    | 1 month            |
| `1y`    | 1 year             |
| `hour`  | Synonym for `1h`   |
| `day`   | Synonym for `1d`   |
| `week`  | Synonym for `1w`   |
| `month` | Synonym for `1m`   |
| `year`  | Synonym for `1y`   |
