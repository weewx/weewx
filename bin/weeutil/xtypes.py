#
#    Copyright (c) 2009-2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined, extended types"""
from __future__ import print_function

import itertools

import six


class ExtendedTypes(dict):
    """Acts like a dict, except it can virtually calculate new types"""

    def __init__(self, record, new_types={}):
        """Initialize an instance of ExtendedTypes.

        record: A dictionary.

        new_types: A dictionary. Key is a new type, its value is a function that will
        calculate the type. Its form must be func(key, record), where record will be the
        record above.

        Returns:
            If the key exists in new_types, then the calculated value is returned.
            If it does not, then the key in record is returned. In this sense, the
            calculated value always takes precedence.

        Example:

            et = ExtendedType({'a':1, 'b':4}, {'c': lambda k, rec: rec['a']+rec['b']})

        In this example, they key 'c' will return a value that is the sum of a and b:

            et['a'] == 1
            et['b'] == 4
            et['c'] == 5
        """
        # Initialize my super class...
        super(ExtendedTypes, self).__init__(record)
        # ... then a dictionary of new types.
        self.new_types = new_types

    def __len__(self):
        return dict.__len__(self) + len(self.new_types)

    def __iter__(self):
        # Chain together my superclass's iterator, and an iterator over the new types
        return itertools.chain(dict.__iter__(self), iter(self.new_types))

    def __getitem__(self, key):
        if key in self.new_types:
            return self.new_types[key](key, self)
        return dict.__getitem__(self, key)

    def __delitem__(self, key):
        if key in self.new_types:
            del self.new_types[key]
        else:
            dict.__delitem__(self, key)

    def __contains__(self, key):
        return key in self.new_types or dict.__contains__(self, key)

    def keys(self):
        return itertools.chain(self.new_types.keys(), dict.keys(self))

    def items(self):
        return itertools.chain(self.new_types.items().dict.items(self))

    def iteritems(self):
        return itertools.chain(six.iteritems(self.new_types), six.iteritems(super(ExtendedTypes, self)))

    def iterkeys(self):
        return itertools.chain(self.new_types.iterkeys(), dict.iterkeys(self))

    def itervalues(self):
        return itertools.chain(self.new_types.itervalues(), dict.itervalues(self))

    def values(self):
        raise NotImplementedError

    def get(self, key, default=None):
        if key in self.new_types:
            return self.new_types[key](key, self)
        return dict.get(self, key, default)
