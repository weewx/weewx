# To do

Doing `wee_database --reweight` effectively upgrades to Version 2 of the daily
summaries.

Some of the aggregations in xtypes.py could be made a little more efficient. Particularly
those with two SELECT statements.

Should Ultimeter driver actually emit `rain24` and `dayRain`? See
this email thread: https://groups.google.com/forum/#!topic/weewx-user/FM9QANjo1cc

# For Version 4.1
Implement a `$gettext()` extension.

Be able to add arbitrary lines to graphics.
