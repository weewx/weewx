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
import os
import os.path
import sys

class ModuleExtensionLoader(object):
    """Manipulates a module."""

    def __init__(self, module_name):
        """Import a module by name."""
        self.module_name = module_name
        __import__(module_name)
        self.module = sys.modules[module_name]

    def discover_classes(self, superclass):
        """Discover all classes in a module that are the subclass of a given superclass.
        
        superclass: All strict subclasses within the module will be returned.
        
        returns:
        A list of tuples (symname, Cls) where symname is a symbolic name and Cls is a 
        class object.
        """

        _mems = []
        # Get all the entries in the module:
        for _name, _Cls in inspect.getmembers(self.module):
            # Find all entries that are a strict subclass of the superclass:
            if inspect.isclass(_Cls) and issubclass(_Cls, superclass) and _Cls != superclass:
                # Retrieve a symbolic name for the class. If not found, use the class name
                _symname = _Cls.symname if hasattr(_Cls, 'symname') else _name
                _mems.append((_symname, _Cls))
        return _mems

class DirectoryExtensionLoader(object):
    """Manipulates modules found in a directory."""

    def __init__(self, dir_name):
        """Loads all the modules found in a directory."""
        # Get all the files found in the directory.
        _files = os.listdir(dir_name)
        # Because listdir() returns a list in arbitrary order, sort it.
        _files.sort()

        self.module_list = []

        # Go through all the files that were found
        for _file in _files:
            # Get the full path for each file:
            _file_path = os.path.join(dir_name, _file)
            # Follow any symbolic links:
            _real_path = os.path.realpath(_file_path)
            # Make sure it's a real file (not a directory):
            if os.path.isfile(_real_path):
                # Split out the suffix
                _file_info = os.path.splitext(os.path.basename(_real_path))
                # Accept only those files with a suffix ".py" or no suffix at all:
                if _file_info[1] in [".py", '']:
                    # Massage the path so that the module can be found, saving the
                    # old path first
                    _old_path = list(sys.path)
                    sys.path.append(os.path.dirname(_real_path))
                    # Add the retrieved module to the list of modules
                    self.module_list.append(ModuleExtensionLoader(_file_info[0]))
                    sys.path = _old_path

    def discover_classes(self, superclass):
        """Discover all classes in a directory that are the subclass of a given superclass.
        
        superclass: All strict subclasses within the modules will be returned.
        
        returns:
        A list of tuples (symname, Cls) where symname is a symbolic name and Cls is a 
        class object.
        """

        _mems = []
        # Go through all the modules in the list.
        for _module in self.module_list:
            # For each module, find all subclasses of the given superclass
            for _symname, _Cls in _module.discover_classes(superclass):
                # Add any that were found to the list
                _mems.append((_symname, _Cls))

        return _mems

