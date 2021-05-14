# To do

Right now, there are so many overrides specified in the `[StdReport]/[[Defaults]]` 
section that `skin.conf` has little influence. Consider commenting many of them out.

Along the same line, the new I18N strategy does not depend on them at all. Consider
deleting them.

Review the I18N documentation.

Modify installation software so the user can pick a unit system.

Parameterize PIL fonts on the basis of `lang`.

Allow downloading and memoizing fonts, so we don't have to ship every font out there.
