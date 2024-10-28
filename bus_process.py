import pandas as pd
from datetime import datetime
from geopy.distance import great_circle
import json
import sys
import os

DATE = sys.argv[1]

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
    
    # Initialize new columns with default values
    group['in_bus_lane'] = False
    group['bus_lane_avg_speed'] = 0
    group['bus_lane_implied_speed'] = 0
    group['wrong_direction'] = False

    if len(relevant_points) < 2:
        return group
    
    first_point = relevant_points.iloc[0]
    last_point = relevant_points.iloc[-1]
    
    # Check direction
    correct_direction = last_point['longitude'] < first_point['longitude']

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
    group['wrong_direction'] == correct_direction

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
# these columns should be enough to isolate individual journeys
journey_ref_col = [
    "dated_vehicle_journey_ref", "origin_aimed_departure_time", "vehicle_ref", "direction_ref"
    ]

bus_data[timestamp_col] = bus_data[timestamp_col].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S%z'))

locations_list = bus_data[location_col].apply(get_lat_lon).tolist()
bus_data["latitude"], bus_data["longitude"] = zip(*locations_list)

# filter to inbound only
bus_data = bus_data[bus_data['direction_ref'] == 'inbound']
# filter to stagecoach only
bus_data = bus_data[bus_data['operator_ref'] == 'SDVN']

# Group by journey_ref and vehicle and calculate distance and time within each group
grouped_data = bus_data.groupby(journey_ref_col)
bus_data = grouped_data.apply(calculate_distance_and_time)

# filter to buses only in fore street bus lane
bus_data = bus_data[bus_data['in_bus_lane'] == True]
# and only correct direction
bus_data[bus_data['wrong_direction'] == False]

# save the interesting data:
tosave = bus_data[[
    "direction_ref", "line_ref", "dated_vehicle_journey_ref", 
    "latitude", "longitude", "recorded_at_time",
    "bus_lane_implied_speed"
]]

tosave.to_csv(f'csv_data\speeds\speeds_{DATE}.csv', index=False)

# Filter and report buses traveling in the wrong direction
wrong_direction_buses = bus_data[bus_data['wrong_direction'] == True]
if not wrong_direction_buses.empty:
    print(f"\nFound {len(wrong_direction_buses)} buses traveling in the wrong direction:")
    columns_to_display = ['line_ref', 'dated_vehicle_journey_ref', 'source_date', 'recorded_at_time', 'longitude', 'latitude']
    
    # Optionally, save to a CSV file
    output_dir = 'wrong_direction_reports'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'wrong_direction_{timestamp}.csv'
    filepath = os.path.join(output_dir, filename)
    wrong_direction_buses[columns_to_display].to_csv(filepath, index=False)
    print(f"Wrong direction data has been written to {filepath}")
else:
    print("\nNo buses found traveling in the wrong direction.")