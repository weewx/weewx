# [SummaryImageGenerator]

This section is used by generator `weewx.summaryimage.SummaryImageGenerator` and
controls a single PNG holding the current readings as text. It is meant for
sharing: a forum post, an email signature, or anywhere a page cannot be linked.

The image is not a chart. It is the numbers, laid out in columns, with the
station name and the time they were taken.

#### enable

Whether to draw the image at all. Default is `False`.

#### filename

Where to write it, relative to `HTML_ROOT`. Default is `current.png`.

#### observations

Comma separated list of the observation types to show, in the order they are to
appear. Four to six fit comfortably. Default is
`outTemp, windSpeed, rain, barometer`.

A type the station does not record is left out.

#### width

The width of the image in pixels. Default is `900`.

#### columns

How many readings to a row. Default is `2`.

#### scale

Render at this multiple, then downsample. `2` is sharp on a phone screen at the
cost of four times the pixels. Default is `2`.

#### background_color

The background of the image. Default is `#ffffff`.

#### title_color

The colour of the station name. Default is `#16222e`.

#### value_color

The colour of the readings themselves. Default is `#16222e`.

#### label_color

The colour of the labels beside them. Default is `#8397a7`.

#### sub_color

The colour of the smaller text under a reading, such as the time. Default is
`#55666f`.

#### rule_color

The colour of the lines between the rows. Default is `#dbe4ec`.

#### *_font_path

Where to find a TrueType font, relative to the skin directory. There is one for
each role: `title_font_path`, `value_font_path`, `label_font_path` and
`sub_font_path`.

A missing font falls back to the one built into PIL, which cannot draw accented
characters, so keep these pointing at a real font on a station whose language
needs them.

#### *_font_size

The size of each of those fonts, in points before `scale` is applied.
