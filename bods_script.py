from bods_client.models.base import APIError
from bods_client.client import BODSClient
from bods_client.models import BoundingBox, Siri, SIRIVMParams
from dotenv import load_dotenv

import csv
import time, datetime
import os


load_dotenv()
API_KEY = os.getenv('BODS_API_KEY')
client = BODSClient(api_key=API_KEY)


def query_vehicle_data(client, params):
    siri_response = client.get_siri_vm_data_feed(params=params)
    if type(siri_response) == APIError:
        raise APIError(siri_response)
    siri = Siri.from_bytes(siri_response)
    v_data = siri.service_delivery.vehicle_monitoring_delivery.vehicle_activities
    
    return v_data


def create_csv_dict(v_data):
    timestamp = v_data.recorded_at_time
    j_data = v_data.monitored_vehicle_journey.model_dump()
    j_data['recorded_at_time'] = timestamp

    return j_data


def create_buses_file(client, params):
    # Get the current time
    now = datetime.datetime.now()
    # Create a new file name based on the date
    csv_file = now.strftime("buses_%Y-%m-%d.csv")

    v_data = []
    # get some initial bus data
    while(len(v_data) == 0):
        v_data = query_vehicle_data(client, params)
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        if len(v_data) > 0:
            print(f'{now_str} found {len(v_data)} buses!')
        else:
            print(f'{now_str} - no buses found.')
            time.sleep(30)

    # Open the CSV file for writing and write the header
    with open(csv_file, "w", newline="") as csvfile:
        j_data = create_csv_dict(v_data[0])
        writer = csv.DictWriter(csvfile, fieldnames=j_data.keys())
        writer.writeheader()

        # write first set of data
        for v in v_data:
            j_row = create_csv_dict(v)
            print(f'Writing {j_row}')
            writer.writerow(j_row)

        # now read more bus data
        # End the loop at the end of the day (e.g., 11:59 PM)
        end_time = now.replace(hour=23, minute=59, second=59)
        while now < end_time:
            csvfile.flush()
            time.sleep(30)

            v_data = query_vehicle_data(client, params)
            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            if len(v_data) > 0:
                print(f'{now_str} - Found {len(v_data)} buses!')
                for v in v_data:
                    j_row = create_csv_dict(v)
                    print(f'Writing: {j_row}')
                    writer.writerow(j_row)
            else:
                print(f'{now_str} - No buses found.')


bounding_box = BoundingBox(
    **{
        "min_latitude": 50.72,
        "max_latitude": 50.772,
        "min_longitude": -3.51,
        "max_longitude": -3.499,
    }
)

params = SIRIVMParams(bounding_box=bounding_box)

while True:
    # This will keep calling the function to make a file, which will automatically exit at midnight
    create_buses_file(client, params)
