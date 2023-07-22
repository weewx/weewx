# Class ValueHelper

Class `ValueHelper` contains all the information necessary to do
the proper formatting of a value, including a unit label.

### Instance attribute

#### ValueHelper.value_t

Returns the `ValueTuple` instance held internally.

### Instance methods

#### ValueHelper.__str__()

Formats the value as a string, including a unit label, and returns it.

#### ValueHelper.format(format_string=None, None_string=None, add_label=True, localize=True)

Format the value as a string, using various specified options, and
return it. Unless otherwise specified, a label is included.

Its parameters:

- `format_string` A string to be used for formatting. It must
include one, and only one, [format
specifier](https://docs.python.org/3/library/string.html#formatspec).

- `None_string` In the event of a value of Python `None`, this string
will be substituted. If `None`, then a default string from
`skin.conf` will be used.

- `add_label` If truthy, then an appropriate unit label will be
attached. Otherwise, no label is attached.

- `localize` If truthy, then the results will be localized. For
example, in some locales, a comma will be used as the decimal specifier.
