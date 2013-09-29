#
#    Copyright (c) 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Routines for the weewx extension facilities."""

import inspect
import sys
import os
import os.path

class ModuleExtensionLoader(object):
    
    def __init__(self, module_name):
        
        self.module_name = module_name
        __import__(module_name)
        self.module = sys.modules[module_name]
        
    def discover_classes(self, superclass):

        _mems = []       
        for _name, _Cls in inspect.getmembers(self.module):
            if inspect.isclass(_Cls) and issubclass(_Cls, superclass) and _Cls != superclass:
                _symname = _Cls.symname if hasattr(_Cls, 'symname') else _name
                _mems.append((_symname, _Cls))
        
        _mems.sort(key=lambda x:x[1], reverse=False)
        return _mems

class DirectoryExtensionLoader(object):
    
    def __init__(self, dir_name):
        
        old_path = list(sys.path)
        sys.path.append(dir_name)
        
        self.module_list = []
        for _file in os.listdir(dir_name):
            if os.path.isfile(os.path.join(dir_name, _file)):
                _file_info = os.path.splitext(_file)
                if _file_info[1] == ".py":
                    self.module_list.append(ModuleExtensionLoader(_file_info[0]))
            
        sys.path = old_path
            
    def discover_classes(self, superclass):
        
        _mem_set = set()
        for _module in self.module_list:
            for _symname, _Cls in _module.discover_classes(superclass):
                _mem_set.add((_symname, _Cls))
                
        _mems = list(_mem_set)
        _mems.sort(key=lambda x:x[1], reverse=False)
        return _mems

