### Install
Note in the docs that doing:
```shell script
python3 setup.py install
```
will cause the shebang at the top of the executables to use Python 3:
```python
#!/usr/bin/python3
# ...
```
Basically, however you invoke `setup.py` is what will be injected.

Update suse.htm for how to install using Python 3.

### Other
Really have to find some way of making `accumulateLeaves()` and friends accessible
from `weeutil.weeutil`.

Check `weedb` tests against later versions of MySQL. In particular, 8.0.