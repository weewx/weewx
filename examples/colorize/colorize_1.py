#    Copyright (c) 2022 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.

"""Pick a color on the basis of a temperature. Simple, hardwired version.

*******************************************************************************

This search list extension offers an extra tag:

    'colorize': Returns a color depending on a temperature measured in Celsius.

*******************************************************************************

To use this search list extension:

1) Copy this file to the user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the option search_list_extensions in the skin.conf configuration file, adding
the name of this extension.  When you're done, it will look something like this:

    [CheetahGenerator]
        search_list_extensions = user.colorize_1.Colorize

You can then colorize backgrounds. For example, to colorize an HTML table cell:

<table>
  <tr>
    <td>Outside temperature</td>
    <td style="background-color:$colorize($current.outTemp.raw)">$current.outTemp</td>
  </tr>
</table>

*******************************************************************************
"""

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
            return "moccasin"
        elif t_c < 30:
            return "yellow"
        elif t_c < 40:
            return "coral"
        else:
            return "tomato"
