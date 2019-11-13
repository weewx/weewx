### Extensible types
Test accumulators with String accumulator, as well as with string types.

Write `TestWXCalculate`
 - Test `windrun`
 - Test `ET` (should not be calculated for LOOP packets)

### Logging
Refactor `wee_import` to use the new logging facility.

Update *Upgrading Guide*.


### Issue [#435](https://github.com/weewx/weewx/issues/435) (Update WU uploader)
Need to test some of the new types, in particular `windSpeed2`, `windGust10`,
`windGustDir10`.


### Other
Really have to find some way of making `accumulateLeaves()` and friends accessible
from `weeutil.weeutil`.

Document the suffixes `.exists` and `.has_data`.

Update macos.htm for how to install using Python 3.

Update redhat.htm for how to install using Python 3.

Update suse.htm for how to install using Python 3.