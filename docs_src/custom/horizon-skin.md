# Theming the Horizon skin

The Horizon skin draws its charts in the browser, but its look is settled before that,
in CSS custom properties. Everything you see is one of them: the surfaces, the type
sizes, the corner radius, the colours the charts read for their grid and axes.

Any of them can be overridden from `skin.conf`, so restyling the skin is a change to
your configuration and not to a file that the next upgrade will overwrite.

## How it works

Under `[DisplayOptions]`:

``` ini
[DisplayOptions]
    [[Theme]]
        [[[Light]]]
            accent  = "#7a4b2c"
            bg      = "#faf6f2"
            radius  = 2px
            font    = Georgia, "Times New Roman", serif
        [[[Dark]]]
            accent  = "#d8a77a"
            bg      = "#1a1512"
```

There is no fixed list of names. Whatever you write becomes `--name`, so anything
`horizon.css` defines can be replaced, and nothing else is emitted. `[[[Light]]]`
applies everywhere; `[[[Dark]]]` overrides it where the reader's browser or the theme
toggle asks for a dark page.

## What there is

| Name | What it colours |
|---|---|
| `bg`, `surface`, `surface-sunk` | the page, the cards, inset areas |
| `ink`, `ink-muted`, `ink-faint` | body text, labels, captions |
| `border`, `border-strong` | card edges, table rules |
| `accent`, `accent-bright` | links, the active tab |
| `hi`, `lo`, `ok`, `warn` | highs, lows, good and warning states |
| `chart-grid`, `chart-axis`, `chart-night` | inside the charts, read by `horizon.js` |
| `radius`, `gap`, `shadow` | corners, the space between cards, card shadow |
| `font` | the stack for the whole page |
| `fs-xs` … `fs-huge` | type sizes, from the small print to the headline figure |

The chart *line* colours are not here. They come from `chart_line_colors` in
`[ImageGenerator]`, where the PNGs take them too, so a chart and the image of the same
plot stay the same colour.

## When the names are not enough

Name a stylesheet of your own:

``` ini
[DisplayOptions]
    custom_css = my-station.css
```

It is loaded after `horizon.css` and after `[[Theme]]`, so it wins over both. Put the
file in the skin directory and add it to `copy_once` in `[CopyGenerator]`, or it will
not be installed.
