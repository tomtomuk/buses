import pandas as pd
from datetime import datetime
from geopy.distance import great_circle
import json

# Westbound stops
HEAVITREE_BRIDGE_IN = {"latitude": 50.719708, "longitude": -3.493304}
ST_LOYES_RD_IN = {"latitude": 50.720561, "longitude": -3.496193}
BUTTS_ROAD_IN = {"latitude": 50.721171, "longitude": -3.501255}
POST_OFFICE_IN = {"latitude": 50.721455, "longitude": -3.506379}

# Fore street = -3.508142 to -3.501045 ~(City Vets to Butts Road)
# Bus lane = -3.504520 to -3.501827

BUSFILE = 'csv_data/buses_2024-10-22.csv'


# Extract latitude and longitude from JSON string
def get_lat_lon(location_json):
  # json decoder requires double quotes around properties
  location_json = location_json.replace("'", '"')
  data = json.loads(location_json)
  return data["latitude"], data["longitude"]


def calculate_distance_and_time(group):
    previous_row = None
    for index, row in group.iterrows():
        if previous_row is not None:
            group.loc[index, "distance"] = great_circle(
                (row["latitude"], row["longitude"]),
                (previous_row["latitude"], previous_row["longitude"])
            ).kilometers

        # Check if the current location is near a westbound stop
        group.loc[index, "near_westbound_stop"] = is_near_westbound_stop(row["latitude"], row["longitude"])
        previous_row = row

    group["time_diff"] = pd.to_timedelta(group[timestamp_col].diff())

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

# Calculate speed
bus_data["speed"] = bus_data["distance"] / bus_data["time_diff"].dt.total_seconds() * 3600  # Convert to km/h

# The "speed" column now contains the individual speeds at each timestep
# save the interesting data:
tosave = bus_data[[
    "direction_ref", "line_ref", "dated_vehicle_journey_ref", "latitude", "longitude", "recorded_at_time", "speed", "near_westbound_stop"
]]

tosave.to_csv('speeds.csv', index=False)
