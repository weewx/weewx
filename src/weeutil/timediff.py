#
#    Copyright (c) 2019-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Class for calculating time derivatives.

Not used within WeeWX, but it is used by a few extensions.
"""
import weewx


class TimeDerivative:
    """Calculate time derivative for a specific observation type."""

    def __init__(self, obs_type, stale_age):
        """Initialize.

        Args:
            obs_type(str): the observation type for which the derivative will be calculated.
            stale_age(float): Derivatives are calculated as a difference over time. This is how old
                the old value can be and still be considered useful.
        """
        self.obs_type = obs_type
        self.stale_age = stale_age
        self.old_timestamp = None
        self.old_value = None

    def add_record(self, record):
        """Return the difference in value divided by the difference in time.

        Args:
            record(dict): A LOOP packet or archive record.

        Returns:
            float|None: The change in value since the last record, divided by the difference
                in timestamps, or None if the derivative cannot be calculated.
        """

        # If the type does not appear in the incoming record,
        # then we can't calculate the derivative
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
