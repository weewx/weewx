#
#    Copyright (c) 2018-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Convenience functions for ConfigObj"""

from __future__ import absolute_import

import configobj
from configobj import Section


def search_up(d, k, *default):
    """Search a ConfigObj dictionary for a key. If it's not found, try my parent, and so on
    to the root.

    d: An instance of configobj.Section

    k: A key to be searched for. If not found in d, it's parent will be searched

    default: If the key is not found, then the default is returned. If no default is given,
    then an AttributeError exception is raised.

    Example:

    >>> c = configobj.ConfigObj({"color":"blue", "size":10, "robin":{"color":"red", "sound": {"volume": "loud"}}})
    >>> print(search_up(c['robin'], 'size'))
    10
    >>> print(search_up(c, 'color'))
    blue
    >>> print(search_up(c['robin'], 'color'))
    red
    >>> print(search_up(c['robin'], 'flavor', 'salty'))
    salty
    >>> try:
    ...   print(search_up(c['robin'], 'flavor'))
    ... except AttributeError:
    ...   print('not found')
    not found
    >>> print(search_up(c['robin'], 'sound'))
    {'volume': 'loud'}
    >>> print(search_up(c['robin'], 'smell', {}))
    {}
    """
    if k in d:
        return d[k]
    if d.parent is d:
        if len(default):
            return default[0]
        else:
            raise AttributeError(k)
    else:
        return search_up(d.parent, k, *default)


def accumulateLeaves(d, max_level=99):
    """Merges leaf options above a ConfigObj section with itself, accumulating the results.

    This routine is useful for specifying defaults near the root node,
    then having them overridden in the leaf nodes of a ConfigObj.

    d: instance of a configobj.Section (i.e., a section of a ConfigObj)

    Returns: a dictionary with all the accumulated scalars, up to max_level deep,
    going upwards

    Example: Supply a default color=blue, size=10. The section "dayimage" overrides the former:

    >>> c = configobj.ConfigObj({"color":"blue", "size":10, "dayimage":{"color":"red", "position":{"x":20, "y":30}}})
    >>> accumulateLeaves(c["dayimage"]) == {"color":"red", "size": 10}
    True
    >>> accumulateLeaves(c["dayimage"], max_level=0) == {'color': 'red'}
    True
    >>> accumulateLeaves(c["dayimage"]["position"]) == {'color': 'red', 'size': 10, 'y': 30, 'x': 20}
    True
    >>> accumulateLeaves(c["dayimage"]["position"], max_level=1) == {'color': 'red', 'y': 30, 'x': 20}
    True
    """

    # Use recursion. If I am the root object, then there is nothing above
    # me to accumulate. Start with a virgin ConfigObj
    if d.parent is d:
        cum_dict = configobj.ConfigObj()
    else:
        if max_level:
            # Otherwise, recursively accumulate scalars above me
            cum_dict = accumulateLeaves(d.parent, max_level - 1)
        else:
            cum_dict = configobj.ConfigObj()

    # Now merge my scalars into the results:
    merge_dict = {}
    for k in d.scalars:
        merge_dict[k] = d[k]
    cum_dict.merge(merge_dict)
    return cum_dict


def merge_config(self_config, indict):
    """Merge and patch a config file"""

    self_config.merge(indict)
    patch_config(self_config, indict)


def patch_config(self_config, indict):
    """The ConfigObj merge does not transfer over parentage, nor comments. This function
    fixes these limitations.

    Example:
    >>> import sys
    >>> c = ConfigObj(StringIO('''[Section1]
    ... option1 = bar'''))
    >>> d = ConfigObj(StringIO('''[Section1]
    ...     # This is a Section2 comment
    ...     [[Section2]]
    ...     option2 = foo
    ... '''))
    >>> c.merge(d)
    >>> # First do accumulateLeaves without a patch
    >>> print(accumulateLeaves(c['Section1']['Section2']))
    {'option2': 'foo'}
    >>> # Now patch and try again
    >>> patch_config(c, d)
    >>> print(accumulateLeaves(c['Section1']['Section2']))
    {'option1': 'bar', 'option2': 'foo'}
    >>> c.write()
    ['[Section1]', 'option1 = bar', '# This is a Section2 comment', '[[Section2]]', 'option2 = foo']
    """
    for key in self_config:
        if isinstance(self_config[key], Section) \
                and key in indict and isinstance(indict[key], Section):
            self_config[key].parent = self_config
            self_config[key].main = self_config.main
            self_config.comments[key] = indict.comments[key]
            self_config.inline_comments[key] = indict.inline_comments[key]
            patch_config(self_config[key], indict[key])


def comment_scalar(a_dict, key):
    """Comment out a scalar in a ConfigObj object.

    Convert an entry into a comment, sticking it at the beginning of the section.

    Returns: 0 if nothing was done.
             1 if the ConfigObj object was changed.
    """

    # If the key is not in the list of scalars there is no need to do anything.
    if key not in a_dict.scalars:
        return 0

    # Save the old comments
    comment = a_dict.comments[key]
    inline_comment = a_dict.inline_comments[key]
    if inline_comment is None:
        inline_comment = ''
    # Build a new inline comment holding the key and value, as well as the old inline comment
    new_inline_comment = "%s = %s %s" % (key, a_dict[key], inline_comment)

    # Delete the old key
    del a_dict[key]

    # If that was the only key, there's no place to put the comments. Do nothing.
    if len(a_dict.scalars):
        # Otherwise, put the comments before the first entry
        first_key = a_dict.scalars[0]
        a_dict.comments[first_key] += comment
        a_dict.comments[first_key].append(new_inline_comment)

    return 1


def delete_scalar(a_dict, key):
    """Delete a scalar in a ConfigObj object.

    Returns: 0 if nothing was done.
             1 if the scalar was deleted
    """

    if key not in a_dict.scalars:
        return 0

    del a_dict[key]
    return 1


def conditional_merge(a_dict, b_dict):
    """Merge fields from b_dict into a_dict, but only if they do not yet
    exist in a_dict"""
    # Go through each key in b_dict
    for k in b_dict:
        if isinstance(b_dict[k], dict):
            if k not in a_dict:
                # It's a new section. Initialize it...
                a_dict[k] = {}
                # ... and transfer over the section comments, if available
                try:
                    a_dict.comments[k] = b_dict.comments[k]
                except AttributeError:
                    pass
            conditional_merge(a_dict[k], b_dict[k])
        elif k not in a_dict:
            # It's a scalar. Transfer over the value...
            a_dict[k] = b_dict[k]
            # ... then its comments, if available:
            try:
                a_dict.comments[k] = b_dict.comments[k]
            except AttributeError:
                pass


def config_from_str(input_str):
    """Return a ConfigObj from a string. Values will be in Unicode."""
    import six
    from six import StringIO
    # This is a bit of a hack. We want to return a ConfigObj with unicode values. Under Python 2,
    # ConfigObj v5 requires a unicode input string, but earlier versions require a
    # byte-string.
    if configobj.__version__ >= '5.0.0':
        # Convert to unicode
        open_str = six.ensure_text(input_str)
    else:
        open_str = input_str
    config = configobj.ConfigObj(StringIO(open_str), encoding='utf-8', default_encoding='utf-8')
    return config
