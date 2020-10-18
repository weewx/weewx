# To do

In order to calculate derived types, `weecfg.database` instantiates `weewx.wxservices.WXCalculate`,
which no longer exists. As a result, the test suites won't run.

Should Ultimeter driver actually emit `rain24` and `dayRain`? See
this email thread: https://groups.google.com/forum/#!topic/weewx-user/FM9QANjo1cc

# For Version 4.1
Implement a `$gettext()` extension.

Be able to add arbitrary lines to graphics.
