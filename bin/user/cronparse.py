import calendar
import datetime
import time

# spans of valid values for each CRON field
MINUTES = (0, 59)
HOURS = (0, 23)
DOM = (1, 31)
MONTHS = (1, 12)
DOW = (0, 6)
# field names
FIELDS = (MINUTES, HOURS, DOM, MONTHS, DOW)
# map month names to CRON month number
MONTH_NAME_MAP = zip(('jan', 'feb', 'mar', 'apr',
                      'may', 'jun', 'jul', 'aug',
                      'sep', 'oct', 'nov', 'dec'), xrange(1, 13))
# map day names to CRON day number
DAY_NAME_MAP = zip(('sun', 'mon', 'tue', 'wed',
                    'thu', 'fri', 'sat'), xrange(7))
# map nicknames to equivalent CRON line
NICKNAME_MAP = {
    "@yearly": "0 0 1 1 *",
    "@anually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@hourly": "0 * * * *"
}

class ReportCron(object):
    """Class for processing a CRON line and determining whether it should be
    fired for a given time.

    The following CRON capabilities are supported:
    - There are two ways to specify the day the CRON is fired, DOM and DOW. A
      match on either all other fields and either DOM or DOW will casue the
      CRON to be fired.
    - first-last, *. Matches all possible values for the field concerned.
    - step, /x. Matches every xth minute/hour/day etc. May be bounded by a list
      or range.
    - range, lo-hi. Matches all values from lo to hi inclusive.
    - lists, x,y,z. Matches those items in the list. List items may be a range.
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

    is_valid:         Whether passed line is a valid CRON line or not.
    validation_error: Error message if passed line is an invalid CRON line.
    raw_line:         Raw line data passed to ReportCron.
    line:             5 item list representing the 5 CRON date/time fields
                      after the raw CRON line has been processed and dom/dow
                      named parameters replaced with numeric equivalents.
    """

    def __init__(self, line):
        """Instantiates a ReportCron object.

        Processes raw CRON line to produce 5 field CRON line suitable for
        further processing.
        """

        self.is_valid = None
        self.validation_error = None
        self.raw_line = line
        # do some basic checking of the CRON line for unsupported characters
        for unsupported_char in ('%', '#', 'L', 'W'):
            if unsupported_char in line:
                self.is_valid = False
                self.validation_error = "Unsupported character '%s' found in CRON line '%s'." % (unsupported_char,
                                                                                                 line)
                return
        line = line.strip().lower()
        # six special time defintion 'nicknames' are supported which replace
        # the CRON line elements with pre-detemined values. These nicknames
        # start with the @ character. Check for any of these nicknames and
        # substitute the CRON line accordingly
        for nickname, nn_line in NICKNAME_MAP.iteritems():
            if line == nickname:
                line = nn_line
                break
        fields = line.split(None, 5)
        if len(fields) == 5:
            fields.append(None)
        # extract individual CRON line elements
        minutes, hours, dom, months, dow, extra = fields
        # CRON represents dow as 0..7 where 0 and 7 = Sunday. To simplify
        # Python code for parsing CRON lines replace all 7's with 0 in dow
        # field
        dow = dow.replace('7', '0')
        # CRON represents dow as Mon..Sun (case insensitive) or 0..7
        # where 0 and 7 = Sunday. Need to check for any dow names in dow and
        # substitute with corresponding dow number.
        for dow_name, dow_ord in DAY_NAME_MAP:
            dow = dow.replace(dow_name, str(dow_ord))
        # CRON represents month as jan..dec (case insensitive) or 1..12
        # where 1=Jan and 12=Dec. Need to check for any month names in months
        # and substitute with corresponding month number.
        for month_name, month_ord in MONTH_NAME_MAP:
            months = months.replace(month_name, str(month_ord))
        self.line = [minutes, hours, dom, months, dow]
        (self.is_valid, self.validation_error) = self.decode()

    def decode(self):
        """Decode each CRON field and store the sets of valid values.

        Returns a 2-way tuple (True|False, ERROR MESSAGE). First item is True
        is the CRON line is valid otherwise False. ERROR MESSAGE is None if
        the CRON line is valid otherwise a string containing a short error
        message.
        """

        # set a list to hold our decoded ranges
        self.decode = []
        try:
            # step through each field and its associated range
            for field, span in zip(self.line, FIELDS):
                # do some basic validation
                if '*' in field:
                    if len(field) == 1:
                        pass
                    elif '/' in field and not field.split('/', 1)[1].isdigit():
                        raise ValueError("Invalid step in CRON line field '%s'" %
                                         field)
                field_set = self.parse_field(field, span)
                self.decode.append(field_set)
            return (True, None)
        except ValueError, e:
            return (False, e)

    def is_triggered(self, ts_hi, ts_lo=None):
        """Determine if CRON is to be triggered.

        Return True if CRON is triggered between timestamps ts_lo and ts_hi
        (exclusivie on ts_lo inclusive on ts_hi), False if it is not
        triggered or None if the CRON line is invalid or ts_hi is not valid.
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
                # CRON uses a 1 min resolution so step backwards every 60 sec.
                _range = range(int(ts_hi), int(ts_lo), -60)
            # Iterate through each ts in our range. All we need is one ts that
            # triggers the CRON line.
            dom_match = False
            for _ts in _range:
                # convert ts to timetuple and extract required data
                trigger_dt = datetime.datetime.fromtimestamp(_ts)
                trigger_tt = trigger_dt.timetuple()
                month, dow, day, hour, minute = (trigger_tt.tm_mon,
                                                trigger_tt.tm_wday,
                                                trigger_tt.tm_mday,
                                                trigger_tt.tm_hour,
                                                trigger_tt.tm_min)
                # construct a tuple so we can iterate over and process each
                # field
                element_tuple = zip((minute, hour, day, month, dow),
                                    self.line,
                                    FIELDS,
                                    self.decode)
                # Iterate over each field and check if it will prevent
                # triggering. Remember, we only need a match on either DOM or
                # DOW but all other fields must match.
                for period, field, field_name, decode in element_tuple:
                    if period in decode:
                        # we have a match
                        if field_name == 'DOM':
                            # we have a match on DOM so set dom_match
                            dom_match = True
                        continue
                    elif field_name == 'DOW' and dom_match:
                        # No match but if consider it a match if this field is
                        # DOW and we already have a DOM match.
                        continue
                    else:
                        # The field will prevent the CRON line from triggerring
                        # for this ts so we break and move to the next ts.
                        break
                else:
                    # If we arrived here then all fields match and CRON would
                    # be triggered so return True.
                    return True
            # If we got here it is becasue we broke out of all inner for loops
            # and the CRON was not triggered so return False.
            return False
        else:
            # Our CRON line is not valid or we do not have a timestamp to use,
            # return None
            return None

    def parse_field(self, field, span):
        """Return the set of valid values for a CRON field given its span.

        Returns a set containing all of the field values. Can be called
        recursively to parse sub-fields (eg lists of ranges). If an error is
        detected in the CRON line a ValueError is raised.

        field: String containing the raw CRON line field to be parsed.
        span:  Tuple representing the range of values the field may take.
               Format is (lower, upper).
        """

        field = field.strip()
        if field == '*':  # first-last
            # simply return a set of all poss values
            return set(xrange(span[0], span[1] + 1))
        elif field.isdigit():  # just a number
            # just return the field itself as a set
            return set((int(field), ))
        elif ',' in field:  # we have a list
            # get the first list item and the rest of the list
            _first, _rest = field.split(',', 1)
            # get _first as a set using a recursive call
            _first_set = self.parse_field(_first, span)
            # get _rest as a set using a recursive call
            _rest_set = self.parse_field(_rest, span)
            # return the union of the _first and _rest sets
            return _first_set | _rest_set
        elif '/' in field:  # a step
            # get the value and the step
            _val, _step = field.split('/', 1)
            # get _val as a set using a recursive call
            _val_set = self.parse_field(_val, span)
            # get the set of all possible values using _step
            _lowest = min(_val_set)
            _step_set = set([x for x in _val_set if ((x - _lowest) % int(_step) == 0)])
            # return the intersection of the _val and _step sets
            return _val_set & _step_set
        elif '-' in field:  # we have a range
            # get the lo and hi values of the range
            lo, hi = field.split('-', 1)
            # are they both numbers?
            if lo.isdigit() and hi.isdigit():
                # if so return a set of the range
                return set(xrange(int(lo), int(hi) + 1))
            else:
                # both are not numbers, we have an invalid field
                raise ValueError("Invalid range specification '%s'" % field)
        else:
            # we have something I don't know how to parse so raise a ValueError
            raise ValueError("Invalid field '%s'" % field)