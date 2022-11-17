# To do

## For the poetry implementation

Applications need to be converted into poetry scripts.

What to do with `weewx.conf` and the skins? 
- Cannot access them as package data using `importlib.resources` because package data is supposed 
to be readonly. So, even if the user was willing to find them deep in the virtual environment, 
s/he could not edit them. 
- Have to move them to some place where they are writable.

So, what's the final resting point? `~/.weewx`

Think about namespaces. Problem areas:
- Package `user`
- Package `schemas`