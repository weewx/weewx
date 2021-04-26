# Simple localization for WeeWX
# Copyright (C) 2021 Johanna Karen Roedenbeck

#    See the file LICENSE.txt for your full rights.

"""
  provides tag $gettext(key, page)
  
  Language dependent texts are stored in special localization files.
  The are merged into skin_dict in reportengine.py according to the
  language the user chooses in weewx.conf for the given report. 
  Different reports can be in different languages.
  
  The file defines language dependent label texts as well as other
  texts used in skins. 
  
  The values provided by $gettext(key, page) are found in the file
  in the [Texts] section. Subsections in the [Texts] section can
  provide special texts for certain templates. To get values from
  subsections $gettext() is called with special tag $page for the
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
  
  $gettext("Key1")           ==> Text1
  
  $gettext("Title",$page)    ==> is Text2 if included in template "index"
                                 and Text3 if included in template 
                                 "othertemplate"
                                
  $gettext(page=$page).Title ==> same as before
  
  You can use "speaking" key names. If they contain whitespace they need
  to be enclosed in quotes in the localization file
  
  If the value contains commas you must enclose it in single or double
  quotes. Otherwise an array instead of a string is returned.
  
"""

from weewx.cheetahgenerator import SearchList

# Test for new-style weewx v4 logging by trying to import weeutil.logger
import weeutil.logger
import logging

log = logging.getLogger(__name__)


class Gettext(SearchList):

    def __init__(self,generator):
        """Create an instance of the class"""
        super(Gettext,self).__init__(generator)
        
        # get the set language code
        # (needed for things like <html lang="...">
        self.lang = self.generator.skin_dict.get('lang','undefined')
        _idx = self.lang.rfind('/')
        if _idx>=0:
            self.lang = self.lang[_idx+1:]
        _idx = self.lang.rfind('.conf')
        if _idx>=0:
            self.lang = self.lang[:_idx]
        
        
    def get_extension_list(self,timespan,db_lookup):
            
        def locale_label(key='',page=''):
            """ $gettext()
            
                key: key to look up for
                page: section name  
                
            """
            _text_dict = self.generator.skin_dict.get('Texts',{})

            # get the appropriate section for page if defined
            # Note: no hierarchy here
            if page:
                if not page in _text_dict:
                    log.error("could not find section [Texts][[%s]] for report %s" % (page,self.generator.skin_dict.get('REPORT_NAME','unknown')))
                # Note: no 'else:' here, because we need the empty dict
                # page is specified --> get subsection "page"
                _text_dict = _text_dict.get(page,{})
                # if the result is not a dict, make it a dict
                if not isinstance(_text_dict,dict):
                    _text_dict={page:_text_dict}
            
            # if key is not empty, get the value for key
            if key:
            
                if key in _text_dict:
                    # key is in dict _text_dict --> return value of key
                    val = _text_dict[key]
                else:
                    # otherwise return key as value
                    val = key
                
                return val
        
            # if key is empty but page is not return further class instance
            if page:
                cheetah_dict={}
                cheetah_dict_key = 'CheetahGenerator'
                if "FileGenerator" in self.generator.skin_dict and 'CheetahGenerator' not in self.generator.skin_dict:
                    cheetah_dict_key = "FileGenerator"
                if cheetah_dict_key in self.generator.skin_dict:
                    cheetah_dict = Gettext._get_cheetah_dict(self.generator.skin_dict[cheetah_dict_key],page)
                return FilesBinder(page,_text_dict,self.generator.skin_dict.get('Labels',{}).get('Generic',{}),cheetah_dict)
                
            # if key as well as page are empty
            return FilesBinder('N/A',_text_dict,{},{'lang':self.lang})
            
        return [{'gettext':locale_label}]

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


class FilesBinder(object):
    """ special labels for a specific page to be created by Cheetah """

    def __init__(self,page,lang_files_dict,skin_labels_dict,cheetah_dict):
        self.page=page
        self.lang_files_dict=lang_files_dict
        self.skin_labels_dict=skin_labels_dict
        self.cheetah_dict=cheetah_dict
        
    def __getattr__(self,attr):
        if attr in self.lang_files_dict:
            # entry found in localization file
            return self.lang_files_dict[attr]
        elif attr in self.cheetah_dict:
            # entry found [CheetahGenerator] subsection
            return self.cheetah_dict[attr]
        elif attr=='nav':
            # if $gettext(page='xxx').nav not in localization file, try 
            # nav_xxx in [Labels][[Generic]] section of skin.conf
            # helpful for extending Belchertown skin
            if 'nav_'+self.page in self.skin_labels_dict:
                return self.skin_labels_dict['nav_'+self.page]
        elif attr=='page_header':
            # if $gettext(page='xxx').page_header not in localization file, 
            # try xxx_page_header in [Labels][[Generic]] section of skin.conf
            # helpful for extending Belchertown skin
            x=self.page+'_page_header'
            if x in self.skin_labels_dict:
                return self.skin_labels_dict[x]
        elif attr in self.skin_labels_dict:
            # finally look in [Labels][[Generic]] section if skin.conf
            return str(self.skin_labels_dict[attr])
        return '$%s.%s' % (self.page,attr)

            
