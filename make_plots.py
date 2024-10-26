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


# check for very low speeds
low_speed_rows = df[df['bus_lane_implied_speed'] < 1]  # Adjust the threshold as needed
if not low_speed_rows.empty:
    print("\nRows with very low average speed (< 1 km/h):")
    print(low_speed_rows[['line_ref', 'dated_vehicle_journey_ref', 'source_date', 'recorded_at_time', 'bus_lane_implied_speed', 'longitude', 'latitude']])
    print(f"Total rows with very low speed: {len(low_speed_rows)}")
else:
    print("\nNo rows found with very low average speed.")


def calculate_average_speed_and_slow_count(data, start_time, end_time, slow_threshold=8):
    mask = (data['recorded_at_time'].dt.time >= start_time) & (data['recorded_at_time'].dt.time < end_time)
    subset = data.loc[mask, 'bus_lane_implied_speed']
    avg_speed = subset.mean()
    slow_count = (subset < slow_threshold).sum()
    total_count = len(subset)
    slow_pct = (slow_count / total_count * 100) if total_count > 0 else 0
    return avg_speed, slow_pct

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
    
    # Calculate average speeds and slow counts for each time range
    morning_stats = calculate_average_speed_and_slow_count(data, datetime.strptime('08:00', '%H:%M').time(), datetime.strptime('09:30', '%H:%M').time())
    midday_stats = calculate_average_speed_and_slow_count(data, datetime.strptime('09:30', '%H:%M').time(), datetime.strptime('16:00', '%H:%M').time())
    evening_stats = calculate_average_speed_and_slow_count(data, datetime.strptime('16:00', '%H:%M').time(), datetime.strptime('18:30', '%H:%M').time())
    
    # Add vertical lines and text for each time range
    for time_str, stats, ha in [('08:00', morning_stats, 'right'), 
                                ('09:30', morning_stats, 'left'),
                                ('16:00', evening_stats, 'right'),
                                ('18:30', evening_stats, 'left')]:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        x_pos = today + pd.Timedelta(hours=time_obj.hour, minutes=time_obj.minute)
        ax.axvline(x=x_pos, linestyle='--', color='gray', alpha=0.5)
        if ha == 'left':
            ax.text(x_pos, ax.get_ylim()[1], f' Avg: {stats[0]:.2f} km/h\n Slow: {stats[1]:.2f}%', ha=ha, va='top', rotation=90)
    
    # Add text for midday average
    midday_x = today + pd.Timedelta(hours=12, minutes=45)  # 12:45, middle of 09:30-16:00
    ax.text(midday_x, ax.get_ylim()[1], f'Avg: {midday_stats[0]:.2f} km/h\nSlow: {midday_stats[1]:.2f}%', ha='center', va='top')
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    
create_scatter_plot(
    data=grouped,
    x='recorded_at_time',
    y='bus_lane_implied_speed',
    hue='line_ref',
    style='source_date',
    title='Average Speed by Line and Journey (Time of Day) - Inbound',
    filename='average_speed_scatter_plot.png'
)

print("Script completed. Check the console output for data statistics.")
