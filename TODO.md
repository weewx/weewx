The extension installer no longer patches incoming skins. Does the documentation
need to be changed to reflect this?


need to ensure that these use cases work properly:
- override SLE in a skin from weewx.conf (and other cheetahgenerator options)
- override imagegenerator options from weewx.conf (e.g., add cmon to exfoliation)


need to revisit precedence order (sorry!:/):

Existing: hard-coded, report_name/skin.conf, [StdReport][[report_name]]

option 1: hard-coded, [Defaults], [StdReport][[report_name]], report_name/skin.conf

option 2: hard-coded, report_name/skin.conf, [Defaults], [StdReport][[report_name]]


need to document the two primary i18n/l10n use cases:
1) end-user wants to translate existing skin (change defaults, lang)
2) skin author wants to distribute skin with multiple languages
also be sure that weewx actually supports these cases properly.
are there other use cases?
