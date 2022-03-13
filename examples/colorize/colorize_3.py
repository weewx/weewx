#    Copyright (c) 2022 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.

"""Pick a color on the basis of a value. This version uses information from
the skin configuration file.

*******************************************************************************

This search list extension offers an extra tag:

    'colorize': Returns a color depending on a value

*******************************************************************************

To use this search list extension:

1) Copy this file to the user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the option search_list_extensions in the skin.conf configuration file, adding
the name of this extension.  When you're done, it will look something like this:

    [CheetahGenerator]
        search_list_extensions = user.colorize_3.Colorize

3) Add a section [Colorize] to skin.conf. For example, this version would
allow you to colorize both temperature and UV values:

    [Colorize]
        [[group_temperature]]
            unit_system = metricwx
            default = tomato
            None = lightgray
            [[[upper_bounds]]]
                -10 = magenta
                0 = violet
                10 = lavender
                20 = moccasin
                30 = yellow
                40 = coral
        [[group_uv]]
            unit_system = metricwx
            default = darkviolet
            [[[upper_bounds]]]
                2.4 = limegreen
                5.4 = yellow
                7.4 = orange
                10.4 = red

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

class Colorize(SearchList):                                               # 1

    def __init__(self, generator):                                        # 2
        SearchList.__init__(self, generator)
        self.color_tables = self.generator.skin_dict.get('Colorize', {})

    def colorize(self, value_vh):
        """
        Pick a color on the basis of a value. The color table will be obtained
        from the configuration file.

        Args:
            value_vh (ValueHelper): The value, represented as ValueHelper.

        Returns:
            str: A color string.
        """

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
