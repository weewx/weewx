The following drivers have been checked under Python 3:

```
vantage.py
wmr100.py
```

Figured so long as we were using jquery-ui for the TOC generator, we might as well
use it for tabs. This makes adding sub-tabs much easier.

Transitioned the `setup.htm` document to use jquery-ui for its tabs. This involved
the following changes:
* A slightly different WeeWX CSS file, `weewx_ui.css` (instead of the old `weewx_docs.css`)
* For styling, it uses CSS (and js) from the subdirectory `jquery-ui-1.12.1.custom`. 
It no longer uses the stuff in `css/ui-lightness`.
* More modern version of jQuery: `jquery-3.3.1.min.js` (instead of `jquery-1.11.1.min.js`)

The other documents should be transitioned to this scheme. Then the following could be
deleted:
* `css/ui-lightness` subdirectory
* `css/weewx_docs.css`
* `js/jquery-1.11.1.min.js`
* `js/jquery-ui-1.10.4.custom.min`

In general, we should expect the user to run the command `python`, whatever that might
point to. On some systems, it will be Python 2, others Python 3.

Nevertheless, we should probably include a section on how to run explicitly under 
Python 2 vs 3.