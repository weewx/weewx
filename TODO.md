# To do

## For the poetry implementation

Applications need to be converted into poetry scripts.

Function `prompt_for_info()`, and all other functions that manipulation `stn_info` go away.

Tests for `prompt_for_info()` go away.

Make sure distutil isn't used anywhere. E.g., distutils.copytree().
