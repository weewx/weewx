The extension installer no longer patches incoming skins. Does the documentation
need to be changed to reflect this?

Do we want to move the following options from `[StdReport]` to `[StdReport][Defaults]`?
  * `SKIN_ROOT`
  * `HTML_ROOT`
  * `data_binding`

Comments needed in `weewx.conf` for `[[Defaults]]` section

need to ensure that these use cases work properly:
- override SLE in a skin from weewx.conf (and other cheetahgenerator options)
- override imagegenerator options from weewx.conf (e.g., add cmon to exfoliation)

need to document the two primary i18n/l10n use cases:
1) end-user wants to translate existing skin (change defaults, lang)
2) skin author wants to distribute skin with multiple languages
also be sure that weewx actually supports these cases properly.
are there other use cases?

Can we use `weecfg.prompt_with_options()` in place of `weeutil.weeutil.y_or_n()`?
