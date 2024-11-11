import pandas as pd
from datetime import datetime
from geopy.distance import great_circle
import json
import sys
import os


ROAD_SECTIONS = {
    'bus_lane': [
        {"latitude": 50.721252, "longitude": -3.504539},
        {"latitude": 50.721186, "longitude": -3.501835}
    ],
    'ewh': [
        {"latitude": 50.721173, "longitude": -3.501134},
        {"latitude": 50.719663, "longitude": -3.492795}
    ],
    'butts_to_po': [
        {"latitude": 50.721476, "longitude": -3.506459},
        {"latitude": 50.721156, "longitude": -3.500906}
    ]
}

# Get command line arguments
if len(sys.argv) != 3:
    print("Usage: python bus_process.py <date> <road_section>")
    print("Available road sections:", ", ".join(ROAD_SECTIONS.keys()))
    sys.exit(1)

DATE = sys.argv[1]
SECTION_NAME = sys.argv[2]

if SECTION_NAME not in ROAD_SECTIONS:
    print(f"Invalid road section. Choose from: {', '.join(ROAD_SECTIONS.keys())}")
    sys.exit(1)

# Get the selected road section data
ROAD_SECTION = ROAD_SECTIONS[SECTION_NAME]


def calc_lat_range(bus_lane):
    # Extract latitudes from the BUS_LANE list
    latitudes = [point["latitude"] for point in ROAD_SECTION]

    # Find the minimum and maximum latitudes
    min_latitude = min(latitudes)
    max_latitude = max(latitudes)

    # Calculate the desired values
    lower_bound = min_latitude - 0.000346
    upper_bound = max_latitude + 0.000346

    return lower_bound, upper_bound

LAT_RANGE = calc_lat_range(ROAD_SECTION)

BUSFILE = f'csv_data/bus_data/buses_{DATE}.csv'


# Extract latitude and longitude from JSON string
def get_lat_lon(location_json):
  # json decoder requires double quotes around properties
  location_json = location_json.replace("'", '"')
  data = json.loads(location_json)
  return data["latitude"], data["longitude"]


def calculate_distance_and_time(group):
    group = group.sort_values(timestamp_col)
    
    # Find the points just before, within, and just after the ROAD_SECTION range
    # this assumes traffic travelling westbound (i.e decreasing longitude over time)
    after_section = group[group['longitude'] < ROAD_SECTION[0]['longitude']].iloc[:1] if not group[group['longitude'] < ROAD_SECTION[0]['longitude']].empty else pd.DataFrame()
    in_section = group[
        (group['longitude'].between(ROAD_SECTION[0]['longitude'], ROAD_SECTION[1]['longitude'], inclusive='both')) &
        (group['latitude'].between(LAT_RANGE[0], LAT_RANGE[1], inclusive='both'))
    ]
    before_section = group[group['longitude'] > ROAD_SECTION[1]['longitude']].iloc[-1:] if not group[group['longitude'] > ROAD_SECTION[1]['longitude']].empty else pd.DataFrame()
    
    relevant_points = pd.concat([before_section, in_section, after_section]).sort_values(timestamp_col)
    
    # check that after sorting by time, the longitude values are decreasing (if not implies an error in the data)
    if not relevant_points['longitude'].is_monotonic_decreasing:
        print("Error: Longitude values are not decreasing as expected for this group.")
        print(relevant_points[['line_ref', 'longitude', timestamp_col]])
        return group
    
    # Initialize new columns with default values
    group['in_section'] = False
    group['avg_speed'] = 0
    group['implied_speed'] = 0

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
    
    # Calculate implied speed in section
    section_distance = great_circle(
        (ROAD_SECTION[0]['latitude'], ROAD_SECTION[0]['longitude']),
        (ROAD_SECTION[1]['latitude'], ROAD_SECTION[1]['longitude'])
    ).kilometers
    
    # Calculate the fraction of total distance that the section represents
    if total_distance > 0:
        time_fraction = section_distance / total_distance
        implied_time = total_time * time_fraction
    else:
        implied_time = 0
    
    implied_speed = section_distance / implied_time if implied_time > 0 else 0
    
    # Add new columns to the group
    group['in_section'] = group.index.isin(in_section.index)
    group['avg_speed'] = avg_speed
    group['implied_speed'] = implied_speed
    
    return group


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
# also filter to westbound only by selecting bearing between 190 and 350
bus_data = bus_data[bus_data['bearing'].between(190, 350)]
# filter to stagecoach only
bus_data = bus_data[bus_data['operator_ref'] == 'SDVN']
# remove R bus (as R inbound goes wrong way and also not down Fore Street)
bus_data = bus_data[bus_data['line_ref'] != 'R']

# Group by journey_ref and vehicle and calculate distance and time within each group
grouped_data = bus_data.groupby(journey_ref_col)
bus_data = grouped_data.apply(calculate_distance_and_time)

# filter to buses only section
bus_data = bus_data[bus_data['in_section'] == True]

# save the interesting data:
tosave = bus_data[[
    "direction_ref", "line_ref", "dated_vehicle_journey_ref", 
    "latitude", "longitude", "recorded_at_time",
    "implied_speed"
]]

# Update file paths
BUSFILE = f'csv_data/bus_data/buses_{DATE}.csv'
SPEEDS_DIR = f'csv_data/speeds/{SECTION_NAME}/archive'

# Create directories if they don't exist
os.makedirs(SPEEDS_DIR, exist_ok=True)

# Update output file paths
speeds_output = os.path.join(SPEEDS_DIR, f'speeds_{DATE}.csv')

# save
tosave.to_csv(speeds_output, index=False)
