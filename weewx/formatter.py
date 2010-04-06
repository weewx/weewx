#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Views into a tree like model, and a formatter to format them.

This module probably contains the most hard core Python code in the
whole system.
"""

import time
import types
import weewx
import weewx.units

#===============================================================================
#                             class ModelFormatter
#===============================================================================

class ModelFormatter(object):
    """A view into an hierarchical data model.
    
    Much of the template rendering logic depends on this class. Given a
    hierarchical data model consisting of dictionaries and attributes,
    this class offers views into it, using introspection. The views
    are through a formatter object. The views are created on the fly,
    on demand. Thus the model can change without changing any state in
    the view. It does this by creating itself recursively, as it goes
    down the model, root to leaf node. When a primitive such as an int,
    float, or string is encountered, it is assumed that we are at the
    leaf note, and the ModelFormatter stops and invokes the formatter.
    
    For example, given a model such as:
        data = {}
        data['year'] = {}
        data['year']['outTemp'] = {}
        data['year']['outTemp']['min'] = 45.88
        data['year']['outTemp']['max'] = 55.298
    
    Then a ModelFormatter can be constructed into it, using a formatter:

        formatter = Formatter({'outTemp' : '%.1f'}, 
                              {'outTemp' : " Fahrenheit"},
                              None)
        dataView = ModelFormatter(data, formatter)
    
        print data['year']['outTemp']['min']     # Prints 45.88
        print dataView['year']['outTemp']['min'] # Prints "45.9 Fahrenheit"

    Note that data['year']['outTemp']['min'] returns a *float* of value 45.88,
    (which print then converts into a string), while the ModelFormatter
    offers a formatted view, returning a *string*."""
    def __init__(self, model, formatter, context = ()):
        """Initialize an instance of ModelFormatter.
        
        model: The hierarchical model to be viewed.
        
        formatter: An instance of weewx.formatter.Formatter.
        
        context: Contains the accumulating context as ModelFormatter creates 
        itself recursively. 
        """
        self.model     = model
        self.formatter = formatter
        self.context   = context
        
    def __getitem__(self, key):
        """Query the underlying model if it has the key 'key'.
        
        If it does, return a formatted version of the value. 
        If it does not, throw exception 'KeyError'
        """
        # This will raise a KeyError exception if the model
        # does not support the key 'key':
        v = self.model[key]

        # If we made it this far, the model does have key 'key'.
        # Is it a primitive?
        if type(v) in (int, float, str, types.NoneType):
            # It is. We're done. Return a wrapper that will format it as requested:
            return ModelObjectFormatter(v, self.formatter, self.context +(key,))
        
        # Not a primitive. Did the model return a generator type? 
        elif isinstance(v, types.GeneratorType):
            # It did. Wrap it in a ModelGeneratorFormatter. 
            # Unfortunately, we do not have access to
            # whatever variable the results of the generator expression is being
            # bound to, so we kludge up a context. If the key that triggered the
            # the return of the generator ends in s, then the context is that
            # key up to the 's'. This turns 'days' to 'day', 'months' to 'month',
            # etc. It's not general, but it will work within the context of weewx.
            if weewx.debug:
                assert(key[-1] == 's')
            return ModelGeneratorFormatter(v, self.formatter, (key[:-1],))

        # Not a generator type. Did the model return an instance method? 
        elif isinstance(v, types.MethodType):
            # It is an instance method. Wrap it in a call formatter before returning it:
            return ModelCallFormatter(v, self.formatter, self.context + (key,))

        # Don't know what it is. Hopefully, we're at an internal node of the tree,
        # and subsequent calls will work us down to a leaf. 
        # Create a new instance recursively, adding the key to the context:
        return ModelFormatter(v, self.formatter, self.context + (key,))
    
    def __getattr__(self, attr):
        """Query the underlying model if it has the attribute 'attr'.
        
        If it does, return a formatted version of the value of the attribute.
        if it does not, throw exception 'AttributeError'.
        """
        # We override __getattr__ (instead of __getattribute__)
        # because with the latter, if we didn't find the attribute in
        # the model, we'd have to pass the request on to the
        # superclass's __getattribute__, to see whether it can handle
        # it, requiring us to set up an exception block
        
        # This will raise an AttributeError exception if the model
        # does not support the attribute 'attr':
        v = getattr(self.model, attr)

        # If we made it this far, the model does have attribute 'attr'.
        # Is it a primitive?
        if type(v) in (int, float, str, types.NoneType):
            # It is. We're done. Return a wrapper that will format it as requested:
            return ModelObjectFormatter(v, self.formatter, self.context +(attr,))
        
        # Not a primitive. Did the model return a generator type? 
        elif isinstance(v, types.GeneratorType):
            # It did. Wrap it in a ModelGeneratorFormatter. 
            # Unfortunately, we do not have access to
            # whatever variable the results of the generator expression is being
            # bound to, so we kludge up a context. If the key that triggered the
            # the return of the generator ends in s, then the context is that
            # key up to the 's'. This turns 'days' to 'day', 'months' to 'month',
            # etc. It's not general, but it will work within the context of weewx.
            if weewx.debug:
                assert(attr[-1] == 's')
            return ModelGeneratorFormatter(v, self.formatter, (attr[:-1],))
        
        # Not a generator type. Did the model return an instance method? 
        elif isinstance(v, types.MethodType):
            # It is an instance method. Wrap it in a call formatter before returning it:
            return ModelCallFormatter(v, self.formatter, self.context + (attr,))

        # Don't know what it is. Hopefully, we're at an internal node of the tree,
        # and subsequent calls will work us down to a leaf. 
        # Create a new instance recursively, adding the key to the context:
        return ModelFormatter(v, self.formatter, self.context + (attr,))
    
#===============================================================================
#                             class ModelGeneratorFormatter
#===============================================================================

class ModelGeneratorFormatter(object):
    """Wraps a generator object in a formatter.
    
    The presence of an __iter__ method is what makes this object iterable."""
    def __init__(self, model_generator, formatter, context):
        self.model_generator = model_generator
        self.formatter       = formatter
        self.context         = context
        
    def __iter__(self):
        # This is a common idiom with Python: Iterators return themselves when
        # asked for an iterator:
        return ModelGeneratorFormatter(self.model_generator, self.formatter, self.context)
        
    def next(self):
        """Return the next item"""
        try:
            # Ask my model for the next item:
            x = self.model_generator.next()
            
            # Is the results a primitive?
            if type(x) in (int, float, str, types.NoneType):
                # Yes. Wrap it in a ModelObjectFormatter:
                return ModelObjectFormatter(x, self.formatter, self.context)
            else:
                # No. Wrap it in a ModelFormatter so the recursion can continue
                return ModelFormatter(x, self.formatter, self.context)
        except StopIteration:
            raise
      
#===============================================================================
#                             class ModelCallFormatter
#===============================================================================

class ModelCallFormatter(object):
    """Wraps an instance method in a formatter."""
    def __init__(self, model_call, formatter, context):
        self.model_call = model_call
        self.formatter  = formatter
        self.context    = context
        
    def __call__(self, *args):
        """The client is invoking the instance method"""

        # Invoke the call on the model, with the given arguments:
        x = self.model_call(*args)

        # Is the results a primitive?
        if type(x) in (int, float, str, types.NoneType):
            # Yes. Wrap it in a ModelObjectFormatter:
            return ModelObjectFormatter(x, self.formatter, self.context)
        else:
            # No. Wrap it in a ModelFormatter so the recursion can continue
            return ModelFormatter(x, self.formatter, self.context)
          
#===============================================================================
#                             class ModelObjectFormatter
#===============================================================================

class ModelObjectFormatter(object):
    """Wraps a primitive type (int, float, string) in a formatter."""
    
    def __init__(self, model, formatter, context):
#        print "making ModelObjectFormatter ", model, context
        self.model     = model
        self.formatter = formatter
        self.context   = context
        
    def __str__(self):
        """Return a formatted version of the model value with a label. """
        res = self.formatter.format(self.model, self.context)
        return res
    
    @property
    def raw(self):
        """Return a raw version of the underlying model.
        
        The raw version does not apply any formatting."""
        return self.model
    
    @property
    def formatted(self):
        """Return a formatted version of the model, but with no label."""
        res = self.formatter.format(self.model, self.context, False)
        return res
    
    def format(self, format_string, NONE_string = None):
        """Return a formatted version of the model, using a user-supplied format."""
        res = self.formatter.format(self.model, self.context, False, format_string, NONE_string)
        return res
    
    def string(self, NONE_string = None):
        if self.model is None:
            return self.formatter.format(self.model, self.context, None_string = NONE_string)
        else:
            return str(self.model)
        
#===============================================================================
#                             class Formatter
#===============================================================================

class Formatter(object):
    """Formatter to be used to convert a value to a string, given a context."""
    def __init__(self, unit_format_dict, unit_label_dict, time_format_dict):
        """Initialize an instance of Formatter.
        
        unit_format_dict: A dictionary with key of a unit type, value a string format
        
          Example: {'mbar' : '%0.1f', 'inHg' : '%0.3f'}
        
        unit_label_dict: A dictionary with key of a unit type, value a unit label
        
          Example: {'degree_F' : '&deg;F', 'inHg': 'inHg'}
        
        time_format_dict: A dictionary with key a time period ('day', 'week', 
        'current', etc.), value a strftime format that should be used to format 
        that period. 
        
          Example: {'day' : '%H:%M', 'current' : '%d-%b-%Y %H:%M', 'week' : '%H:%M on %A'}"""
          
        self.unit_format_dict  = unit_format_dict
        self.unit_label_dict   = unit_label_dict
        self.time_format_dict  = time_format_dict
        
    def format(self, v, context, addLabel = True, useThisFormat = None, None_string = None):
        """Format the value v in the context context.
        
        v: The value to be formatted.
        
        context: A tuple with the context of the value.  An example
        context would be ('year', 'barometer', 'max'). The first
        position is always the time period, the second always the type.
        The optional third position is something like 'max' or 'maxtime.'
        
        addLabel: True to add a label (such as 'feet') to the returned value.
                  False otherwise.
                  
        useThisFormat: If not None, use this format to do the formatting. The
        dictionary unit_format_dict supplied in the initializer is ignored.
        
        None_string: Use this string if the value is None. An example would
        be "N/A". If set to None, retrieve the string from the unit label dictionary.
        
        returns formatted version of v
        """

        # Figure out what the value is.
        
        # Is it a None value?
        if v is None :
            return None_string if None_string else self.unit_format_dict.get('NONE', 'N/A')

        # Is it a date?
        elif context[-1] in ('mintime', 'maxtime', 'time', 'dateTime'):
            # The last tag is 'time' related. Format as a date/time.
            # The first context element will be the time period, something like
            # 'current' or 'month'. This will be the key into the time format dictionary. 
            _format = self.time_format_dict[context[0]] if not useThisFormat else useThisFormat
            return time.strftime(_format, time.localtime(v))

        # Is it a count of some kind? 
        elif context[-1] in ('count', 'max_ge', 'max_le', 'min_le', 'sum_ge'):
            # It is. Format as an int by simply converting to a string:
            return str(v)
        
        else:
            _type = context[-1] if context[-1] in ('vecdir', 'gustdir') else context[1]
            # Try formatting it. If we get a TypeError the format is for the wrong type 
            # (eg, an integer format being used to format a float). If we get a KeyError, there is
            # no format in the format dictionary for the type.
            try:
                if useThisFormat:
                    val_str = useThisFormat % v
                else:
                    val_str   = self.unit_format_dict[_type] % v
            except (TypeError, KeyError):
                # Don't know how to format it. Explicitly convert to a string:
                val_str = str(v)
            
            # Add the (optional) label and return
            if addLabel:
                val_str += self.unit_label_dict.get(_type, '') 
    
            return val_str


#===============================================================================
#                            Testing routines
#===============================================================================


if __name__ == '__main__':

    def testValueFormatting(skin_dict):
        val = weewx.std_unit_system.Value(22.0, 'degree_C')

        value_formatter = ValueFormatter(skin_dict['Units']['Groups'])
        print value_formatter.toString(val)

        value_formatter = ValueFormatter.fromSkinDict(skin_dict)
        print value_formatter.toString(val)
        
        print value_formatter.toString(weewx.std_unit_system.Value(None, 'degree_C'))
        


    
    def testFormatting(config_dict):
            
        unitTypeDict         = {'outTemp' : 'degree_F'}
        unitStringFormatDict = {'outTemp' : "%.2f"}
        unitLabelDict        = {'outTemp' : ' degrees F'}    # No degree sign in order to avoid introducing UTF-8
        timeLabelDict        = {'day'     : "%H:%M",
                                'week'    : "%H:%M on %A",
                                'month'   : "%d-%b-%Y %H:%M",
                                'year'    : "%d-%b-%Y %H:%M",
                                'current' : "%d-%b-%Y %H:%M"} 

        statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                     config_dict['Stats']['stats_file'])

        statsDb = weewx.stats.StatsReadonlyDb(statsFilename, 65.0, 65.0)

        end_tt =   (2010,  1, 1, 0, 0, 0, 0, 0, -1)

        tagStats = weewx.stats.TaggedStats(statsDb, time.mktime(end_tt), unitTypeDict)
        print "Temperature minimum; unformatted output: ", tagStats.month.outTemp.min
        print "Temperature mintime; unformatted output: ", tagStats.month.outTemp.mintime
        print "Days w/max temp over 90.0:               ", tagStats.month.outTemp.max_ge(90.0)
        formatter =  Formatter(unitStringFormatDict,
                               unitLabelDict,
                               timeLabelDict)

        # Get a formatted view into the statistical information.
        tagStatsFormatted = ModelFormatter(tagStats, formatter)
        print tagStatsFormatted.month.outTemp.min
        print tagStatsFormatted.month.outTemp.mintime
        print tagStatsFormatted.month.outTemp.max_ge(90.0)
        print tagStatsFormatted.month.outTemp.count
        print tagStatsFormatted.month.outTemp.count.raw

        for day in tagStatsFormatted.month.days:
            print "            ********"
            print "Date:                               ", day.dateTime.format("%d-%m-%y")
            print "Start of day:                       ", day.dateTime
            print "Start of day   raw:                 ", day.dateTime.raw
            print "Day's mintime, formatted & labeled: ", day.outTemp.mintime
            print "Day's min,     formatted & labeled: ", day.outTemp.min
            print "Day's mintime, raw                : ", day.outTemp.mintime.raw
            print "Day's min,     raw                : ", day.outTemp.min.raw
            print "Day's mintime, formatted          : ", day.outTemp.mintime.formatted
            print "Day's min,     formatted          : ", day.outTemp.min.formatted
            

    import configobj
    import os.path
    import sys
    
    import weewx.stats

    if len(sys.argv) < 2 :
        print "Usage: stats.py path-to-configuration-file"
        exit()
        
    weewx.debug = 1
    config_path = sys.argv[1]
    try :
        config_dict = configobj.ConfigObj(config_path, file_error=True)
    except IOError:
        print "Unable to open configuration file ", config_path
        raise
#    testFormatting(config_dict)

    skin_path = os.path.join(config_dict['Reports']['SKIN_ROOT'],
                             'Standard/skin.conf')
    try :
        skin_dict = configobj.ConfigObj(skin_path, file_error=True)
    except IOError:
        print "Unable to open skin configuration file ", skin_path
        raise

    testValueFormatting(skin_dict)
