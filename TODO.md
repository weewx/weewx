### Tests

Synthetic database used for tests: some of the types require the database, but it's not available until
after the transaction. Need to either go back later and patch in the derived types, or make them
available outside the database. Or, give up the idea of calculating them.

`gen_fake_data.py` is now more realistic, but the expected results haven't caught back up to it yet.

### Xtypes
Allow expressions in aggregates.

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