#
#    Copyright (c) 2019-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Class for calculating time derivatives"""
import weewx


class TimeDerivative(object):
    """Calculate time derivative for a specific observation type."""

    def __init__(self, obs_type, stale_age):
        """Initialize.

        obs_type: the observation type for which the derivative will be calculated.

        stale_age: Derivatives are calculated as a difference over time. This is how old the old value
        can be and still be considered useful.
        """
        self.obs_type = obs_type
        self.stale_age = stale_age
        self.old_timestamp = None
        self.old_value = None

    def add_record(self, record):
        """Add a new record, then return the difference in value divided by the difference in time."""

        # If the type does not appear in the incoming record, then we can't calculate the derivative
        if self.obs_type not in record:
            raise weewx.CannotCalculate(self.obs_type)

        derivative = None
        if record[self.obs_type] is not None:
            # We can't calculate anything if we don't have an old record
            if self.old_timestamp:
                # Check to make sure the incoming record is later than the retained record
                if record['dateTime'] < self.old_timestamp:
                    raise weewx.ViolatedPrecondition("Records presented out of order (%s vs %s)"
                                                     % (record['dateTime'], self.old_timestamp))
                # Calculate the time derivative only if there is a delta in time,
                # and the old record is not too old.
                if record['dateTime'] != self.old_timestamp \
                        and (record['dateTime'] - self.old_timestamp) <= self.stale_age:
                    # All OK.
                    derivative = (record[self.obs_type] - self.old_value) \
                                 / (record['dateTime'] - self.old_timestamp)
            # Save the current values
            self.old_timestamp = record['dateTime']
            self.old_value = record[self.obs_type]

        return derivative
