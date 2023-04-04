# Localization

This section provides suggestions for localization, including
translation to different languages and display of data in formats
specific to a locale.

## If the skin has been internationalized

All the skins that come with WeeWX have been *internationalized*,
that is, they are capable of being *localized*, although there may or may not
be a localization available for your specific language.
See the section [Internationalized skins](../custom_reports/#internationalized-skins) for
how to tell.

### Internationalized, your language is available

This is the easy case: the skin has been internationalized, and your
locale is available. In this case, all you need to do is to select your
locale in `weewx.conf`. For example, to select German (code
`de`) for the *Seasons* skin, just add the highlighted line (or
change, if it's already there):

``` ini hl_lines="9"
...
[StdReport]
    ...
    [[SeasonsReport]]
        # The SeasonsReport uses the 'Seasons' skin, which contains the
        # images, templates and plots for the report.
        skin = Seasons
        enable = true
        lang = de
        ...
```

### Internationalized, but your language is missing {#internationalized-missing-language}

If the `lang` subdirectory is present in the skin directory, then
the skin has been internationalized. However, if your language code is
not included in the subdirectory, then you will have to *localize* it to
your language. To do so, copy the file `en.conf` and name it
according to the language code of your language. Then translate all the
strings on the right side of the equal signs to your language. For
example, say you want to localize the skin in the French language. Then
copy `en.conf` to `fr.conf`

```shell
cp en.conf fr.conf
```

Then change things that look like this:

``` ini
...
[Texts]
    "Language" = "English"

    "7-day" = "7-day"
    "24h" = "24h"
    "About this weather station" = "About this weather station"
    ...
```

to something that looks like this:

``` ini
...
[Texts]
    Language = French

    "7-day" = "7-jours"
    "24h" = "24h"
    "About this weather station" = "A propos de cette station"
    ...
```

And so on. When you're done, the skin author may be interested in your
localization file to ship it together with the skin for the use of other
users. If the skin is one that came with WeeWX, contact the WeeWX team
via a post to the [weewx-user
group](https://groups.google.com/forum/#!forum/weewx-user) and, with
your permission, we may include your localization file in a future WeeWX
release.

Finally, set the option `lang` in `weewx.conf` to your
language code (`fr` in this example) as described in the [User's
Guide](../../usersguide/weewx-config-file/stdreport-config/#lang).

## How to internationalize a skin

What happens when you come across a skin that you like, but it has not
been internationalized? This section explains how to convert the report
to local formats and language.

Internationalization of WeeWX templates uses a pattern very similar to
the well-known GNU
"[`gettext`](https://www.gnu.org/software/gettext/)" approach.
The only difference is that we have leveraged the `ConfigObj`
configuration library used throughout WeeWX.

### Create the localization file

Create a subdirectory called `lang` in the skin directory. Then create a file named by the language
code with the suffix `.conf` in this subdirectory. For example, if you want to translate to
Spanish, name the file `lang/es.conf`. Include the following in the file:

``` ini
[Units]

    [[Labels]]

        # These are singular, plural
        meter             = " meter",  " meters"
        day               = " day",    " days"
        hour              = " hour",   " hours"
        minute            = " minute", " minutes"
        second            = " second", " seconds"

    [[Ordinates]]

        # Ordinal directions. The last one should be for no wind direction
        directions = N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW, N/A

[Labels]

    # Set to hemisphere abbreviations suitable for your location:
    hemispheres = N, S, E, W

    # Generic labels, keyed by an observation type.
    [[Generic]]
        altimeter              = Altimeter                # QNH
        altimeterRate          = Altimeter Change Rate
        appTemp                = Apparent Temperature
        appTemp1               = Apparent Temperature
        barometer              = Barometer                # QFF
        barometerRate          = Barometer Change Rate
        cloudbase              = Cloud Base
        dateTime               = Time
        dewpoint               = Dew Point
        ET                     = ET
        extraTemp1             = Temperature1
        extraTemp2             = Temperature2
        extraTemp3             = Temperature3
        heatindex              = Heat Index
        inDewpoint             = Inside Dew Point
        inHumidity             = Inside Humidity
        inTemp                 = Inside Temperature
        interval               = Interval
        lightning_distance     = Lightning Distance
        lightning_strike_count = Lightning Strikes
        outHumidity            = Outside Humidity
        outTemp                = Outside Temperature
        pressure               = Pressure                 # QFE
        pressureRate           = Pressure Change Rate
        radiation              = Radiation
        rain                   = Rain
        rainRate               = Rain Rate
        THSW                   = THSW Index
        UV                     = UV Index
        wind                   = Wind
        windchill              = Wind Chill
        windDir                = Wind Direction
        windGust               = Gust Speed
        windGustDir            = Gust Direction
        windgustvec            = Gust Vector
        windrun                = Wind Run
        windSpeed              = Wind Speed
        windvec                = Wind Vector


[Almanac]

    # The labels to be used for the phases of the moon:
    moon_phases = New, Waxing crescent, First quarter, Waxing gibbous, Full, Waning gibbous, Last quarter, Waning crescent

[Texts]

    Language              = Español # Replace with the language you are targeting
        
```

Go through the file, translating all phrases on the right-hand side of
the equal signs to your target language (Spanish in this example).

### Internationalize the template

You will need to internationalize every HTML template (these typically
have a file suffix of `.html.tmpl`). This is most easily done by
opening the template and the language file in different editor windows.
It is much easier if you can change both files simultaneously.

#### Change the `html lang` attribute

At the top of the template, change the HTML "lang" attribute to a
configurable value.

``` html
<!DOCTYPE html>
<html lang="$lang">
  <head>
    <meta charset="UTF-8">
    ...
```

The value `$lang` will get replaced by the actual language to be
used.

[language codes](https://www.w3schools.com/tags/ref_language_codes.asp)<br/>
[country codes](https://www.w3schools.com/tags/ref_country_codes.asp)

#### Change the body text

The next step is to go through the templates and change all natural
language phrases into lookups using `$gettext`. For example,
suppose your skin has a section that looks like this:

``` html
<div>
    Current Conditions
    <table>
        <tr>
            <td>Outside Temperature</td>
            <td>$current.outTemp</td>
        </tr>
    </table>
</div>
```

There are two natural language phrases here: *Current Conditions* and
*Outside Temperature*. They would be changed to:

``` html
<div>
    $gettext("Current Conditions")
    <table>
        <tr>
            <td>$obs.label.outTemp</td>
            <td>$current.outTemp</td>
        </tr>
    </table>
</div>
```

We have done two replacements here. For the phrase *Current Conditions*,
we substituted `$gettext("Current Conditions")`. This will
cause the Cheetah Generator to look up the localized version of
"Current Conditions" in the localization file and substitute it. We
could have done something similar for *Outside Temperature*, but in this
case, we chose to use the localized name for type `outTemp`,
which you should have provided in your localization file, under section
`[Labels] / [[Generic]]`.

In the localization file, include the translation for *Current
Conditions* under the `[Texts]` section:

``` ini
...
[Texts]

    "Language"           = "Español"
    "Current Conditions" = "Condiciones Actuales"
    ...
```

Repeat this process for all the strings that you find. Make sure not to
replace HTML tags and HTML options.

### Think about time

Whenever a time is used in a template, it will need a format. WeeWX
comes with the following set of defaults, defined in
`defaults.py`:

``` ini
[Units]
    ...
    [[TimeFormats]]
        day        = %X
        week       = %X (%A)
        month      = %x %X
        year       = %x %X
        rainyear   = %x %X
        current    = %x %X
        ephem_day  = %X
        ephem_year = %x %X
```

These defaults will give something readable in every locale, but they
may not be very pretty. Therefore, you may want to change them to
something more suitable for the locale you are targeting, using the
Python [`strftime()` specific
directives](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior).

Example: the default time formatting for "Current" conditions is `%x
%x`, which will show today's date as "14/05/21 10:00:00" in the
Spanish locale. Suppose you would rather see "14-mayo-2021 10:00". You
would add the following to your Spanish localization file
`es.conf`:

``` ini
...

[Units]
    [[TimeFormats]]
        current = %d-%B-%Y %H:%M

...     
```

### Set the environment variable `LANG` {#environment_variable_LANG}

Finally, you will need to set the environment variable `LANG` to
reflect your locale. For example, assuming you set

``` shell
$ export LANG=es_ES.UTF-8
```

before running WeeWX, then the local Spanish names for days of the week
and months of the year will be used. The decimal point for numbers will
also be modified appropriately.
