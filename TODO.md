# To do

Right now, there are so many overrides specified in the `[StdReport]/[[Defaults]]` 
section that `skin.conf` has little influence. Consider commenting many of them out.

Along the same line, the new I18N strategy does not depend on them at all. Consider
deleting them.

Update the documentation. I think the I18N sections still use `gettext()` rather than
`gettext[]`.

Update the test suites to use `lang` and `units`.

