import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import pytz
import matplotlib.dates as mdates
import glob

LOCAL_TIMEZONE = 'Europe/London'

BUS_LANE = [-3.504520, -3.501827]
LAT_RANGE = [50.720832, 50.721658]

csv_files = glob.glob('csv_data/speeds/speeds_*.csv')

df_list = []
for file in csv_files:
    temp_df = pd.read_csv(file)
    temp_df['source_file'] = file  # Add a column to track the source file
    df_list.append(temp_df)
df = pd.concat(df_list, ignore_index=True)

# Convert 'recorded_at_time' to datetime and reset the date to today
df['recorded_at_time'] = pd.to_datetime(df['recorded_at_time'])
local_tz = pytz.timezone(LOCAL_TIMEZONE)
df['recorded_at_time'] = df['recorded_at_time'].dt.tz_convert(local_tz)

today = pd.Timestamp.today().normalize()
df['recorded_at_time'] = df['recorded_at_time'].apply(lambda x: today + pd.Timedelta(hours=x.hour, minutes=x.minute, seconds=x.second))

# Filter the DataFrame
df = df[(df['longitude'] >= BUS_LANE[0]) & (df['longitude'] <= BUS_LANE[1]) &
        (df['latitude'] >= LAT_RANGE[0]) & (df['latitude'] <= LAT_RANGE[1])]

# Group by line_ref and dated_vehicle_journey_ref, and get the first entry for each group
grouped = df.groupby(['line_ref', 'dated_vehicle_journey_ref', 'source_file']).first().reset_index()

# Create a scatter plot
fig, ax = plt.subplots(figsize=(12, 8))
sns.scatterplot(data=grouped, x='recorded_at_time', y='avg_speed', hue='line_ref', ax=ax)

# Customize the plot
plt.title('Average Speed by Line and Journey (Time of Day)')
plt.xlabel('Time of Day')
plt.ylabel('Average Speed (km/h)')

# Format x-axis to show time in HH:MM format, with one label per hour
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax.xaxis.set_major_locator(mdates.HourLocator())

# Set x-axis limits to cover a full day
ax.set_xlim(today, today + pd.Timedelta(days=1))

# Draw vertical lines at specified times
for time_str in ['08:00', '09:30', '16:00', '18:30']:
    time_obj = datetime.strptime(time_str, '%H:%M').time()
    ax.axvline(x=today + pd.Timedelta(hours=time_obj.hour, minutes=time_obj.minute), 
               linestyle='--', color='gray', alpha=0.5)

# Rotate x-axis labels for better readability
plt.xticks(rotation=45)

# Adjust layout to prevent cutting off labels
plt.tight_layout()

# Save the plot
plt.savefig('average_speed_scatter_plot.png')

# Display the plot (optional, remove if running in a non-interactive environment)
plt.show()

print("Scatter plot has been saved as 'average_speed_scatter_plot.png'")
