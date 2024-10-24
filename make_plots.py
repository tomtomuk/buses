import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import matplotlib.dates as mdates
import pytz
import glob
import re

LOCAL_TIMEZONE = 'Europe/London'  # Replace with your local timezone

csv_files = glob.glob('csv_data/speeds/speeds_*.csv')

print(f"Found {len(csv_files)} CSV files")

def extract_date_from_filename(filename):
    # Updated regex to match YYYY-MM-DD format
    match = re.search(r'speeds_(\d{4}-\d{2}-\d{2})\.csv', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    return None

df_list = []
for file in csv_files:
    temp_df = pd.read_csv(file)
    file_date = extract_date_from_filename(file)
    if file_date:
        temp_df['source_date'] = file_date
    else:
        temp_df['source_date'] = pd.NaT
    df_list.append(temp_df)
    print(f"Read {file}: {len(temp_df)} rows")

df = pd.concat(df_list, ignore_index=True)
print(f"Combined DataFrame: {len(df)} rows")

df['recorded_at_time'] = pd.to_datetime(df['recorded_at_time'])

local_tz = pytz.timezone(LOCAL_TIMEZONE)
df['recorded_at_time'] = df['recorded_at_time'].dt.tz_convert(local_tz)

today = pd.Timestamp.today().normalize()
df['recorded_at_time'] = df['recorded_at_time'].apply(lambda x: today + pd.Timedelta(hours=x.hour, minutes=x.minute, seconds=x.second))

grouped = df.groupby(['line_ref', 'dated_vehicle_journey_ref', 'source_date']).first().reset_index()
print(f"Grouped data: {len(grouped)} rows")

# Diagnostic: Print rows with average speed of zero
zero_speed_rows = df[df['avg_speed'] == 0]
if not zero_speed_rows.empty:
    print("\nRows with average speed of zero:")
    print(zero_speed_rows[['line_ref', 'dated_vehicle_journey_ref', 'source_date', 'recorded_at_time', 'avg_speed', 'longitude', 'latitude']])
    print(f"Total rows with zero speed: {len(zero_speed_rows)}")
else:
    print("\nNo rows found with average speed of zero.")

# Additional check for very low speeds
low_speed_rows = df[df['avg_speed'] < 1]  # Adjust the threshold as needed
if not low_speed_rows.empty:
    print("\nRows with very low average speed (< 1 km/h):")
    print(low_speed_rows[['line_ref', 'dated_vehicle_journey_ref', 'source_date', 'recorded_at_time', 'avg_speed', 'longitude', 'latitude']])
    print(f"Total rows with very low speed: {len(low_speed_rows)}")
else:
    print("\nNo rows found with very low average speed.")


def create_scatter_plot(data, x, y, hue, style, title, filename):
    if len(data) == 0:
        print(f"No data to plot for {filename}")
        return
    
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.scatterplot(data=data, x=x, y=y, hue=hue, style=style, ax=ax)
    
    plt.title(title)
    plt.xlabel('Time of Day')
    plt.ylabel('Speed (km/h)')
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator())
    
    for time_str in ['08:00', '09:30', '16:00', '18:30']:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        ax.axvline(x=today + pd.Timedelta(hours=time_obj.hour, minutes=time_obj.minute), 
                   linestyle='--', color='gray', alpha=0.5)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

create_scatter_plot(
    data=grouped,
    x='recorded_at_time',
    y='avg_speed',
    hue='line_ref',
    style='source_date',
    title='Average Speed by Line and Journey (Time of Day) - Inbound',
    filename='average_speed_scatter_plot.png'
)

df_with_speed = df[df['speed'].notna()]
print(f"Data points with speed: {len(df_with_speed)}")

create_scatter_plot(
    data=df_with_speed,
    x='recorded_at_time',
    y='speed',
    hue='line_ref',
    style='source_date',
    title='All Individual Speeds by Line and Journey (Time of Day) - Inbound',
    filename='all_speeds_scatter_plot.png'
)

print("Script completed. Check the console output for data statistics.")
