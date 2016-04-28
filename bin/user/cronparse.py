import calendar
import datetime
import time

# spans of valid values for each field
MINUTES = (0, 59)
HOURS = (0, 23)
DOM = (1, 31)
MONTHS = (1, 12)
DOW = (0, 6)
# day names
DAY_NAMES = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')
# month names
MONTH_NAMES = ('jan', 'feb', 'mar', 'apr', 'may', 'jun',
               'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
# map month names to month number
MONTH_NAME_MAP = zip(('jan', 'feb', 'mar', 'apr',
                      'may', 'jun', 'jul', 'aug',
                      'sep', 'oct', 'nov', 'dec'), xrange(1, 13))
# map day names to day number
DAY_NAME_MAP = zip(('sun', 'mon', 'tue', 'wed',
                    'thu', 'fri', 'sat'), xrange(7))
# map nicknames to equivalent CRON like line
NICKNAME_MAP = {
    "@yearly": "0 0 1 1 *",
    "@anually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@hourly": "0 * * * *"
}
# Spans
SPANS = (MINUTES, HOURS, DOM, MONTHS, DOW)
# Names
NAMES = ((), (), (), MONTH_NAMES, DAY_NAMES)
# Maps
MAPS = ((), (), (), MONTH_NAME_MAP, DAY_NAME_MAP)

class ReportCron(object):
    """Class for processing a CRON like line and determining whether it should
    be fired for a given time.

    The following CRON like capabilities are supported:
    - There are two ways to specify the day the line is fired, DOM and DOW. A
      match on either all other fields and either DOM or DOW will casue the
      line to be fired.
    - first-last, *. Matches all possible values for the field concerned.
    - step, /x. Matches every xth minute/hour/day etc. May be bounded by a list
      or range.
    - range, lo-hi. Matches all values from lo to hi inclusive. Ranges using
      month and day names are not supported.
    - lists, x,y,z. Matches those items in the list. List items may be a range.
      Lists using month and day names are not supported.
    - month names. Months may be specified by number 1..12 or first 3 (case
      insensitive) letters of the English month name jan..dec.
    - weekday names. Weekday names may be specified by number 0..7
      (0,7 = Sunday) or first 3 (case insensitive) letters of the English
      weekday names sun..sat.
    - nicknames. Following nicknames are supported:
        @yearly   : Run once a year,  ie "0 0 1 1 *"
        @annually : Run once a year,  ie "0 0 1 1 *"
        @monthly  : Run once a month, ie "0 0 1 * *"
        @weekly   : Run once a week,  ie "0 0 * * 0"
        @daily    : Run once a day,   ie "0 0 * * *"
        @hourly   : Run once an hour, ie "0 * * * *"

    Useful ReportCron class attributes:

    is_valid:         Whether passed line is a valid line or not.
    validation_error: Error message if passed line is an invalid line.
    raw_line:         Raw line data passed to ReportCron.
    line:             5 item list representing the 5 date/time fields after the
                      raw line has been processed and dom/dow named parameters
                      replaced with numeric equivalents.
    """

    def __init__(self, line):
        """Initialises a ReportCron object.

        Processes raw line to produce 5 field line suitable for further
        processing.

        line:  The raw line to be processed.
        """

        # initialise some properties
        self.is_valid = None
        self.validation_error = None
        self.raw_line = line.strip()
        # do some basic checking of the line for unsupported characters
        for unsupported_char in ('%', '#', 'L', 'W'):
            if unsupported_char in line:
                self.is_valid = False
                self.validation_error = "Unsupported character '%s' in '%s'." % (unsupported_char,
                                                                                 line)
                return
        # six special time defintion 'nicknames' are supported which replace
        # the line elements with pre-detemined values. These nicknames start
        # with the @ character. Check for any of these nicknames and substitute
        # the corresponding line.
        for nickname, nn_line in NICKNAME_MAP.iteritems():
            if line == nickname:
                line = nn_line
                break
        fields = line.split(None, 5)
        if len(fields) < 5:
            # Not enough fields
            self.is_valid = False
            self.validation_error = "Insufficient fields found in '%s'" % line
            return
        elif len(fields) == 5:
            fields.append(None)
        # Extract individual line elements
        minutes, hours, dom, months, dow, extra = fields
        # Save individual fields
        self.line = [minutes, hours, dom, months, dow]
        # Is DOM restricted ie is DOM not '*'
        self.dom_restrict = self.line[2] != '*'
        # Is DOW restricted ie is DOW not '*'
        self.dow_restrict = self.line[4] != '*'
        # Decode the line and generate a set of possible values for each field
        (self.is_valid, self.validation_error) = self.decode()

    def decode(self):
        """Decode each field and store the sets of valid values.

        Set of valid values is stored in self.decode. Self.decode can only be
        considered valid if self.is_valid is True. Returns a 2-way tuple
        (True|False, ERROR MESSAGE). First item is True is the line is valid
        otherwise False. ERROR MESSAGE is None if the line is valid otherwise a
        string containing a short error message.
        """

        # set a list to hold our decoded ranges
        self.decode = []
        try:
            # step through each field and its associated range, names and maps
            for field, span, names, map in zip(self.line, SPANS, NAMES, MAPS):
                field_set = self.parse_field(field, span, names, map)
                self.decode.append(field_set)
            # if we are this far then our line is valid so return True and no
            # error message
            return (True, None)
        except ValueError, e:
            # we picked up a ValueError in self.parse_field() so return False
            # and the error message
            return (False, e)

    def parse_field(self, field, span, names, map, is_rorl=False):
        """Return the set of valid values for a field.

        Parses and validates a field and if the field is valid returns a set
        containing all of the possible field values. Called recursively to
        parse sub-fields (eg lists of ranges). If a field is invalid a
        ValueError is raised.

        field:   String containing the raw field to be parsed.
        span:    Tuple representing the lower and upper numeric values the
                 field may take. Format is (lower, upper).
        names:   Tuple containing all valid named values for the field. For
                 numeric only fields the tuple is empty.
        map:     Tuple of 2 way tuples mapping named values to numeric
                 equivalents. Format is ((name1, numeric1), ..
                 (namex, numericx)). For numeric only fields the tuple is empty.
        is_rorl: Is field part of a range or list. Either True or False.
        """

        field = field.strip()
        if field == '*':  # first-last
            # simply return a set of all poss values
            return set(xrange(span[0], span[1] + 1))
        elif field.isdigit():  # just a number
            # If its a DOW then replace any 7s with 0
            _field = field.replace('7','0') if span == DOW else field
            # its valid if its within our span
            if span[0] <= int(_field) <= span[1]:
                # it's valid so return the field itself as a set
                return set((int(_field), ))
            else:
                # invalid field value so raise ValueError
                raise ValueError("Invalid field value '%s' in '%s'" % (field, self.raw_line))
        elif field.lower() in names:  # an abbreviated name
            # abbreviated names are only valid if not used in a range or list
            if not is_rorl:
                # replace all named values with numbers
                _field = field
                for _name, _ord in map:
                    _field = _field.replace(_name, str(_ord))
                # its valid if its within our span
                if span[0] <= int(_field) <= span[1]:
                    # it's valid so return the field itself as a set
                    return set((int(_field), ))
                else:
                    # invalid field value so raise ValueError
                    raise ValueError("Invalid field value '%s' in '%s'" % (field, self.raw_line))
            else:
                # invalid use of abbreviated name so raise ValueError
                raise ValueError("Invalid use of abbreviated name '%s' in '%s'" % (field, self.raw_line))
        elif ',' in field:  # we have a list
            # get the first list item and the rest of the list
            _first, _rest = field.split(',', 1)
            # get _first as a set using a recursive call
            _first_set = self.parse_field(_first, span, names, map, True)
            # get _rest as a set using a recursive call
            _rest_set = self.parse_field(_rest, span, names, map, True)
            # return the union of the _first and _rest sets
            return _first_set | _rest_set
        elif '/' in field:  # a step
            # get the value and the step
            _val, _step = field.split('/', 1)
            # step is valid if it is numeric
            if _step.isdigit():
                # get _val as a set using a recursive call
                _val_set = self.parse_field(_val, span, names, map, True)
                # get the set of all possible values using _step
                _lowest = min(_val_set)
                _step_set = set([x for x in _val_set if ((x - _lowest) % int(_step) == 0)])
                # return the intersection of the _val and _step sets
                return _val_set & _step_set
            else:
                # invalid step so raise ValueError
                raise ValueError("Invalid step value '%s' in '%s'" % (field, self.raw_line))
        elif '-' in field:  # we have a range
            # get the lo and hi values of the range
            lo, hi = field.split('-', 1)
            # if lo is numeric and in the span range then the range is valid if
            # hi is valid
            if lo.isdigit() and span[0] <= int(lo) <= span[1]:
                # if hi is numeric and in the span range and greater than or
                # equal to lo then the range is valid
                if hi.isdigit() and int(hi) >= int(lo) and span[0] <= int(hi) <= span[1]:
                    # valid range so return a set of the range
                    return set(xrange(int(lo), int(hi) + 1))
                else:
                    # something is wrong, we have an invalid field
                    raise ValueError("Invalid range specification '%s' in '%s'" % (field, self.raw_line))
            else:
                # something is wrong with lo, we have an invalid field
                raise ValueError("Invalid range specification '%s' in '%s'" % (field, self.raw_line))
        else:
            # we have something I don't know how to parse so raise a ValueError
            raise ValueError("Invalid field '%s' in '%s'" % (field, self.raw_line))

    def is_triggered(self, ts_hi, ts_lo=None):
        """Determine if CRON like line is to be triggered.

        Return True if line is triggered between timestamps ts_lo and ts_hi
        (exclusivie on ts_lo inclusive on ts_hi), False if it is not
        triggered or None if the line is invalid or ts_hi is not valid.
        If ts_lo is not specified check for triggering on ts_hi only.

        ts_hi:  Timestamp of latest time to be checked for triggering.
        ts_lo:  Timestamp used for earliest time in range of times to be
                checked for triggering. May be ommitted in which case only
                ts_hi is checked.
        """

        if self.is_valid and ts_hi is not None:
            # setup ts range to iterate over
            if ts_lo is None:
                _range = [int(ts_hi)]
            else:
                # CRON like line has a 1 min resolution so step backwards every
                # 60 sec.
                _range = range(int(ts_hi), int(ts_lo), -60)
            # Iterate through each ts in our range. All we need is one ts that
            # triggers the line.
            for _ts in _range:
                # convert ts to timetuple and extract required data
                trigger_dt = datetime.datetime.fromtimestamp(_ts)
                trigger_tt = trigger_dt.timetuple()
                month, dow, day, hour, minute = (trigger_tt.tm_mon,
                                                (trigger_tt.tm_wday + 1) % 7,
                                                trigger_tt.tm_mday,
                                                trigger_tt.tm_hour,
                                                trigger_tt.tm_min)
                # construct a tuple so we can iterate over and process each
                # field
                element_tuple = zip((minute, hour, day, month, dow),
                                    self.line,
                                    SPANS,
                                    self.decode)
                # Iterate over each field and check if it will prevent
                # triggering. Remember, we only need a match on either DOM or
                # DOW but all other fields must match.
                dom_match = False
                dom_restricted_match = False
                for period, field, field_span, decode in element_tuple:
                    if period in decode:
                        # we have a match
                        if field_span == DOM:
                            # we have a match on DOM but we need to know if it
                            # was a match on a restricted DOM field
                            dom_match = True
                            dom_restricted_match = self.dom_restrict
                        elif field_span == DOW and not(dom_restricted_match or self.dow_restrict or dom_match):
                            break
                        continue
                    elif field_span == DOW and dom_restricted_match or field_span == DOM:
                        # No match but consider it a match if this field is DOW
                        # and we already have a DOM match. Also, if we didn't
                        # match on DOM then continue as we might match on DOW.
                        continue
                    else:
                        # The field will prevent the line from triggerring for
                        # this ts so we break and move to the next ts.
                        break
                else:
                    # If we arrived here then all fields match and the line
                    # would be triggered on this ts so return True.
                    return True
            # If we are here it is becasue we broke out of all inner for loops
            # and the line was not triggered so return False.
            return False
        else:
            # Our line is not valid or we do not have a timestamp to use,
            # return None
            return None

