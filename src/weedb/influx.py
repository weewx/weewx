#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""weedb driver for InfluxDB"""

try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS
    from influxdb_client.rest import ApiException
except ImportError:
    raise ImportError("InfluxDB client not found. Install it with 'pip install influxdb-client'")

import weedb
from weeutil.weeutil import to_bool


def guard(fn):
    """Decorator function that converts InfluxDB exceptions into weedb exceptions."""

    def guarded_fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiException as e:
            # Map InfluxDB exceptions to weedb exceptions based on status code and error message
            if e.status == 401:
                raise weedb.BadPasswordError(e)
            elif e.status == 403:
                raise weedb.PermissionError(e)
            elif e.status == 404:
                if "bucket" in str(e).lower():
                    raise weedb.NoDatabaseError(e)
                else:
                    raise weedb.OperationalError(e)
            elif e.status == 409:
                raise weedb.DatabaseExistsError(e)
            else:
                raise weedb.OperationalError(e)
        except ConnectionError:
            raise weedb.CannotConnectError("Cannot connect to InfluxDB server")
        except Exception as e:
            raise weedb.OperationalError(e)

    return guarded_fn


def connect(host='localhost', port=8086, org='', token='', bucket='', driver='', 
            protocol='http', **kwargs):
    """Connect to the specified InfluxDB database"""
    return Connection(host=host, port=port, org=org, token=token, bucket=bucket, 
                      protocol=protocol, **kwargs)


@guard
def create(host='localhost', port=8086, org='', token='', bucket='', driver='',
           protocol='http', **kwargs):
    """Create a bucket in InfluxDB. If it already exists,
    an exception of type weedb.DatabaseExistsError will be raised."""
    
    client = InfluxDBClient(url=f"{protocol}://{host}:{port}", token=token, org=org)
    try:
        buckets_api = client.buckets_api()
        
        # Check if bucket already exists
        buckets = buckets_api.find_buckets().buckets
        for existing_bucket in buckets:
            if existing_bucket.name == bucket:
                raise weedb.DatabaseExistsError(f"Bucket '{bucket}' already exists")
        
        # Create the bucket
        buckets_api.create_bucket(bucket_name=bucket, org=org)
    finally:
        client.close()


@guard
def drop(host='localhost', port=8086, org='', token='', bucket='', driver='',
         protocol='http', **kwargs):
    """Drop a bucket from InfluxDB."""
    
    client = InfluxDBClient(url=f"{protocol}://{host}:{port}", token=token, org=org)
    try:
        buckets_api = client.buckets_api()
        
        # Find the bucket ID
        buckets = buckets_api.find_buckets().buckets
        bucket_id = None
        for existing_bucket in buckets:
            if existing_bucket.name == bucket:
                bucket_id = existing_bucket.id
                break
        
        if bucket_id is None:
            raise weedb.NoDatabaseError(f"No such bucket '{bucket}'")
        
        # Delete the bucket
        buckets_api.delete_bucket(bucket_id)
    finally:
        client.close()


class Connection(weedb.Connection):
    """A wrapper around an InfluxDB connection object."""

    @guard
    def __init__(self, host='localhost', port=8086, org='', token='', bucket='',
                 protocol='http', **kwargs):
        """Initialize an instance of Connection.

        Args:
            host (str): IP or hostname hosting the InfluxDB server.
            port (int): The port number (default is 8086)
            org (str): The InfluxDB organization name
            token (str): The authentication token
            bucket (str): The bucket to use (equivalent to database_name)
            protocol (str): The protocol to use (http or https)
            kwargs (dict): Any extra arguments to pass to the InfluxDB client
        """
        self.host = host
        self.port = port
        self.org = org
        self.token = token
        self.bucket = bucket
        self.protocol = protocol
        self.kwargs = kwargs
        
        # Initialize the InfluxDB client
        url = f"{protocol}://{host}:{port}"
        self.client = InfluxDBClient(url=url, token=token, org=org, **kwargs)
        
        # Verify the connection by checking if the bucket exists
        buckets_api = self.client.buckets_api()
        buckets = buckets_api.find_buckets().buckets
        bucket_exists = False
        for existing_bucket in buckets:
            if existing_bucket.name == bucket:
                bucket_exists = True
                break
        
        if not bucket_exists:
            self.close()
            raise weedb.NoDatabaseError(f"Bucket '{bucket}' does not exist")
        
        # Initialize the write API for this connection
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        
        # Initialize the query API for this connection
        self.query_api = self.client.query_api()
        
        # Import Point class for creating data points
        from influxdb_client import Point
        self.Point = Point
        
        weedb.Connection.__init__(self, self.client, bucket, 'influxdb')

    def cursor(self):
        """Return a cursor object."""
        return Cursor(self)

    @guard
    def tables(self):
        """Returns a list of measurements in the bucket.
        InfluxDB doesn't have tables in the traditional SQL sense, 
        but measurements can be considered analogous."""
        
        # Run a Flux query to get distinct measurement names
        query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{self.bucket}")
        '''
        result = self.query_api.query(query=query, org=self.org)
        
        table_list = []
        if result:
            for table in result:
                for record in table.records:
                    table_list.append(record.values.get('_value'))
        
        return table_list

    @guard
    def get_unit_system(self):
        """Get the unit system from the metadata measurement"""
        import sys
        try:
            # Query to get the most recent unit system value
            query = f'''
            from(bucket: "{self.bucket}")
              |> range(start: -30d)
              |> filter(fn: (r) => r._measurement == "weewx_metadata")
              |> filter(fn: (r) => r.type == "unit_system")
              |> last()
            '''
            result = self.query_api.query(query=query, org=self.org)
            
            if result and len(result) > 0 and len(result[0].records) > 0:
                unit_system = result[0].records[0].values.get('_value')
                # FIXME: this is hacky, but it works for now
                # Make sure it's an integer, not a string or timestamp
                if isinstance(unit_system, str) and unit_system.isdigit():
                    unit_system = int(unit_system)
                elif not isinstance(unit_system, int):
                    print(f"DEBUG: Converting unit system to integer: {unit_system}", file=sys.stderr)
                    unit_system = 1  # Default to US units if not parseable
                
                print(f"DEBUG: Found unit system in metadata: {unit_system}", file=sys.stderr)
                return unit_system
            else:
                print(f"DEBUG: No unit system found in metadata, using default (1)", file=sys.stderr)
                return 1  # Default to US units (0x01)
        except Exception as e:
            print(f"DEBUG: Error getting unit system: {e}, using default (1)", file=sys.stderr)
            return 1  # Default to US units (0x01) on error
        
    @guard
    def genSchemaOf(self, measurement):
        """Return a summary of the schema of the specified measurement.
        
        In InfluxDB, we don't have a fixed schema, but we can try to discover 
        the fields being used in a measurement."""
        
        try:
            # Query to get field keys for the specified measurement
            query = f'''
            import "influxdata/influxdb/schema"
            schema.fieldKeys(bucket: "{self.bucket}", measurement: "{measurement}")
            '''
            result = self.query_api.query(query=query, org=self.org)
            
            # Query to get tag keys for the specified measurement
            tags_query = f'''
            import "influxdata/influxdb/schema"
            schema.tagKeys(bucket: "{self.bucket}", measurement: "{measurement}")
            '''
            tags_result = self.query_api.query(query=tags_query, org=self.org)
            
            field_list = []
            if result:
                for table in result:
                    for record in table.records:
                        field_list.append(record.values.get('_value'))
            
            tag_list = []
            if tags_result:
                for table in tags_result:
                    for record in table.records:
                        tag_list.append(record.values.get('_value'))
            
            # Map fields to types
            # This is a simplification as InfluxDB has different field types
            # For now, assume everything is REAL since we're dealing with weather data
            irow = 0
            for field in field_list:
                # Yield tuple of (number, column_name, column_type, can_be_null, default_value, is_primary)
                yield (irow, field, 'REAL', True, None, False)
                irow += 1
            
            # Add tags
            for tag in tag_list:
                yield (irow, tag, 'TAG', True, None, False)
                irow += 1
                
        except Exception as e:
            # If there's an error getting the schema (likely because the measurement doesn't exist yet),
            # return a basic schema with required WeeWX fields
            
            # For archive measurement, provide the default schema
            if measurement.lower() == 'archive':
                default_schema = [
                    (0, 'dateTime', 'INTEGER', False, None, True),  # dateTime is the timestamp
                    (1, 'usUnits', 'INTEGER', False, None, False),
                    (2, 'interval', 'INTEGER', False, None, False),
                    (3, 'barometer', 'REAL', True, None, False),
                    (4, 'pressure', 'REAL', True, None, False),
                    (5, 'altimeter', 'REAL', True, None, False),
                    (6, 'outTemp', 'REAL', True, None, False),
                    (7, 'outHumidity', 'REAL', True, None, False),
                    (8, 'windSpeed', 'REAL', True, None, False),
                    (9, 'windDir', 'REAL', True, None, False),
                    (10, 'windGust', 'REAL', True, None, False),
                    (11, 'windGustDir', 'REAL', True, None, False),
                    (12, 'rainRate', 'REAL', True, None, False),
                    (13, 'rain', 'REAL', True, None, False),
                    (14, 'dewpoint', 'REAL', True, None, False),
                    (15, 'windchill', 'REAL', True, None, False),
                    (16, 'heatindex', 'REAL', True, None, False),
                    (17, 'radiation', 'REAL', True, None, False),
                    (18, 'UV', 'REAL', True, None, False),
                ]
                for row in default_schema:
                    yield row
            else:
                # For other measurements, yield a minimal schema with just dateTime
                yield (0, 'dateTime', 'INTEGER', False, None, True)

    @guard
    def columnsOf(self, measurement):
        """Return a list of columns (fields and tags) in the specified measurement."""
        column_list = []
        
        # Use genSchemaOf to get fields and tags
        for row in self.genSchemaOf(measurement):
            column_list.append(row[1])  # Column name is at index 1
            
        # Don't raise an error if there's no columns - this can happen for a new measurement
        # We'll use the default schema from genSchemaOf instead
            
        return column_list

    @guard
    def get_variable(self, var_name):
        """Return a database specific operational variable."""
        # InfluxDB doesn't have an exact equivalent to database variables
        # For now, return None for all variables
        return None

    @property
    def has_math(self):
        """Returns True if the database supports math functions such as cos() and sin()."""
        return True
        
    @property
    def std_unit_system(self):
        """Return the unit system in use by this database."""
        return self.get_unit_system()

    @guard
    def begin(self):
        """InfluxDB doesn't support traditional transactions in the same way as SQL databases.
        This is a no-op for compatibility."""
        pass

    @guard
    def commit(self):
        """InfluxDB doesn't support traditional transactions in the same way as SQL databases.
        This is a no-op for compatibility."""
        pass

    @guard
    def rollback(self):
        """InfluxDB doesn't support traditional transactions in the same way as SQL databases.
        This is a no-op for compatibility."""
        pass

    @guard
    def close(self):
        """Close the database connection."""
        try:
            if hasattr(self, 'write_api') and self.write_api:
                self.write_api.close()
            if hasattr(self, 'client') and self.client:
                self.client.close()
        except Exception:
            pass


class Cursor(weedb.Cursor):
    """A wrapper around the InfluxDB query API to provide a cursor-like interface."""

    @guard
    def __init__(self, connection):
        """Initialize a Cursor from a connection.
        
        connection: An instance of weedb.influx.Connection"""
        self.connection = connection
        self.query_api = connection.query_api
        self.write_api = connection.write_api
        self.org = connection.org
        self.bucket = connection.bucket
        self._results = None
        self._rowcount = 0
        self._current_record_index = 0

    @guard
    def execute(self, sql_string, sql_tuple=()):
        """Execute a query against InfluxDB.
        
        sql_string: A query string. This can be either SQL or Flux.
        sql_tuple: Values to be substituted into the query placeholders.
        """
        self._results = None
        self._rowcount = 0
        self._current_record_index = 0
        
        # Check if this is an INSERT statement
        if sql_string.strip().upper().startswith('INSERT'):
            return self._execute_insert(sql_string, sql_tuple)
        
        # Check if this is a direct Flux query (starts with 'from' or another Flux keyword)
        elif sql_string.strip().lower().startswith(('from', 'import')):
            return self._execute_flux(sql_string, sql_tuple)
        
        # Otherwise, attempt to translate SQL to Flux
        else:
            return self._execute_sql(sql_string, sql_tuple)
    
    @guard
    def _execute_insert(self, sql_string, sql_tuple=()):
        """Handle INSERT statements by converting to InfluxDB point format."""
        # Parse the INSERT statement
        # Example: INSERT INTO archive (dateTime, outTemp, barometer) VALUES (?, ?, ?)
        
        # Add debug logging
        import sys
        print(f"DEBUG: Processing INSERT statement into InfluxDB", file=sys.stderr)
        print(f"DEBUG: SQL: {sql_string}", file=sys.stderr)
        print(f"DEBUG: Values: {sql_tuple}", file=sys.stderr)
        
        # First, extract the table/measurement name
        import re
        match = re.search(r'INSERT\s+INTO\s+(\w+)', sql_string, re.IGNORECASE)
        if not match:
            print(f"DEBUG: Error - Invalid INSERT statement format", file=sys.stderr)
            raise weedb.OperationalError("Invalid INSERT statement format")
        
        measurement = match.group(1)
        print(f"DEBUG: Measurement/Table: {measurement}", file=sys.stderr)
        
        # Extract column names and values
        columns_match = re.search(r'\(([^)]+)\)\s+VALUES\s+\(([^)]+)\)', sql_string, re.IGNORECASE)
        if not columns_match:
            print(f"DEBUG: Error - Could not extract columns and values", file=sys.stderr)
            raise weedb.OperationalError("Invalid INSERT statement format")
        
        # Get column names and strip any backticks
        columns = [col.strip().strip('`') for col in columns_match.group(1).split(',')]
        print(f"DEBUG: Columns: {columns}", file=sys.stderr)
        
        # Get placeholders and check if they match the provided values
        placeholders = columns_match.group(2).split(',')
        if len(placeholders) != len(sql_tuple):
            print(f"DEBUG: Error - Mismatch between placeholders and values", file=sys.stderr)
            print(f"DEBUG: Placeholders: {len(placeholders)}, Values: {len(sql_tuple)}", file=sys.stderr)
            raise weedb.OperationalError("Mismatch between placeholders and values")
        
        # Create a Point object for the measurement
        from influxdb_client import Point
        point = Point(measurement)
        
        # Special handling for dateTime column which becomes the timestamp in InfluxDB
        timestamp = None
        
        # Check if we're creating an initial record with unit system info
        if measurement.lower() == 'archive' and 'usunits' in [col.lower() for col in columns]:
            # Store the unit system in the database using a special write
            usunits_index = next((i for i, col in enumerate(columns) if col.lower() == 'usunits'), None)
            if usunits_index is not None:
                usunits_value = sql_tuple[usunits_index]
                
                # FIXME: this is hacky, but it works for now
                # Make sure unit system is an integer between 0-255
                if isinstance(usunits_value, str) and usunits_value.isdigit():
                    usunits_value = int(usunits_value)
                
                # Validate the unit system value
                if not isinstance(usunits_value, int) or usunits_value > 255:
                    usunits_value = 1  # Default to US units (0x01)
                    
                print(f"DEBUG: Setting unit system to: {usunits_value}", file=sys.stderr)
                
                # Write a special record for unit system tracking
                unit_point = Point('weewx_metadata')
                unit_point = unit_point.tag('type', 'unit_system')
                unit_point = unit_point.field('value', usunits_value)
                
                try:
                    self.write_api.write(bucket=self.bucket, org=self.org, record=unit_point)
                    print(f"DEBUG: Successfully stored unit system metadata: {usunits_value}", file=sys.stderr)
                except Exception as e:
                    print(f"DEBUG: Error storing unit system metadata: {e}", file=sys.stderr)
        
        # Map columns to values and add them to the point
        for i, column in enumerate(columns):
            column = column.strip()
            value = sql_tuple[i]
            
            print(f"DEBUG: Processing column: {column} = {value}", file=sys.stderr)
            
            # Special handling for dateTime column (used as timestamp in InfluxDB)
            if column.lower() == 'datetime':
                from datetime import datetime
                # Convert Unix timestamp to datetime
                if isinstance(value, (int, float)):
                    timestamp = datetime.utcfromtimestamp(value)
                    print(f"DEBUG: Using dateTime as timestamp: {timestamp}", file=sys.stderr)
                else:
                    timestamp = value
                    print(f"DEBUG: Using dateTime as timestamp (non-numeric): {timestamp}", file=sys.stderr)
            # Special handling for known metadata fields that should be tags, not fields
            elif column.lower() in ('station', 'station_type'):
                point = point.tag(column, str(value))
                print(f"DEBUG: Added tag: {column} = {value}", file=sys.stderr)
            # Special handling for usUnits - add as both tag and field for improved compatibility
            elif column.lower() == 'usunits':
                point = point.tag(column, str(value))
                point = point.field(column, value)
                print(f"DEBUG: Added usUnits as both tag and field: {value}", file=sys.stderr)
            # Special handling for interval - add as both tag and field for compatibility
            elif column.lower() == 'interval':
                point = point.tag(column, str(value))
                point = point.field(column, value)
                print(f"DEBUG: Added interval as both tag and field: {value}", file=sys.stderr)
            else:
                # All other values go into fields
                try:
                    point = point.field(column, value)
                    print(f"DEBUG: Added field: {column} = {value}", file=sys.stderr)
                except Exception as e:
                    # Skip null values for now - InfluxDB doesn't support them
                    if value is None:
                        print(f"DEBUG: Skipping NULL value for field: {column}", file=sys.stderr)
                    else:
                        print(f"DEBUG: Error adding field {column} = {value}: {e}", file=sys.stderr)
                        raise
        
        # Set the timestamp if one was found
        if timestamp:
            point = point.time(timestamp)
            print(f"DEBUG: Set point timestamp to: {timestamp}", file=sys.stderr)
        else:
            print(f"DEBUG: WARNING - No timestamp found in record", file=sys.stderr)
        
        # Write the point to InfluxDB
        try:
            print(f"DEBUG: Writing point to InfluxDB bucket: {self.bucket}", file=sys.stderr)
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            print(f"DEBUG: Successfully wrote point to InfluxDB", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Error writing to InfluxDB: {e}", file=sys.stderr)
            raise
        
        # Set rowcount to indicate a successful insert
        self._rowcount = 1
        
        return self
    
    @guard
    def _execute_flux(self, flux_query, params=()):
        """Execute a direct Flux query."""
        # Simple placeholder substitution for parameterized queries
        if params:
            query = flux_query
            for param in params:
                if isinstance(param, str):
                    # Wrap strings in quotes
                    query = query.replace('?', f'"{param}"', 1)
                else:
                    # Use the parameter as is
                    query = query.replace('?', str(param), 1)
        else:
            query = flux_query
        
        # Execute the query
        self._results = self.query_api.query(query=query, org=self.org)
        
        # Count the total number of records
        self._rowcount = 0
        if self._results:
            for table in self._results:
                self._rowcount += len(table.records)
        
        return self
    
    @guard
    def _execute_sql(self, sql_string, sql_tuple=()):
        """Translate SQL to Flux and execute."""
        # Handle special cases first
        import re
        
        # Handle the "SELECT sqlite_version()" query
        if re.search(r'SELECT\s+sqlite_version\(\)', sql_string, re.IGNORECASE):
            # Return a dummy version for compatibility
            self._results = None
            self._rowcount = 1
            self._special_result = [("InfluxDB 2.x compatibility",)]
            return self
        
        # Handle "SELECT name FROM sqlite_master" query
        if re.search(r'SELECT\s+name\s+FROM\s+sqlite_master', sql_string, re.IGNORECASE):
            # Return the list of measurements as "tables"
            tables = self.connection.tables()
            self._results = None
            self._rowcount = len(tables)
            self._special_result = [(table,) for table in tables]
            return self
        
        # Handle "SELECT COUNT(*) FROM sqlite_master" query
        if re.search(r'SELECT\s+COUNT\(\*\)\s+FROM\s+sqlite_master', sql_string, re.IGNORECASE):
            # Return the count of measurements as "tables"
            tables = self.connection.tables()
            self._results = None
            self._rowcount = 1
            self._special_result = [(len(tables),)]
            return self
        
        # Handle "PRAGMA table_info(X)" query
        pragma_match = re.search(r'PRAGMA\s+table_info\((\w+)\)', sql_string, re.IGNORECASE)
        if pragma_match:
            measurement = pragma_match.group(1)
            # Generate schema info for the table
            schema = list(self.connection.genSchemaOf(measurement))
            self._results = None
            self._rowcount = len(schema)
            self._special_result = schema
            return self
        
        # Standard SQL query handling
        try:
            # Extract the table/measurement name
            match = re.search(r'FROM\s+(\w+)', sql_string, re.IGNORECASE)
            if not match:
                # Some queries from WeeWX don't have a FROM clause, like "SELECT SQLITE_VERSION()"
                # For these, we'll return empty results
                self._results = None
                self._rowcount = 0
                return self
            
            measurement = match.group(1)
            
            # Extract the WHERE clause if it exists
            where_match = re.search(r'WHERE\s+(.+?)(?:ORDER BY|GROUP BY|LIMIT|$)', sql_string, re.IGNORECASE)
            where_clause = where_match.group(1).strip() if where_match else None
            
            # Extract the ORDER BY clause if it exists
            order_match = re.search(r'ORDER BY\s+(.+?)(?:LIMIT|$)', sql_string, re.IGNORECASE)
            order_clause = order_match.group(1).strip() if order_match else None
            
            # Extract the LIMIT clause if it exists
            limit_match = re.search(r'LIMIT\s+(\d+)', sql_string, re.IGNORECASE)
            limit = int(limit_match.group(1)) if limit_match else None
            
            # Start building the Flux query
            flux_query = f'from(bucket: "{self.bucket}")\n'
            
            # Add time range filter if specified in WHERE clause
            # This is a simple implementation - we're looking for datetime comparisons
            time_range_start = None
            time_range_stop = None
            
            if where_clause:
                # Look for dateTime > X
                start_match = re.search(r'dateTime\s*>\s*(\d+)', where_clause)
                if start_match:
                    time_range_start = int(start_match.group(1))
                
                # Look for dateTime < X
                stop_match = re.search(r'dateTime\s*<\s*(\d+)', where_clause)
                if stop_match:
                    time_range_stop = int(stop_match.group(1))
            
            if time_range_start and time_range_stop:
                # Convert Unix timestamps to RFC3339 format for Flux
                from datetime import datetime
                start_time = datetime.utcfromtimestamp(time_range_start).isoformat() + 'Z'
                stop_time = datetime.utcfromtimestamp(time_range_stop).isoformat() + 'Z'
                flux_query += f'  |> range(start: {start_time}, stop: {stop_time})\n'
            elif time_range_start:
                from datetime import datetime
                start_time = datetime.utcfromtimestamp(time_range_start).isoformat() + 'Z'
                flux_query += f'  |> range(start: {start_time})\n'
            elif time_range_stop:
                from datetime import datetime
                stop_time = datetime.utcfromtimestamp(time_range_stop).isoformat() + 'Z'
                flux_query += f'  |> range(stop: {stop_time})\n'
            else:
                # Default to recent data if no time range specified
                flux_query += '  |> range(start: -30d)\n'
            
            # Filter by measurement name
            flux_query += f'  |> filter(fn: (r) => r._measurement == "{measurement}")\n'
            
            # Add ordering if specified
            if order_clause:
                if 'desc' in order_clause.lower():
                    flux_query += '  |> sort(columns: ["_time"], desc: true)\n'
                else:
                    flux_query += '  |> sort(columns: ["_time"])\n'
            
            # Add limit if specified
            if limit:
                flux_query += f'  |> limit(n: {limit})\n'
            
            # Execute the generated Flux query
            return self._execute_flux(flux_query, sql_tuple)
            
        except Exception as e:
            # Log the error for debugging
            import sys
            print(f"Error in _execute_sql: {e}", file=sys.stderr)
            print(f"SQL: {sql_string}", file=sys.stderr)
            
            # Return empty results rather than raising an exception
            self._results = None
            self._rowcount = 0
            return self

    def fetchone(self):
        """Fetch the next row of a query result set."""
        # Handle special results (sqlite compatibility layer)
        if hasattr(self, '_special_result'):
            if self._current_record_index < self._rowcount:
                result = self._special_result[self._current_record_index]
                self._current_record_index += 1
                return result
            else:
                return None
        
        # Handle normal InfluxDB query results
        if not self._results or self._current_record_index >= self._rowcount:
            return None
        
        # Find the appropriate record
        current_count = 0
        for table in self._results:
            for record in table.records:
                if current_count == self._current_record_index:
                    self._current_record_index += 1
                    
                    # Convert InfluxDB record to a tuple format similar to what SQLite would return
                    values = []
                    
                    # Handle timestamp - store it as Unix timestamp for WeeWX compatibility
                    if '_time' in record.values:
                        from datetime import datetime
                        timestamp = record.values.get('_time')
                        if isinstance(timestamp, datetime):
                            # Convert to Unix timestamp
                            import calendar
                            values.append(calendar.timegm(timestamp.utctimetuple()))
                        else:
                            values.append(timestamp)
                    
                    # Add all field values, skipping internal fields that start with _
                    for field in sorted(record.values.keys()):
                        if field not in ('_time', '_measurement', '_field', '_value', 'result', 'table') and not field.startswith('_'):
                            value = record.values.get(field)
                            # Convert known numeric string values to their appropriate type
                            if field.lower() == 'interval' and isinstance(value, str) and value.isdigit():
                                value = int(value)
                            elif field.lower() == 'usunits' and isinstance(value, str) and value.isdigit():
                                value = int(value)
                            values.append(value)
                    
                    # Ensure essential fields like interval are included
                    # This handles the case where interval might be stored as a tag and not a field
                    if 'interval' in record.values and record.values['interval'] not in values:
                        values.append(record.values['interval'])
                    # Check for interval in tags (which are not included in record.values by default)
                    elif hasattr(record, 'values') and record.values.get('_measurement') == 'archive' and 'interval' not in record.values:
                        # Try to get interval from tags if available
                        interval_value = None
                        try:
                            interval_value = record.values.get('interval')
                        except:
                            pass
                        
                        if interval_value is not None:
                            # Convert to int if it's a string
                            if isinstance(interval_value, str) and interval_value.isdigit():
                                interval_value = int(interval_value)
                            values.append(interval_value)
                        else:
                            # Add a default interval value of 5 minutes (300 seconds) if not found
                            import sys
                            print(f"DEBUG: Adding default interval value for record", file=sys.stderr)
                            values.append(5)
                    
                    # Add _value field which contains the actual measurement value in InfluxDB
                    if '_value' in record.values:
                        values.append(record.values.get('_value'))
                    
                    return tuple(values)
                current_count += 1
        
        return None

    def fetchall(self):
        """Fetch all remaining rows of a query result."""
        # Handle special results
        if hasattr(self, '_special_result'):
            # Get all remaining records from the special result
            results = self._special_result[self._current_record_index:]
            self._current_record_index = self._rowcount
            return results
        
        # Handle normal results
        if not self._results:
            return []
        
        all_records = []
        while True:
            record = self.fetchone()
            if record is None:
                break
            all_records.append(record)
        
        return all_records

    def fetchmany(self, size=None):
        """Fetch the next set of rows of a query result."""
        # Handle special results
        if hasattr(self, '_special_result'):
            if size is None:
                size = self._rowcount
            
            end_idx = min(self._current_record_index + size, self._rowcount)
            results = self._special_result[self._current_record_index:end_idx]
            self._current_record_index = end_idx
            return results
        
        # Handle normal results
        if not self._results:
            return []
        
        if size is None:
            size = self._rowcount
        
        records = []
        for _ in range(size):
            record = self.fetchone()
            if record is None:
                break
            records.append(record)
        
        return records

    def close(self):
        """Close the cursor."""
        self._results = None
        self._rowcount = 0
        self._current_record_index = 0

    def __enter__(self):
        return self

    def __exit__(self, etyp, einst, etb):
        self.close()
        
    def __iter__(self):
        """Make the cursor iterable."""
        # Handle special results
        if hasattr(self, '_special_result'):
            for record in self._special_result:
                yield record
            return
            
        # Return an iterator that yields each record
        record = self.fetchone()
        while record is not None:
            yield record
            record = self.fetchone()