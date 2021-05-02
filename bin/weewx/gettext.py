# Simple localization for WeeWX
# Copyright (C) 2021 Johanna Karen Roedenbeck

#    See the file LICENSE.txt for your full rights.

"""
  provides tag $gettext
  
  Language dependent texts are stored in special localization files.
  The are merged into skin_dict in reportengine.py according to the
  language the user chooses in weewx.conf for the given report. 
  Different reports can be in different languages.
  
  The file defines language dependent label texts as well as other
  texts used in skins. 
  
  The values provided by $gettext are found in the file
  in the [Texts] section. Subsections in the [Texts] section can
  provide special texts for certain templates.

  Examples:
  
  Assume the localization file to be:
  
  [Texts]
    Key1 = Text1
    [[index]]
      Title = Text2
    [[othertemplate]]
      Title = Text3
  
  With that file is:
  
  $gettext["Key1"]           ==> Text1
  
  $gettext[$page]["Title"]    ==> is Text2 if included in template "index"
                                 and Text3 if included in template 
                                 "othertemplate"
                                
  You can use "speaking" key names. If they contain whitespace they need
  to be enclosed in quotes in the localization file
  
  If the value contains commas you must enclose it in single or double
  quotes. Otherwise an array instead of a string is returned.
  
"""

from six.moves import collections_abc
from weewx.cheetahgenerator import SearchList
import six
import logging

log = logging.getLogger(__name__)


class Gettext(SearchList):

    def get_extension_list(self, timespan, db_lookup):
        text_dict = self.generator.skin_dict.get('Texts', {'lang': 'en'})
        gettext = ParallelDict(text_dict)
        return [{'gettext': gettext}]


class ParallelDict(collections_abc.Mapping):
    """This class holds another dictionary internally. When keyed, it returns the value in
    the other dictionary. However, if the key is missing, then it returns the key."""

    # Some of the complexity below is to guard against the following scenario:
    #
    #    p = ParallelDict({})
    #    p["page"]["Some text"]
    #
    # We want it to return "Some text", but it will return a TypeError("string indices must be
    # integers")
    #

    def __init__(self, source):
        self.source = source

    def __getitem__(self, key):
        """Return value for the key. If the key is missing, return the key"""
        try:
            return self.source[key]
        except KeyError:
            # KeyError. Return a ParallelDict with the key. The key can then be retrieved by
            # using __str__().
            return ParallelDict(key)
        except TypeError:
            # source is something other than a dict. If it's a string, return it. Otherwise,
            # let the exception propagate upwards.
            if not isinstance(self.source, six.string_types):
                log.error("ParallelDict source ('%s') is not a string", self.source)
                raise
            return key

    def __len__(self):
        return self.source.__len__()

    def __iter__(self):
        for key in self.source:
            yield key

    def __str__(self):
        return str(self.source)
