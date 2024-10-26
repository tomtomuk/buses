import pandas as pd
from datetime import datetime
from geopy.distance import great_circle
import json

DATE = '2024-10-24'

BUS_LANE = [
    {"latitude": 50.721252, "longitude": -3.504539},
    {"latitude": 50.721186, "longitude": -3.501835}
    ]

def calc_lat_range(bus_lane):
    # Extract latitudes from the BUS_LANE list
    latitudes = [point["latitude"] for point in BUS_LANE]

    # Find the minimum and maximum latitudes
    min_latitude = min(latitudes)
    max_latitude = max(latitudes)

    # Calculate the desired values
    lower_bound = min_latitude - 0.000346
    upper_bound = max_latitude + 0.000346

    return lower_bound, upper_bound

LAT_RANGE = calc_lat_range(BUS_LANE)

# Westbound stops
HEAVITREE_BRIDGE_IN = {"latitude": 50.719708, "longitude": -3.493304}
ST_LOYES_RD_IN = {"latitude": 50.720561, "longitude": -3.496193}
BUTTS_ROAD_IN = {"latitude": 50.721171, "longitude": -3.501255}
POST_OFFICE_IN = {"latitude": 50.721455, "longitude": -3.506379}

BUSFILE = f'csv_data/bus_data/buses_{DATE}.csv'


# Extract latitude and longitude from JSON string
def get_lat_lon(location_json):
  # json decoder requires double quotes around properties
  location_json = location_json.replace("'", '"')
  data = json.loads(location_json)
  return data["latitude"], data["longitude"]


def calculate_distance_and_time(group):
    group = group.sort_values(timestamp_col)
    
    # Find the points just before, within, and just after the BUS_LANE range
    after_lane = group[group['longitude'] < BUS_LANE[0]['longitude']].iloc[:1] if not group[group['longitude'] < BUS_LANE[0]['longitude']].empty else pd.DataFrame()
    in_lane = group[
        (group['longitude'].between(BUS_LANE[0]['longitude'], BUS_LANE[1]['longitude'], inclusive='both')) &
        (group['latitude'].between(LAT_RANGE[0], LAT_RANGE[1], inclusive='both'))
    ]
    before_lane = group[group['longitude'] > BUS_LANE[1]['longitude']].iloc[-1:] if not group[group['longitude'] > BUS_LANE[1]['longitude']].empty else pd.DataFrame()
    
    relevant_points = pd.concat([before_lane, in_lane, after_lane]).sort_values(timestamp_col)
    
    if len(relevant_points) < 2:
        return group
    
    first_point = relevant_points.iloc[0]
    last_point = relevant_points.iloc[-1]
    
    # Calculate total distance and time
    total_distance = great_circle(
        (first_point['latitude'], first_point['longitude']),
        (last_point['latitude'], last_point['longitude'])
    ).kilometers
    
    total_time = (last_point[timestamp_col] - first_point[timestamp_col]).total_seconds() / 3600  # in hours
    
    # Calculate average speed
    avg_speed = total_distance / total_time if total_time > 0 else 0
    
    # Calculate implied speed between BUS_LANE points
    bus_lane_distance = great_circle(
        (BUS_LANE[0]['latitude'], BUS_LANE[0]['longitude']),
        (BUS_LANE[1]['latitude'], BUS_LANE[1]['longitude'])
    ).kilometers
    
    # Calculate the fraction of total distance that the bus lane represents
    if total_distance > 0:
        time_fraction = bus_lane_distance / total_distance
        implied_time = total_time * time_fraction
    else:
        implied_time = 0
    
    implied_speed = bus_lane_distance / implied_time if implied_time > 0 else 0
    
    # Add new columns to the group
    group['in_bus_lane'] = group.index.isin(in_lane.index)
    group['bus_lane_avg_speed'] = avg_speed
    group['bus_lane_implied_speed'] = implied_speed
    
    return group


# def calculate_distance_and_time(group):
#     group = group.sort_values(timestamp_col)  # Ensure the group is sorted by timestamp
#     previous_row = None
#     total_distance = 0
#     total_time = pd.Timedelta(0)
    
#     for index, row in group.iterrows():
#         if previous_row is not None:
#             # Calculate time difference
#             time_diff = row[timestamp_col] - previous_row[timestamp_col]
#             group.loc[index, "time_diff"] = time_diff
#             total_time += time_diff

#             # Calculate distance
#             distance = great_circle(
#                 (row["latitude"], row["longitude"]),
#                 (previous_row["latitude"], previous_row["longitude"])
#             ).kilometers
#             group.loc[index, "distance"] = distance
#             total_distance += distance

#             # Calculate speed for each row
#             if time_diff.total_seconds() > 0:
#                 group.loc[index, "speed"] = distance / time_diff.total_seconds() * 3600  # Convert to km/h
#             else:
#                 group.loc[index, "speed"] = None
#         else:
#             # For the first row, set distance, time_diff, and speed to None
#             group.loc[index, "distance"] = None
#             group.loc[index, "time_diff"] = None
#             group.loc[index, "speed"] = None

#         # Check if the current location is near a westbound stop
#         group.loc[index, "near_westbound_stop"] = is_near_westbound_stop(row["latitude"], row["longitude"])
#         previous_row = row

#     # Calculate average speed for the group
#     if total_time.total_seconds() > 0:
#         group["avg_speed"] = total_distance / total_time.total_seconds() * 3600  # Convert to km/h
#     else:
#         group["avg_speed"] = None

#     return group


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
journey_ref_col = ["dated_vehicle_journey_ref", "vehicle_ref", "direction_ref"]

bus_data[timestamp_col] = bus_data[timestamp_col].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S%z'))

locations_list = bus_data[location_col].apply(get_lat_lon).tolist()
bus_data["latitude"], bus_data["longitude"] = zip(*locations_list)

# filter to inbound only
bus_data = bus_data[bus_data['direction_ref'] == 'inbound']
# Group by journey_ref and vehicle and calculate distance and time within each group
grouped_data = bus_data.groupby(journey_ref_col)
bus_data = grouped_data.apply(calculate_distance_and_time)

# filter to buses only in fore street bus lane
bus_data = bus_data[bus_data['in_bus_lane'] == True]

# save the interesting data:
tosave = bus_data[[
    "direction_ref", "line_ref", "dated_vehicle_journey_ref", 
    "latitude", "longitude", "recorded_at_time",
    "bus_lane_implied_speed"
]]

tosave.to_csv(f'speeds_{DATE}.csv', index=False)
