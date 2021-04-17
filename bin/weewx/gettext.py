# Simple localization for WeeWX
# Copyright (C) 2021 Johanna Roedenbeck

from weewx.cheetahgenerator import SearchList
from weewx.units import ValueTuple,ValueHelper
import configobj
import weeutil.weeutil
import weeutil.config
import os
import os.path

try:
    # Test for new-style weewx v4 logging by trying to import weeutil.logger
    import weeutil.logger
    import logging

    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'gettext: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


class Gettext(SearchList):

    def __init__(self,generator):
        """Create an instance of the class"""
        super(Gettext,self).__init__(generator)
        

    def get_extension_list(self,timespan,db_lookup):
            
        def locale_label(key='',page=''):
            """ $gettext()
            
                key: key to look up for
                page: section name  
                
            """
            d=self.generator.skin_dict

            # get the appropriate section for page
            try:
                if 'Templates' in d:
                    sec = 'Templates'
                elif 'Texts' in d:
                    sec = 'Texts'
                else:
                    raise KeyError
                if page:
                    d = d[sec][page]
                    if not isinstance(d,dict):
                        d={page:d}
                else:
                    d = d[sec]
            except (KeyError,IndexError,ValueError,TypeError):
                d = {}
                    
            if key:
            
                if key in d:
                    val = d[key]
                else:
                    val = key
                
                return val
        
            if page:
                cheetah_dict={}
                if 'CheetahGenerator' in self.generator.skin_dict:
                    if page in self.generator.skin_dict['CheetahGenerator']:
                        cheetah_dict = self.generator.skin_dict['CheetahGenerator'][page]

                # 
                return FilesBinder(page,d,self.generator.skin_dict['Labels']['Generic'] if 'Generic' in self.generator.skin_dict else {},cheetah_dict)
                
        return [{'gettext':locale_label}]


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
            # if $locale(file='xxx').nav not in localization file, try 
            # nav_xxx in [Labels][[Generic]] section of skin.conf
            if 'nav_'+self.page in self.skin_labels_dict:
                return self.skin_labels_dict['nav_'+self.page]
        elif attr=='page_header':
            # if $locale(file='xxx').page_header not in localization file, 
            # try xxx_page_header in [Labels][[Generic]] section of skin.conf
            x=self.page+'_page_header'
            if x in self.skin_labels_dict:
                return self.skin_labels_dict[x]
        elif attr in self.skin_labels_dict:
            # finally look in [Labels][[Generic]] section if skin.conf
            #if attr=='html_description':
            #   loginf("html_description: %s" % self.skin_labels_dict[attr])
            return str(self.skin_labels_dict[attr])
        return '$%s.%s' % (self.page,attr)

            
