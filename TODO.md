# To do

When doing `setup.py` installs, some Python 2 installations may have to install `setuptools`
first.

Invoke `wee_config` from `setup.py`.

Remove default calculations from `[StdWXCalculate]`. Instead, they must be
listed in `weewx.conf`. 

Swallow any exceptions that occur in `RainRater._setup()`

Right now, if a user is doing software record generation, record augmentation 
from the accumulators gets done twice: once in the software catch up,
then again in `StdArchive.new_archive_record()`.

Need to add `python3-distutils` to the required package list in `debian/control`.

# For Version 4.1
Implement a `$gettext()` extension.