# [Texts]

The section `[Texts]` holds static texts that are used in the
templates. Generally there are multiple language files, one for each
supported language, named by the language codes defined in
[ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
The entries give the translation of the texts to the target language.
For example,

``` ini
[Texts]
    "Current Conditions" = "Aktuelle Werte"
```

would cause "Aktuelle Werte" to be used whereever `$gettext("Current
Conditions"` appeared. See the section on
[`$gettext`](../../custom/cheetah-generator.md#gettext-internationalization).

!!! Note
    Strings that include commas must be included in single or double quotes.
    Otherwise, they will be misinterpreted as a list.
