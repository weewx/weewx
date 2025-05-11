#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Service for streaming weather data to InfluxDB."""

import logging

import weeutil.weeutil
import weeutil.config
import weewx.engine
import weewx.units
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)


class StdWxStreaming(weewx.engine.StdService):
    """Service that streams LOOP data to InfluxDB in real-time."""

    def __init__(self, engine, config_dict):
        super().__init__(engine, config_dict)

        # Extract configuration options
        if 'StdWxStreaming' not in config_dict:
            log.info("No [StdWxStreaming] section in configuration. Skipping.")
            return

        streaming_dict = config_dict.get('StdWxStreaming', {})
        self.data_binding = streaming_dict.get('data_binding', 'influx_binding')
        self.streaming_interval = to_int(streaming_dict.get('streaming_interval', 0))
        self.record_generation = streaming_dict.get('record_generation', 'hardware').lower()
        self.log_success = to_bool(weeutil.config.search_up(streaming_dict, 'log_success', False))
        self.log_failure = to_bool(weeutil.config.search_up(streaming_dict, 'log_failure', True))

        # Make sure the data binding exists in the configuration
        if 'DataBindings' not in config_dict or self.data_binding not in config_dict['DataBindings']:
            log.error(f"Data binding '{self.data_binding}' not found in configuration")
            log.error("Available bindings: %s",
                      ', '.join(config_dict.get('DataBindings', {}).keys()))
            log.error("Data streaming disabled")
            return
        
        # Get list of observation types to skip
        self.skip_types = []
        if 'skip_types' in streaming_dict:
            self.skip_types = [x.strip() for x in streaming_dict['skip_types'].split(',')]
            log.debug(f"Will skip observation types: {self.skip_types}")
        
        # Initialize database connection
        try:
            self.setup_database(config_dict)
        except Exception as e:
            log.error(f"Failed to initialize database for streaming: {e}")
            log.error("Data streaming disabled")
            self.db_manager = None
            return
        
        # Time of the last streaming update
        self.last_streaming_ts = 0
        
        # Subscribe to the NEW_LOOP_PACKET event
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        log.info(f"StdWxStreaming will use data binding {self.data_binding}")

    def setup_database(self, config_dict):
        """Set up the database connection."""
        # Get the database manager for the data binding
        self.db_manager = self.engine.db_binder.get_manager(self.data_binding, initialize=True)
        
        # Make sure the binding is using InfluxDB
        if 'influx' not in str(type(self.db_manager.connection)):
            raise ValueError(f"Data binding '{self.data_binding}' is not using InfluxDB driver")
            
        log.info(f"Using binding '{self.data_binding}' to database '{self.db_manager.database_name}'")
        
        # Store InfluxDB-specific components for easier access
        self.connection = self.db_manager.connection
        self.bucket = self.connection.bucket
        self.write_api = self.connection.write_api
        self.org = self.connection.org
        
        # Initialize Point class for creating data points
        from influxdb_client import Point
        self.Point = Point
        
    def new_loop_packet(self, event):
        """Process a new LOOP packet.
        
        Args:
            event: An instance of weewx.Event with a 'packet' attribute
        """
        # Check if database manager is available
        if not hasattr(self, 'db_manager') or self.db_manager is None:
            return
            
        # Check if it's time to stream data
        if self.streaming_interval > 0:
            if event.packet['dateTime'] - self.last_streaming_ts < self.streaming_interval:
                return
                
        # Stream the data
        try:
            self._stream_data(event.packet)
            self.last_streaming_ts = event.packet['dateTime']
        except Exception as e:
            if self.log_failure:
                log.error(f"Failed to stream LOOP data: {e}")
                
    def _stream_data(self, packet):
        """Stream a packet to InfluxDB.
        
        Args:
            packet: A dictionary containing weather data
        """
        # Create a Point object for the measurement
        point = self.Point(self.db_manager.table_name)
        
        # Add timestamp
        from datetime import datetime
        timestamp = datetime.utcfromtimestamp(packet['dateTime'])
        point = point.time(timestamp)
        
        # Add metadata tags
        if 'station_type' in packet:
            point = point.tag('station_type', str(packet['station_type']))
        
        # Add usUnits and interval as both tags and fields for compatibility
        point = point.tag('usUnits', str(packet['usUnits']))
        point = point.field('usUnits', packet['usUnits'])
        
        if 'interval' in packet:
            point = point.tag('interval', str(packet['interval']))
            point = point.field('interval', packet['interval'])
        
        # Add other observation types as fields
        fields_added = False
        for obs_type in packet:
            # Skip special fields already processed and any in the skip list
            if obs_type in ('dateTime', 'usUnits', 'interval', 'station_type') or obs_type in self.skip_types:
                continue
                
            # Skip null values - InfluxDB doesn't support them
            if packet[obs_type] is None:
                continue
                
            try:
                point = point.field(obs_type, packet[obs_type])
                fields_added = True
            except Exception as e:
                log.debug(f"Error adding field {obs_type} = {packet[obs_type]}: {e}")
        
        # Only write the point if fields were added
        if fields_added:
            # Write the point to InfluxDB
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            
            if self.log_success:
                log.debug(f"Streamed LOOP data with timestamp {timestamp} to InfluxDB")
                
    def shutDown(self):
        """Close database connection when service shuts down."""
        if hasattr(self, 'db_manager') and self.db_manager is not None:
            try:
                self.db_manager.close()
            except Exception:
                pass