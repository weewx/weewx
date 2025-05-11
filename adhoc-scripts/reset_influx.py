#!/usr/bin/env python3
"""
Reset InfluxDB bucket to fix unit system issues
"""

from influxdb_client import InfluxDBClient

# Configuration parameters - update as needed
URL = "http://localhost:8086"
TOKEN = "aXwGB3kJzQgfRD9f1ibYcsmGbmj-9DExYoK_rbbqf2yS5DgbRTNR-kHC8SPOzr9Blfs5rrAMIOsvFMvOl0dA_A=="
ORG = "weewx"
BUCKET = "weather_data"

def reset_bucket():
    """Drop and recreate the weather_data bucket"""
    print(f"Connecting to InfluxDB at {URL}...")
    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
    
    try:
        buckets_api = client.buckets_api()
        
        # Find the bucket
        print(f"Looking for bucket '{BUCKET}'...")
        existing = buckets_api.find_bucket_by_name(BUCKET)
        
        if existing:
            print(f"Found bucket '{BUCKET}' with ID {existing.id}")
            print(f"Dropping bucket '{BUCKET}'...")
            buckets_api.delete_bucket(existing.id)
            print(f"Bucket '{BUCKET}' dropped successfully")
        else:
            print(f"Bucket '{BUCKET}' not found, will create new")
        
        # Create a new bucket
        print(f"Creating new bucket '{BUCKET}'...")
        buckets_api.create_bucket(bucket_name=BUCKET, org=ORG)
        print(f"Bucket '{BUCKET}' created successfully")
        
        # Create a point to set the unit system
        print("Setting default unit system to US (0x01)...")
        from influxdb_client import Point
        from influxdb_client.client.write_api import SYNCHRONOUS
        
        # Create the write API
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        # Create a point for the unit system
        unit_point = Point("weewx_metadata")\
            .tag("type", "unit_system")\
            .field("value", 1)  # 0x01 = US units
        
        # Write the point
        write_api.write(bucket=BUCKET, org=ORG, record=unit_point)
        print("Default unit system set successfully")
        
        # Close the client
        client.close()
        print("Done! Bucket has been reset.")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    reset_bucket()