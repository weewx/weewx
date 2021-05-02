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

#from six.moves import collections_abc
from weewx.cheetahgenerator import SearchList
from weeutil.weeutil import KeyDict
import weeutil.config

# Test for new-style weewx v4 logging by trying to import weeutil.logger
import weeutil.logger
import logging

log = logging.getLogger(__name__)


class Gettext(SearchList):

    def __init__(self,generator):
        """Create an instance of the class"""
        super(Gettext,self).__init__(generator)

        # new version with _deep_copy_to_keydict
        
        # copy section [Text] and convert all subsections to KeyDict
        # in order to return key instead of generating an error in
        # case key does not exist
        self.text_dict = Gettext._deep_copy_to_keydict(self.generator.skin_dict.get('Texts',weeutil.config.config_from_str('')))
        # merge template definitions into page dependent subsections
        Gettext._merge_cheetah_dict(self.text_dict,self.generator.skin_dict.get('CheetahGenerator',weeutil.config.config_from_str('')),None)

    def get_extension_list(self,timespan,db_lookup):
        
        # new version with _deep_copy_to_keydict: nothing else to do here
        return [{'gettext':self.text_dict}]

        # original version commented out
        '''
        def locale_label(key='',page=''):
            """ $gettext()
            
                key: key to look up for
                page: section name  
                
            """
            _text_dict = self.generator.skin_dict.get('Texts',{})

            # get the appropriate section for page if defined
            # Note: no hierarchy here
            if page:
                if page not in _text_dict:
                    log.error("could not find section [Texts][[%s]] for report %s" % (page,self.generator.skin_dict.get('REPORT_NAME','unknown')))
                # Note: no 'else:' here, because we need the empty dict
                # page is specified --> get subsection "page"
                _text_dict = _text_dict.get(page,{})
            
            # if key is not empty, get the value for key
            if key:
                # return the value for key
                # if key not in _text_dict return key instead
                return KeyDict(_text_dict)[key]
                

            # if key is empty but page is not return further class instance
            if page:
                _page_dict = weeutil.config.config_from_str('')
                merge_dict = Gettext._get_cheetah_dict(self.generator.skin_dict.get('CheetahGenerator',{}),page)
                if merge_dict:
                    weeutil.config.merge_config(_page_dict,merge_dict)
                weeutil.config.merge_config(_page_dict,_text_dict)
                return _page_dict
                
            # if key as well as page are empty
            return ParallelDict(_text_dict)
            
        return [{'gettext':locale_label}]
        '''

    # original version, not used in new version
    '''
    @staticmethod
    def _get_cheetah_dict(cheetah_dict,page):
        """ find section page in cheetah_dict recursively """
    
        for section in cheetah_dict.sections:
            subsection = Gettext._get_cheetah_dict(cheetah_dict[section],page)
            if subsection is not None:
                return subsection
        if page in cheetah_dict:
            return cheetah_dict[page]
        return None
    '''
    
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
    
    @staticmethod
    def _merge_cheetah_dict(text_dict, cheetah_dict, section):
        """ merge [CheetahGenerator] into text_dict 
            flatten structure
        """
        # if this section describes a template, copy entries
        if section and 'template' in cheetah_dict:
            # create section 'section' in text_dict if not already there
            if section not in text_dict:
                text_dict[section] = KeyDict({})
            # copy entries
            for scalar in cheetah_dict.scalars:
                text_dict[section][scalar] = cheetah_dict[scalar]
            # filename to be created
            text_dict[section]['filename'] = cheetah_dict['template'].replace('.tmpl','')
        # if there are subsections read them
        for section in cheetah_dict.sections:
            Gettext._merge_cheetah_dict(text_dict, cheetah_dict[section],section)

# TODO: Determine difference between ParallelDict and KeyDict

'''
class ParallelDict(collections_abc.Mapping):

    def __init__(self, source):
        self.source = source

    def __getitem__(self, key):
        try:
            return self.source[key]
        except KeyError:
            return key

    def __len__(self):
        return self.source.__len__()

    def __iter__(self):
        for key in self.source:
            yield key
'''
