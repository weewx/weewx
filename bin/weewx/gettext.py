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

  The values provided by $gettext[] are found in the file
  in the [Texts] section. Subsections in the [Texts] section can
  provide special texts for certain templates. To get values from
  subsections $gettext[$page][] is called with special tag $page for the
  parameter page. That is especially useful in include files that
  are included in multiple templates.

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

  $gettext[$page]["Title"]   ==> is Text2 if included in template "index"
                                 and Text3 if included in template
                                 "othertemplate"

  $gettext[$page].Title      ==> same as before

  You can use "speaking" key names. If they contain whitespace they need
  to be enclosed in quotes in the localization file

  If the value contains commas you must enclose it in single or double
  quotes. Otherwise an array instead of a string is returned.

"""

from weewx.cheetahgenerator import SearchList
import weeutil.config
from weeutil.weeutil import KeyDict

import logging

log = logging.getLogger(__name__)


class Gettext(SearchList):

    def get_extension_list(self, timespan, db_lookup):
        # copy section [Text] and convert all subsections to KeyDict
        # in order to return key instead of generating an error in
        # case key does not exist
        return [{'gettext': Gettext._deep_copy_to_keydict(
            self.generator.skin_dict.get('Texts', weeutil.config.config_from_str('lang = en')))}]

    @staticmethod
    def _deep_copy_to_keydict(text_dict):
        """ convert configObj to KeyDict including subsections """
        _dict = KeyDict({})
        # process subsections
        for section in text_dict.sections:
            _dict[section] = Gettext._deep_copy_to_keydict(text_dict[section])
        # copy entries of this section
        for scalar in text_dict.scalars:
            _dict[scalar] = text_dict[scalar]
        # return result
        return _dict
