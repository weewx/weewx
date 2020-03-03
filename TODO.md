# To do

It appears that the package `mysql-client` is not available on Raspbian.
See https://groups.google.com/d/msg/weewx-development/oTbkjEwC_aQ/wQ124PC6AgAJ

If the engine restarts, user changes to `weewx.accum.accum_dict` do not
get reapplied. The culprit may be `weewx.accum.setup()`. Not convinced
calling it is necessary on a restart.

Right now, if a user is doing software record generation, record augmentation 
from the accumulators gets done twice: once in the software catch up,
then again in `StdArchive.new_archive_record()`.

Need to add `python3-distutils` to the required package list in `debian/control`.

# For Version 4.1
Implement a `$gettext()` extension.