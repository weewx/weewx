#    Copyright (c) 2022 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.

"""Pick a color on the basis of a temperature. This version works for any unit system.

*******************************************************************************

This search list extension offers an extra tag:

    'colorize': Returns a color depending on temperature

*******************************************************************************

To use this search list extension:

1) Copy this file to the user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the option search_list_extensions in the skin.conf configuration file, adding
the name of this extension.  When you're done, it will look something like this:

    [CheetahGenerator]
        search_list_extensions = user.colorize_2.Colorize

You can then colorize backgrounds. For example, to colorize an HTML table cell:

<table>
  <tr>
    <td>Outside temperature</td>
    <td style="background-color:$colorize($current.outTemp)">$current.outTemp</td>
  </tr>
</table>

*******************************************************************************
"""
import weewx.units
from weewx.cheetahgenerator import SearchList


class Colorize(SearchList):                                          # 1

    def colorize(self, value_vh):                                    # 2
        """
        Choose a color on the basis of a temperature value in any unit.

        Args:
            value_vh (ValueHelper): The temperature, represented as a ValueHelper

        Returns:
            str: A color string
        """

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
            return "moccasin"
        elif t_c < 30:
            return "yellow"
        elif t_c < 40:
            return "coral"
        else:
            return "tomato"
