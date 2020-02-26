# To do

Check whether `weewx.accum.setup()` is really necessary. I think even dynamic
imports get done only once.

Right now, if a user is doing software record generation, record augmentation 
from the accumulators gets done twice: once in the software catch up,
then again in `StdArchive.new_archive_record()`.

Need to add `python3-distutils` to the required package list in `debian/control`.

# For Version 4.1
Implement a `$gettext()` extension.