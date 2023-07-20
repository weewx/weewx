# [Labels]

This section defines various labels.

#### hemispheres

Comma separated list for the labels to be used for the four hemispheres.
The default is `N, S, E, W`.

#### latlon_formats

Comma separated list for the formatting to be used when converting
latitude and longitude to strings. There should be three elements:

1.  The format to be used for whole degrees of latitude
2.  The format to be used for whole degrees of longitude
3.  The format to be used for minutes.

This allows you to decide whether you want leading zeroes. The
default includes leading zeroes and is `"%02d", "%03d", "%05.2f"`.

## [[Generic]]

This section specifies default labels to be used for each
observation type. For example, options

``` ini
inTemp  = Temperature inside the house
outTemp = Outside Temperature
UV      = UV Index
```

would cause the given labels to be used for plots of `inTemp` and
`outTemp`. If no option is given, then the observation type
itself will be used (*e.g.*, `outTemp`).
