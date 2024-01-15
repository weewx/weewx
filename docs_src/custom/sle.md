# Writing search list extensions

The intention of this document is to help you write new Search List
Extensions (SLE). Here's the plan:

* We start by explaining how SLEs work.

* Then we will look at an example that implements an extension `$seven_day()`.

* Then we will look at another example, `$colorize()`, which allows you to
pick background colors on the basis of a value (for example, low temperatures
could show blue, while high temperatures show red). It will be implemented
using 3 different, increasingly sophisticated, ways:

    * A simple, hardwired version that works in only one unit system.

    * A version that can handle any unit system, but with the colors
        still hardwared.

    * Finally, a version that can handle any unit system, and takes
        its color bands from the configuration file.


## How the search list works

Let's start by taking a look at how the Cheetah search list works.

The Cheetah template engine finds tags by scanning a search list, a
Python list of objects. For example, for a tag `$foo`, the
engine will scan down the list, trying each object in the list in turn.
For each object, it will first try using `foo` as an attribute,
that is, it will try evaluating `obj.foo`. If that raises an
`AttributeError` exception, then it will try `foo` as a
key, that is `obj[key]`. If that raises a `KeyError`
exception, then it moves on to the next item in the list. The first
match that does not raise an exception is used. If no match is found,
Cheetah raises a `NameMapper.NotFound` exception.

### A simple tag {#simple-tag}

Now let's take a look at how the search list interacts with WeeWX tags.
Let's start by looking at a simple example: station altitude, available
as the tag

``` html
$station.altitude
```

As we saw in the previous section, Cheetah will run down the search list,
looking for an object with a key or attribute `station`. In the default
search list, WeeWX includes one such object, an instance of the class
`weewx.cheetahgenerator.Station`, which has an attribute `station`, so
it gets a hit on this object.

Cheetah will then try to evaluate the attribute `altitude` on this object.
Class `Station` has such an attribute, so Cheetah evaluates it.

#### Return value

What this attribute returns is not a raw value, say `700`, nor
even a string. Instead, it returns an instance of the class
[`ValueHelper`](../reference/valuehelper.md), a special class defined in module
`weewx.units`. Internally, it holds not only the raw value, but
also references to the formats, labels, and conversion targets you
specified in your configuration file. Its job is to make sure that the
final output reflects these preferences. Cheetah doesn't know anything
about this class. What it needs, when it has finished evaluating the
expression `$station.altitude`, is a *string*. In order to
convert the `ValueHelper` it has in hand into a string, it does
what every other Python object does when faced with this problem: it
calls the special method
[`__str__`](https://docs.python.org/3/reference/datamodel.html#object.__str__).
Class `ValueHelper` has a definition for this method. Evaluating
this function triggers the final steps in this process. Any necessary
unit conversions are done, then formatting occurs and, finally, a label
is attached. The result is a string something like

<div class="example_output">
700 feet
</div>

which is what Cheetah actually puts in the generated HTML file. This is
a good example of *lazy evaluation*. The tags gather all the information
they need, but don't do the final evaluation until the last final
moment, when the most context is understood. WeeWX uses this technique
extensively.

### A slightly more complex tag {#complex-tag}

Now let's look at a more complicated example, say the maximum
temperature since midnight:

``` html
$day.outTemp.max
```

When this is evaluated by Cheetah, it actually produces a chain of
objects. At the top of this chain is class
`weewx.tags.TimeBinder`, an instance of which is included in the
default search list. Internally, this instance stores the time of the
desired report (usually the time of the last archive record), a cache to
the databases, a default data binding, as well as references to the
formatting and labelling options you have chosen.

This instance is examined by Cheetah to see if it has an attribute
`day`. It does and, when it is evaluated, it returns the next
class in the chain, an instance of `weewx.tags.TimespanBinder`.
In addition to all the other things contained in its parent
`TimeBinder`, class `TimespanBinder` adds the desired time
period, that is, the time span from midnight to the current time.

Cheetah then continues on down the chain and tries to find the next
attribute, `outTemp`. There is no such hard coded attribute (hard
coding all the conceivable different observation types would be
impossible!). Instead, class `TimespanBinder` defines the Python
special method
[`__getattr__`](https://docs.python.org/3/reference/datamodel.html#object.__getattr__).
If Python cannot find a hard coded version of an attribute, and the
method `__getattr__` exists, it will try it. The definition
provided by `TimespanBinder` returns an instance of the next
class in the chain, `weewx.tags.ObservationBinder`, which not
only remembers all the previous stuff, but also adds the observation
type, `outTemp`.

Cheetah then tries to evaluate an attribute `max` of this class, and the
pattern repeats. Class `weewx.tags.ObservationBinder` does not have an
attribute `max`, but it does have a method `__getattr__`. This method
returns an instance of the next class in the chain, class `AggTypeBinder`,
which not only remembers all the previous information, but adds the
aggregation type, `max`.

One final step needs to occur: Cheetah has an instance of
`AggTypeBinder` in hand, but what it really needs is a string to
put in the file being created from the template. It creates the string
by calling the method `__str__()` of `AggTypeBinder`.
Now, finally, the chain ends and everything comes together. The method
`__str__` triggers the actual calculation of the value, using
all the known parameters: the database binding to be hit, the time span
of interest, the observation type, and the type of aggregation, querying
the database as necessary. The database is not actually hit until the
last possible moment, after everything needed to do the evalation is
known.

Like our previous example, the results of the evaluation are then
packaged up in an instance of `ValueHelper`, which does the final
conversion to the desired units, formats the string, then adds a label.
The results, something like

<div class="example_output">
12°C
</div>

are put in the generated HTML file. As you can see, a lot of machinery
is hidden behind the deceptively simple expression
`$day.outTemp.max`!


## Extending the list {#extending-the-list}

As mentioned, WeeWX comes with a number of objects already in the search
list, but you can extend it.

The general pattern is to create a new class that inherits from
`weewx.cheetahgenerator.SearchList`, which supplies the
functionality you need. You may or may not need to override its member
function `get_extension_list()`. If you do not, then a default is
supplied.

### Adding tag `$seven_day`

Let's look at an example. The regular version of WeeWX offers statistical
summaries by day, week, month, year, rain year, and all time. While WeeWX offers
the tag `$week`, this is statistics *since Sunday at midnight*. Suppose we would
like to have statistics for a full week, that is since midnight seven days ago.

If you wish to use or modify this example, cut and paste the below to
`user/seven_day.py`.

``` {.python .copy}
import datetime
import time

from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan

class SevenDay(SearchList):                                                  # 1

    def __init__(self, generator):                                           # 2
        SearchList.__init__(self, generator)

    def get_extension_list(self, timespan, db_lookup):                       # 3
        """Returns a search list extension with two additions.

        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
        """

        # Create a TimespanBinder object for the last seven days. First,
        # calculate the time at midnight, seven days ago. The variable week_dt 
        # will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(timespan.stop) \
                  - datetime.timedelta(weeks=1)                              # 4
        # Convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())                           # 5
        # Form a TimespanBinder object, using the time span we just
        # calculated:
        seven_day_stats = TimespanBinder(TimeSpan(week_ts, timespan.stop),
                                         db_lookup,
                                         context='week',
                                         formatter=self.generator.formatter,
                                         converter=self.generator.converter,
                                         skin_dict=self.generator.skin_dict) # 6

        # Now create a small dictionary with the key 'seven_day':
        search_list_extension = {'seven_day' : seven_day_stats}              # 7

        # Finally, return our extension as a list:
        return [search_list_extension]                                       # 8
```

Going through the example, line by line:

1.  Create a new class called `SevenDay`, which will inherit from
    class `SearchList`. All search list extensions must inherit
    from this class.
2.  Create an initializer for our new class. In this case, the
    initializer is not really necessary and does nothing except pass its
    only parameter, `generator`, a reference to the calling
    generator, on to its superclass, `SearchList`, which will
    then store it in `self`. Nevertheless, we include the
    initializer in case you wish to modify it.
3.  Override member function `get_extension_list()`. This
    function will be called when the generator is ready to accept your
    new search list extension. The parameters that will be passed in
    are:
    -   `self` Python's way of indicating the instance we are
        working with;
    -   `timespan` An instance of the utility class
        `TimeSpan`. This will contain the valid start and ending
        times used by the template. Normally, this is all valid times,
        but if your template appears under one of the
        ["Summary By"](../reference/skin-options/cheetahgenerator.md#summarybyday)
        sections in the `[CheetahGenerator]` section of `skin.conf`, then
        it will contain the timespan of that time period.
    -   `db_lookup` This is a function supplied by the generator.
        It takes a single argument, a name of a binding. When called, it
        will return an instance of the database manager class for that
        binding. The default for the function is whatever binding you
        set with the option `data_binding` for this report,
        usually `wx_binding`.
4.  The object `timespan` holds the domain of all valid times for
    the template, but in order to calculate statistics for the last
    seven days, we need not the earliest valid time, but the time at
    midnight seven days ago. So, we do a little Python date arithmetic
    to calculate this. The object `week_dt` will be an instance
    of `datetime.date`.
5.  We convert it to unix epoch time and assign it to variable
    `week_ts`.
6.  The class `TimespanBinder` represents a statistical calculation over a
    time period. We have [already met it](#complex-tag) in the introduction.
    In our case, we will set it up to represent the statistics over the last
    seven days. The class takes 6 parameters.
    -   The first is the timespan over which the calculation is to be
        done, which, in our case, is the last seven days. In step 5, we
        calculated the start of the seven days. The end is "now", that
        is, the end of the reporting period. This is given by the end
        point of `timespan`, `timespan.stop`.
    -   The second, `db_lookup`, is the database lookup function
        to be used. We simply pass in `db_lookup`.
    -   The third, `context`, is the time *context* to be used
        when formatting times. The set of possible choices is given by
        sub-section [`[[TimeFormats]]`](../reference/skin-options/units.md#timeformats)
        in the configuration file. Our new tag, `$seven_day`
        is pretty similar to `$week`, so we will just use
        `'week'`, indicating that we want a time format that is
        suitable for a week-long period.
    -   The fourth, `formatter`, should be an instance of class
        `weewx.units.Formatter`, which contains information about
        how the results should be formatted. We just pass in the
        formatter set up by the generator,
        `self.generator.formatter`.
    -   The fifth, `converter`, should be an instance of
        `weewx.units.Converter`, which contains information about
        the target units (*e.g.*, `degree_C`) that are to be
        used. Again, we just pass in the instance set up by the
        generator, `self.generator.converter`.
    -   The sixth, `skin_dict`, is an instance of
        `configobj.ConfigObj`, and contains the contents of the
        skin configuration file. We pass it on in order to allow
        aggregations that need information from the file, such as
        heating and cooling degree-days.
7.  Create a small dictionary with a single key, `seven_day`,
    whose value will be the `TimespanBinder` that we just
    constructed.
8.  Return the dictionary in a list

#### Registering {#register-seven-day}

The final step that we need to do is to tell the template engine where
to find our extension. You do that by going into the skin configuration
file, `skin.conf`, and adding the option
`search_list_extensions` with our new extension. When you're
done, it will look something like this:

``` ini hl_lines="8"
[CheetahGenerator]
    # This section is used by the generator CheetahGenerator, and specifies
    # which files are to be generated from which template.

    # Possible encodings include 'html_entities', 'strict_ascii', 'normalized_ascii',
    # as well as those listed in https://docs.python.org/3/library/codecs.html#standard-encodings
    encoding = html_entities
    search_list_extensions = user.seven_day.SevenDay

    [[SummaryByMonth]]
    ...
```

Our addition has been ==highlighted==. Note that it is in the
section `[CheetahGenerator]`.

Now, if the Cheetah engine encounters the tag `$seven_day`, it
will scan the search list, looking for an attribute or key that matches
`seven_day`. When it gets to the little dictionary we provided,
it will find a matching key, allowing it to retrieve the appropriate
`TimespanBinder` object.

With this approach, you can now include "seven day" statistics in your
HTML templates:

``` html hl_lines="12"
<table>
    <tr>
        <td>Maximum temperature over the last seven days:</td>
        <td>$seven_day.outTemp.max</td>
    </tr>
    <tr>
        <td>Minimum temperature over the last seven days:</td>
        <td>$seven_day.outTemp.min</td>
    </tr>
    <tr>
        <td>Rain over the last seven days:</td>
        <td>$seven_day.rain.sum</td>
    </tr>
</table>
```

We put our addition `seven_day.py` in the "user" directory, which is
automatically included by WeeWX in the Python path. However, if you put the file
somewhere else, you may have to specify its location with the environment
variable [`PYTHONPATH`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH) 
when you start WeeWX:

``` shell
export PYTHONPATH=/home/me/secret_location
```

### Adding tag `$colorize`

Let's look at another example. This one will allow you to supply a
background color, depending on the temperature. For example, to colorize
an HTML table cell:

``` html hl_lines="7"
<table>

    ...

  <tr>
    <td>Outside temperature</td>
    <td style="background-color:$colorize($current.outTemp.raw)">$current.outTemp</td>
  </tr>

    ...

</table>
```

The highlighted expression will return a color, depending on the value
of its argument. For example, if the temperature was 30.9ºF, then the
output might look like:

<table>
    <tr>
        <td>Outside temperature</td>
        <td style="background-color:violet">30.9&#176;F</td>
    </tr>
</table>

#### A very simple implementation

We will start with a very simple version. The code can be found in
`examples/colorize/colorize_1.py`.

``` python
from weewx.cheetahgenerator import SearchList

class Colorize(SearchList):                                          # 1

    def colorize(self, t_c):                                         # 2
        """Choose a color on the basis of temperature

        Args:
            t_c (float): The temperature in degrees Celsius

        Returns:
            str: A color string
        """

        if t_c is None:                                              # 3
            return "#00000000"
        elif t_c < -10:
            return "magenta"
        elif t_c < 0:
            return "violet"
        elif t_c < 10:
            return "lavender"
        elif t_c < 20:
            return "mocassin"
        elif t_c < 30:
            return "yellow"
        elif t_c < 40:
            return "coral"
        else:
            return "tomato"
```

The first thing that's striking about this version is just how simple
an SLE can be: just one class with a single function. Let's go through
the implementation line-by-line.

1.  Just like the first example, all search list extensions inherit from
    `weewx.cheetahgenerator.SearchList`

2.  The class defines a single function, `colorize()`, with a
    single argument that must be of type `float`.

    Unlike the first example, notice how we do not define an
    initializer, `__init__()`, and, instead, rely on our
    superclass to do the initialization.

3.  The function relies on a big if/else statement to pick a color on
    the basis of the temperature value. Note how it starts by checking
    whether the value could be Python `None`. WeeWX uses `None` to represent
    missing or invalid data. One must be always vigilant in guarding
    against a `None` value. If `None` is found, then the color `#00000000` is
    returned, which is transparent and will have no effect.

#### Registering {#register-colorize}

As before, we must register our extension with the Cheetah engine. We do
this by copying the extension to the user directory, then adding its
location to option `search_list_extensions`:

``` ini
[CheetahGenerator]
    ...
    search_list_extensions = user.colorize_1.Colorize
    ...
```

#### Where is `get_extension_list()`?

You might wonder, "What happened to the member function
`get_extension_list()`? We needed it in the first example; why
not now?" The answer is that we are inheriting from, and relying on,
the version in the superclass `SearchList`, which looks like
this:

``` python
    def get_extension_list(self, timespan, db_lookup):
        return [self]
```

This returns a list, with itself (an instance of class
`Colorize`) as the only member.

How do we know whether to include an instance of
`get_extension_list()`? Why did we include a version in the first
example, but not in the second?

The answer is that many extensions, including `$seven_day`, need
information that can only be known when the template is being evaluated.
In the case of `$seven_day`, this was which database binding to
use, which will determine the results of the database query done in its
implementation. This information is not known until
`get_extension_list()` is called, which is just before template
evaluation.

By constrast, `$colorize()` is pure static: it doesn't use the
database at all, and everything it needs it can get from its single
function argument. So, it has no need for the information in
`get_extension_list()`.

#### Review

Let's review the whole process. When the WeeWX Cheetah generator starts
up to evaluate a template, it first creates a search list. It does this
by calling `get_extension_list()` for each SLE that has been
registered with it. In our case, this will cause the function above to
put an instance of `Colorize` in the search list &mdash; we don't
have to do anything to make this happen.

When the engine starts to process the template, it will eventually come
to

``` html
<td style="background-color:$colorize($current.outTemp.raw)">$current.outTemp</td>
```

It needs to evaluate the expression
`$colorize($current.outTemp.raw)`, so it starts scanning the
search list looking for something with an attribute or key
`colorize`. When it comes to our instance of `Colorize` it
gets a hit because, in Python, member functions are implemented as
attributes. The Cheetah engine knows to call it as a function because of
the parenthesis that follow the name. The engine passes in the value of
`$current.outTemp.raw` as the sole argument, where it appears
under the name `t_c`.

As described above, the function `colorize()` then uses the
argument to choose an appropriate color, returning it as a string.

#### Limitation

This example has an obvious limitation: the argument to
`$colorize()` must be in degrees Celsius. We can guard against
passing in the wrong unit by always converting to Celsius first:

``` html
<td style="background-color:$colorize($current.outTemp.degree_C.raw)">$current.outTemp</td>
```

but the user would have to remember to do this every time
`colorize()` is called. The next version gets around this
limitation.

#### A slightly better version

Here's an improved version that can handle an argument that uses any
unit, not just degrees Celsius. The code can be found in
`examples/colorize/colorize_2.py`.

``` python
import weewx.units
from weewx.cheetahgenerator import SearchList

class Colorize(SearchList):                                          # 1

    def colorize(self, value_vh):                                    # 2
        """Choose a color string on the basis of a temperature value"""

        # Extract the ValueTuple part out of the ValueHelper
        value_vt = value_vh.value_t                                  # 3

        # Convert to Celsius:
        t_celsius = weewx.units.convert(value_vt, 'degree_C')        # 4

        # The variable "t_celsius" is a ValueTuple. Get just the value:
        t_c = t_celsius.value                                        # 5

        # Pick a color based on the temperature
        if t_c is None:                                              # 6
            return "#00000000"
        elif t_c < -10:
            return "magenta"
        elif t_c < 0:
            return "violet"
        elif t_c < 10:
            return "lavender"
        elif t_c < 20:
            return "mocassin"
        elif t_c < 30:
            return "yellow"
        elif t_c < 40:
            return "coral"
        else:
            return "tomato"
```

Going through the example, line by line:

1.  Just like the other examples, we must inherit from
    `weewx.cheetahgenerator.SearchList`.

2.  However, in this example, notice that the argument to
    `colorize()` is an instance of class
    [`ValueHelper`](../reference/valuehelper.md), instead of a
    simple float.

    As before, we do not define an initializer, `__init__()`,
    and, instead, rely on our superclass to do the initialization.

3.  The argument `value_vh` will contain many things, including
    formatting and preferred units, but, for now, we are only interested
    in the [`ValueTuple`](../reference/valuetuple.md) contained
    within, which can be extracted with the attribute `value_t`.

4.  The variable `value_vt` could be in any unit that measures
    temperature. Our code needs Celsius, so we convert to Celsius using
    the convenience function `weewx.units.convert()`. The results
    will be a new `ValueTuple`, this time in Celsius.

5.  We need just the temperature value, and not the other things in a
    `ValueTuple`, so extract it using the attribute
    `value`. The results will be a simple instance of
    `float` or, possibly, Python `None`.

6.  Finally, we need a big if/else statement to choose which color to
    return, while making sure to test for `None`.

This version uses a `ValueHelper` as an argument instead of a
float. How do we call it? Here's an example:

``` tty hl_lines="7"
<table>

    ...

  <tr>
    <td>Outside temperature</td>
    <td style="background-color:$colorize($current.outTemp)">$current.outTemp</td>
  </tr>

    ...

</table>
```

This time, we call the function with a simple `$current.outTemp` (without the
`.raw` suffix), which is actually an instance of class `ValueHelper`. When we
met this class earlier, the Cheetah engine needed a string to put in the
template, so it called the special member function `__str__()`. However, in this
case, the results are going to be used as an argument to a function, not as a
string, so the engine simply passes in the `ValueHelper` unchanged to
`colorize()`, where it appears as argument `value_vh`.

Our new version is better than the original because it can take a
temperature in any unit, not just Celsius. However, it can still only
handle temperature values and, even then, the color bands are still
hardwired in. Our next version will remove these limitations.

#### A more sophisticated version

Rather than hardwire in the values and observation type, in this version
we will retrieve them from the skin configuration file,
`skin.conf`. Here's what a typical configuration might look like
for this version:

``` ini
[Colorize]                      # 1
    [[group_temperature]]       # 2
        unit_system = metricwx  # 3
        default = tomato        # 4
        None = lightgray        # 5
        [[[upper_bounds]]]      # 6
            -10 = magenta       # 7
            0 = violet          # 8
            10 = lavender
            20 = mocassin
            30 = yellow
            40 = coral
    [[group_uv]]                # 9
        unit_system = metricwx
        default = darkviolet
        [[[upper_bounds]]]
            2.4 = limegreen
            5.4 = yellow
            7.4 = orange
            10.4 = red
```

Here's what the various lines in the configuration stanza mean:

1.  All the configuration information needed by the SLE
    `Colorize` can be found in a stanza with the heading
    `[Colorize]`. Linking facility with a stanza of the same
    name is a very common pattern in WeeWX.
2.  We need a separate color table for each unit group that we are going
    to support. This is the start of the table for unit group
    `group_temperature`.
3.  We need to specify what unit system will be used by the temperature
    color table. In this example, we are using `metricwx`.
4.  In case we do not find a value in the table, we need a default. We
    will use the color `tomato`.
5.  In case the value is Python `None`, return the color given by option
    `None`. We will use `lightgray`.
6.  The sub-subsecction `[[[upper_bounds]]]` lists the
    upper (max) value of each of the color bands.
7.  The first color band (magenta) is used for temperatures less than or
    equal to -10°C.
8.  The second band (violet) is for temperatures greater than -10°C and
    less than or equal to 0°C. And so on.
9.  The next subsection, `[[group_uv]]`, is very similar to
    the one for `group_temperature`, except the values are for
    bands of the UV index.

Although `[Colorize]` is in `skin.conf`, there is
nothing special about it, and it can be overridden in
`weewx.conf`, just like any other configuration information.

#### Annotated code

Here's the alternative version of `colorize()`, which will use
the values in the configuration file. It can also be found in
`examples/colorize/colorize_3.py`.

``` python
import weewx.units
from weewx.cheetahgenerator import SearchList

class Colorize(SearchList):                                               # 1

    def __init__(self, generator):                                        # 2
        SearchList.__init__(self, generator)
        self.color_tables = self.generator.skin_dict.get('Colorize', {})

    def colorize(self, value_vh):

        # Get the ValueTuple and unit group from the incoming ValueHelper
        value_vt = value_vh.value_t                                       # 3
        unit_group = value_vt.group                                       # 4

        # Make sure unit_group is in the color table, and that the table
        # specifies a unit system.
        if unit_group not in self.color_tables \
                or 'unit_system' not in self.color_tables[unit_group]:    # 5
            return "#00000000"

        # Convert the value to the same unit used by the color table:
        unit_system = self.color_tables[unit_group]['unit_system']        # 6
        converted_vt = weewx.units.convertStdName(value_vt, unit_system)  # 7

        # Check for a value of None
        if converted_vt.value is None:                                    # 8
            return self.color_tables[unit_group].get('none') \
                   or self.color_tables[unit_group].get('None', "#00000000")

        # Search for the value in the color table:
        for upper_bound in self.color_tables[unit_group]['upper_bounds']: # 9
            if converted_vt.value <= float(upper_bound):                  # 10
                return self.color_tables[unit_group]['upper_bounds'][upper_bound]

        return self.color_tables[unit_group].get('default', "#00000000")  # 11
```

1.  As before, our class must inherit from `SearchList`.

2.  In this version, we supply an initializer because we are going to do
    some work in it: extract our color table out of the skin
    configuration dictionary. In case the user neglects to include a
    `[Colorize]` section, we substitute an empty dictionary.

3.  As before, we extract the `ValueTuple` part out of the
    incoming `ValueHelper` using the attribute `value_t`.

4.  Retrieve the unit group used by the incoming argument. This will be
    something like "group_temperature".

5.  What if the user is requesting a color for a unit group that we
    don't know anything about? We must check that the unit group is in
    our color table. We must also check that a unit system has been
    supplied for the color table. If either of these checks fail, then
    return the color `#00000000`, which will have no effect in
    setting a background color.

6.  Thanks to the checks we did in step 5, we know that this line will
    not raise a `KeyError` exception. Get the unit system used by
    the color table for this unit group. It will be something like
    'US', 'metric', or 'metricwx'.

7.  Convert the incoming value, so it uses the same units as the color
    table.

8.  We must always be vigilant for values of Python None! The expression

    ``` python
    self.color_tables[unit_group].get('none') or self.color_tables[unit_group].get('None', "#00000000")
    ```

    is just a trick to allow us to accept either "`none`" or
    "`None`" in the configuration file. If neither is present,
    then we return the color `#00000000`, which will have no
    effect.

9.  Now start searching the color table to find a band that is less than
    or equal to the value we have in hand.

10. Two details to note.

    First, the variable `converted_vt` is a `ValueTuple`.
    We need the raw value in order to do the comparison. We get this
    through attribute `.value`.

    Second, WeeWX uses the utility `ConfigObj` to read
    configuration files. When `ConfigObj` returns its results,
    the values will be *strings*. We must convert these to floats before
    doing the comparison. You must be constantly vigilant about this
    when working with configuration information.

    If we find a band with an upper bound greater than our value, we
    have a hit. Return the corresponding color.

11. If we make it all the way through the table without a hit, then we
    must have a value greater than anything in the table. Return the
    default, or the color `#00000000` if there is no default.
