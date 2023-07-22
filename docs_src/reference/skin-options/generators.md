# [Generators]

This section defines the list of generators that should be run.

#### generator_list

This option controls which generators get run for this skin. It is a
comma separated list. The generators will be run in this order.

For example, the Standard skin uses three generators: `CheetahGenerator`,
`ImageGenerator`, and `CopyGenerator`. Here is the `[Generators]` section
from the Standard `skin.conf`

``` ini
[Generators]
    generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.imagegenerator.ImageGenerator, weewx.reportengine.CopyGenerator
```
