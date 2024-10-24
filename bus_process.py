import pandas as pd
from datetime import datetime
from geopy.distance import great_circle
import json

DATE = '2024-10-23'

# Westbound stops
HEAVITREE_BRIDGE_IN = {"latitude": 50.719708, "longitude": -3.493304}
ST_LOYES_RD_IN = {"latitude": 50.720561, "longitude": -3.496193}
BUTTS_ROAD_IN = {"latitude": 50.721171, "longitude": -3.501255}
POST_OFFICE_IN = {"latitude": 50.721455, "longitude": -3.506379}

# Fore street = -3.508142 to -3.501045 ~(City Vets to Butts Road)
# Bus lane = -3.504520 to -3.501827

BUSFILE = f'csv_data/buses_{DATE}.csv'


# Extract latitude and longitude from JSON string
def get_lat_lon(location_json):
  # json decoder requires double quotes around properties
  location_json = location_json.replace("'", '"')
  data = json.loads(location_json)
  return data["latitude"], data["longitude"]


def calculate_distance_and_time(group):
    group = group.sort_values(timestamp_col)  # Ensure the group is sorted by timestamp
    previous_row = None
    total_distance = 0
    total_time = pd.Timedelta(0)
    
    for index, row in group.iterrows():
        if previous_row is not None:
            # Calculate time difference
            time_diff = row[timestamp_col] - previous_row[timestamp_col]
            group.loc[index, "time_diff"] = time_diff
            total_time += time_diff

            # Calculate distance
            distance = great_circle(
                (row["latitude"], row["longitude"]),
                (previous_row["latitude"], previous_row["longitude"])
            ).kilometers
            group.loc[index, "distance"] = distance
            total_distance += distance

            # Calculate speed for each row
            if time_diff.total_seconds() > 0:
                group.loc[index, "speed"] = distance / time_diff.total_seconds() * 3600  # Convert to km/h
            else:
                group.loc[index, "speed"] = 0
        else:
            # For the first row, set distance, time_diff, and speed to None
            group.loc[index, "distance"] = None
            group.loc[index, "time_diff"] = None
            group.loc[index, "speed"] = None

        # Check if the current location is near a westbound stop
        group.loc[index, "near_westbound_stop"] = is_near_westbound_stop(row["latitude"], row["longitude"])
        previous_row = row

    # Calculate average speed for the group
    if total_time.total_seconds() > 0:
        group["avg_speed"] = total_distance / total_time.total_seconds() * 3600  # Convert to km/h
    else:
        group["avg_speed"] = 0

    return group



def is_near_westbound_stop(lat, lon, max_distance=0.01):  # 0.01 km = 10 meters
    westbound_stops = [HEAVITREE_BRIDGE_IN, ST_LOYES_RD_IN, BUTTS_ROAD_IN, POST_OFFICE_IN]
    for stop in westbound_stops:
        if great_circle((lat, lon), (stop['latitude'], stop['longitude'])).kilometers <= max_distance:
            return True
    return False


# Load the CSV data
bus_data = pd.read_csv(BUSFILE)

# Define relevant columns
timestamp_col = "recorded_at_time"
location_col = "vehicle_location"
journey_ref_col = ["dated_vehicle_journey_ref", "vehicle_ref"]

bus_data[timestamp_col] = bus_data[timestamp_col].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S%z'))

locations_list = bus_data[location_col].apply(get_lat_lon).tolist()
bus_data["latitude"], bus_data["longitude"] = zip(*locations_list)

# Group by journey_ref and vehicle and calculate distance and time within each group
grouped_data = bus_data.groupby(journey_ref_col)
bus_data = grouped_data.apply(calculate_distance_and_time)

# save the interesting data:
tosave = bus_data[[
    "direction_ref", "line_ref", "dated_vehicle_journey_ref", 
    "latitude", "longitude", "recorded_at_time", "speed", "near_westbound_stop",
    "avg_speed"
]]

tosave.to_csv(f'speeds_{DATE}.csv', index=False)
