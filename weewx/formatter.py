#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Views into scalar data, and a formatter to format them."""

import time

class ModelView(object):
    """A view into an hierarchical data model.
    
    Much of the HTML rendering logic depends on this class. Given a
    hierarchical data model consisting of dictionaries and attributes,
    this class offers views into it, using introspection. The views
    are through a formatter object. The views are created on the fly,
    on demand. Thus the model can change without changing any state in
    the view. It does this by creating itself recursively, as it goes
    down the model, root to leaf node. When it finally hits an integer
    or float, it stops and invokes the formatter.
    
    For example, given a model such as:
        data = {}
        data['year'] = {}
        data['year']['outTemp'] = {}
        data['year']['outTemp']['min'] = 45.88
        data['year']['outTemp']['max'] = 55.298
    
    Then a ModelView can be constructed into it, using a formatter:
    
        formatter = weewx.html.Formatter({'outTemp' : '%.1f'}, 
                                         {'outTemp' : " Fahrenheit"}, None)
        dataView = ModelView(data, formatter)
    
        print data['year']['outTemp']['min']     # Prints 45.88
        print dataView['year']['outTemp']['min'] # Prints "45.9 Fahrenheit"

    Note that data['year']['outTemp']['min'] returns a *float* of value 45.88,
    (which print then converts into a string), while the view offers a formatted view, 
    returning a *string*."""
    def __init__(self, model, formatter, context = ()):
        """Initialize an instance of ModelView.
        
        model: The hierarchical model to be viewed.
        
        formatter: An instance of weewx.html.Formatter, or something that looks like it.
        
        context: Contains the accumulating context as ModelView creates 
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
        v = self.model.__getitem__(key)
        # If we made it this far, the model does have key 'key'.
        # Is it a scalar?
        if v is None or type(v) in (float, int):
            # Yes, it is. Format it and return the string.
            str = self.formatter.format(v, self.context + (key,))
            return str
        # It's not a scalar. Create a new instance recursively:
        return ModelView(v, self.formatter, self.context + (key,))
    
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
        v = self.model.__getattribute__(attr)

        # If we made it this far, the model does have attribute 'attr'.
        # Is it a scalar?
        if v is None or type(v) in (float, int) :
            # Yes, it is. Format it and return the string.
            str = self.formatter.format(v, self.context + (attr,))
            return str
        # It's not a scalar. Create a new instance recursively:
        return ModelView(v, self.formatter, self.context + (attr,))
    
    
class Formatter(object):
    """Formatter to be used to convert a value to a string, given a context."""
    def __init__(self, value_format_dict, unit_label_dict, time_format_dict):
        """Initialize an instance of Formatter.
        
        value_label_dict: A dictionary with key of a type, value of a format to be
        used to format that type. Example: {'outTemp' : '%0.1f', 'barometer' : '%0.3f'}
        
        unit_label_dict: A dictionary with the unit label to be used for a type.
        Example: {'outTemp' : '&deg;F', 'barometer': 'inHg'}
        
        time_format_dict: A dictionary with strftime type formats, to be used to format
        any times encountered. The key is a time period ('day', 'week', 'current', etc.)
        and the value is a strftime format that should be used to format that time. 
        Example: {'day' : '%H:%M', 'current' : '%d-%b-%Y %H:%M', 'week' : '%H:%M on %A'}
        The key is usually extracted from the node closest to the root. Hence, a template
        reference such as $week.outTemp.min will use the format keyed by 'week'.
        
        """
        self.value_format_dict = value_format_dict
        self.unit_label_dict   = unit_label_dict
        self.time_format_dict  = time_format_dict
        
    def format(self, v, context):
        """Format the value v in the context context.
        
        v: The value to be formatted. If no suitable format can be found, 
        the value itself will be returned.
        
        context: A tuple with the context of the value.  An example
        context would be ('year', 'barometer', 'max'). The algorithm
        searches backwards down the context ('max', 'barometer',
        'year' in this case), looking for something it can format.
        
        returns formatted version of v
        """
        # Walk backwards through the context tuple, looking
        # for something we recognize and can format:
        for _key in context[::-1]:
            # Is it a date?
            if _key in ('mintime', 'maxtime', 'time', 'dateTime'):
                # Format as a date/time.  If the context is 3 elements
                # long, it's probably something like
                # month.outTemp.min. If it's 2 elements long, it's
                # probably something like current.outTemp.  Based on
                # its length, pick the right time format ('month', or
                # 'current', respectively, in this example).
                _format_key = context[-3] if len(context)>=3 else context[-2]
                return time.strftime(self.time_format_dict[_format_key], time.localtime(v))
            else:
                # Not a date. Is it in one of the other dictionaries?
                if self.value_format_dict.has_key(_key) or self.unit_label_dict.has_key(_key):
                    # It is. Format as a number
                    if v is None :
                        return "N/A"
                    try:
                        val_str   = self.value_format_dict.get(_key, '%f') % v
                    except TypeError:
                        val_str = str(v)
                    label_str = self.unit_label_dict.get(_key, '')
                    return (val_str + label_str).decode('string_escape').decode('latin1')
        # Don't know how to format it. Just return it as is
        return v
