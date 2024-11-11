import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import matplotlib.dates as mdates
import pytz
import glob
import re
import sys
from scipy import stats
import numpy as np

LOCAL_TIMEZONE = 'Europe/London'  
SLOW_THRESHOLD = 11

LOCATION = sys.argv[1]

csv_files = glob.glob(f'csv_data/speeds/{LOCATION}/speeds_*.csv')

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

# report slow speeds
low_speed_rows = df[df['implied_speed'] < SLOW_THRESHOLD]  # Adjust the threshold as needed
if not low_speed_rows.empty:
    print(f"\nRows with slow average speed: (< {SLOW_THRESHOLD} km/h)")
    low_speed_data = low_speed_rows[['line_ref', 'dated_vehicle_journey_ref', 'source_date', 'recorded_at_time', 'implied_speed', 'latitude', 'longitude']]
    print(low_speed_data)
    print(f"Total rows with slow speed: {len(low_speed_rows)}")
    low_speed_data.to_csv('csv_data/slow_speeds.csv', index=False)
else:
    print("\nNo rows found with slow speed.")


def calculate_stats_and_slow_count(data, start_time, end_time, slow_threshold=SLOW_THRESHOLD):
    mask = (data['recorded_at_time'].dt.time >= start_time) & (data['recorded_at_time'].dt.time < end_time)
    subset = data.loc[mask, 'implied_speed']
    avg_speed = subset.mean()
    slow_count = (subset < slow_threshold).sum()
    total_count = len(subset)
    slow_pct = (slow_count / total_count * 100) if total_count > 0 else 0
    return avg_speed, slow_pct, total_count

def create_scatter_plot(data, x, y, hue, style, title, filename):
    if len(data) == 0:
        print(f"No data to plot for {filename}")
        return
    
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.scatterplot(data=data, x=x, y=y, hue=hue, style=style, ax=ax)
    
    plt.title(title)
    plt.xlabel('Time of Day')
    plt.ylabel('Speed (km/h)')
    plt.ylim(bottom=0)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator())
    
    # Calculate average speeds and slow counts for each time range
    morning_stats = calculate_stats_and_slow_count(data, datetime.strptime('08:00', '%H:%M').time(), datetime.strptime('09:30', '%H:%M').time())
    midday_stats = calculate_stats_and_slow_count(data, datetime.strptime('09:30', '%H:%M').time(), datetime.strptime('16:00', '%H:%M').time())
    evening_stats = calculate_stats_and_slow_count(data, datetime.strptime('16:00', '%H:%M').time(), datetime.strptime('18:30', '%H:%M').time())
    
    # Add vertical lines and text for each time range
    for time_str, stats, ha in [('08:00', morning_stats, 'right'), 
                                ('09:30', morning_stats, 'left'),
                                ('16:00', evening_stats, 'right'),
                                ('18:30', evening_stats, 'left')]:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        x_pos = today + pd.Timedelta(hours=time_obj.hour, minutes=time_obj.minute)
        ax.axvline(x=x_pos, linestyle='--', color='gray', alpha=0.5)
        if ha == 'left':
            ax.text(
                x_pos, ax.get_ylim()[1], f' Avg: {stats[0]:.2f} km/h\nSlow: {stats[1]:.2f}%',
                ha=ha, va='top', rotation=90
                )
    
    # Add text for midday average
    midday_x = today + pd.Timedelta(hours=12, minutes=45)  # 12:45, middle of 09:30-16:00
    ax.text(
        midday_x, ax.get_ylim()[1], f'Avg: {midday_stats[0]:.2f} km/h\nSlow: {midday_stats[1]:.2f}%',
        ha='center', va='top'
        )
    
    # line for slow threshold
    ax.axhline(y=SLOW_THRESHOLD, linestyle='--', color='red', alpha=0.5)

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


def create_histogram(data, start_time, end_time, title, filename):
    if len(data) == 0:
        print(f"No data to plot for {filename}")
        return
    
    # Filter data for the time period
    mask = (data['recorded_at_time'].dt.time >= datetime.strptime(start_time, '%H:%M').time()) & \
           (data['recorded_at_time'].dt.time < datetime.strptime(end_time, '%H:%M').time())
    period_data = data.loc[mask]
    
    if len(period_data) == 0:
        print(f"No data for period {start_time} to {end_time}")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create histogram with 2km/h wide bins starting from an odd number
    max_speed = int(period_data['implied_speed'].max() + 2)  # Add 2 to ensure we include the max value
    bins = range(-1, max_speed + 1, 2)
    
    plt.hist(period_data['implied_speed'], bins=bins, edgecolor='black')
    
    plt.title(f'{title}\n({start_time} - {end_time})')
    plt.xlabel('Speed (km/h)')
    plt.ylabel('Number of Vehicles')
    
    # Add vertical line for slow threshold
    plt.axvline(x=SLOW_THRESHOLD, color='red', linestyle='--', label=f'Slow threshold ({SLOW_THRESHOLD} km/h)')
    plt.legend(loc='upper left', bbox_to_anchor=(0.02, 0.98))
    
    # Add text with statistics
    slow_pct = (period_data['implied_speed'] < SLOW_THRESHOLD).mean() * 100
    mean_speed = period_data['implied_speed'].mean()
    median_speed = period_data['implied_speed'].median()

    stats_text = f'Mean: {mean_speed:.1f} km/h\nMedian: {median_speed:.1f} km/h\nSlow %: {slow_pct:.1f}%'
    plt.text(0.95, 0.95, stats_text,
             transform=ax.transAxes,
             verticalalignment='top',
             horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


def create_dual_histogram(data, title, filename):
    if len(data) == 0:
        print(f"No data to plot for {filename}")
        return
    
    # Filter data for both time periods
    morning_mask = (data['recorded_at_time'].dt.time >= datetime.strptime('08:00', '%H:%M').time()) & \
                  (data['recorded_at_time'].dt.time < datetime.strptime('09:30', '%H:%M').time())
    midday_mask = (data['recorded_at_time'].dt.time >= datetime.strptime('09:30', '%H:%M').time()) & \
                  (data['recorded_at_time'].dt.time < datetime.strptime('16:00', '%H:%M').time())
    
    morning_data = data.loc[morning_mask, 'implied_speed']
    midday_data = data.loc[midday_mask, 'implied_speed']
    
    if len(morning_data) == 0 or len(midday_data) == 0:
        print("No data for one or both time periods")
        return

    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Create histogram with 2km/h wide bins starting from an odd number
    max_speed = int(max(morning_data.max(), midday_data.max()) + 2)
    bins = range(-1, max_speed + 1, 2)
    
    # Plot histograms with density=True to make area=1 for distribution fitting
    plt.hist(morning_data, bins=bins, alpha=0.6, density=True, 
            label='Morning Peak (08:00-09:30)',
            edgecolor='black', color='skyblue')
    plt.hist(midday_data, bins=bins, alpha=0.6, density=True,
            label='Midday (09:30-16:00)',
            edgecolor='black', color='orange')
    
    # Kernel Density Estimation
    x_range = np.linspace(0, max_speed, 100)
    morning_kde = stats.gaussian_kde(morning_data)
    midday_kde = stats.gaussian_kde(midday_data)
    
    plt.plot(x_range, morning_kde(x_range), 'b--', linewidth=2,
            label='Morning KDE')
    plt.plot(x_range, midday_kde(x_range), 'r--', linewidth=2,
            label='Midday KDE')
    
    plt.title(title)
    plt.xlabel('Speed (km/h)')
    plt.ylabel('Density')
    
    # Add vertical line for slow threshold
    plt.axvline(x=SLOW_THRESHOLD, color='red', linestyle=':', 
                label=f'Slow threshold ({SLOW_THRESHOLD} km/h)')
    
    # Add statistics for both periods
    morning_stats = f'Morning Peak:\n' \
                   f'Mean: {morning_data.mean():.1f} km/h\n' \
                   f'Median: {morning_data.median():.1f} km/h\n' \
                   f'Std Dev: {morning_data.std():.1f} km/h\n' \
                   f'Slow %: {(morning_data < SLOW_THRESHOLD).mean()*100:.1f}%'
    
    midday_stats = f'Midday:\n' \
                   f'Mean: {midday_data.mean():.1f} km/h\n' \
                   f'Median: {midday_data.median():.1f} km/h\n' \
                   f'Std Dev: {midday_data.std():.1f} km/h\n' \
                   f'Slow %: {(midday_data < SLOW_THRESHOLD).mean()*100:.1f}%'
    
    # Position stats boxes
    plt.text(0.95, 0.95, morning_stats,
             transform=ax.transAxes,
             verticalalignment='top',
             horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='skyblue', alpha=0.1))
    
    plt.text(0.95, 0.60, midday_stats,
             transform=ax.transAxes,
             verticalalignment='top',
             horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='orange', alpha=0.1))
    
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left', bbox_to_anchor=(0.02, 0.98))
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


def create_speed_cdf_plot(data, title, filename):
    if len(data) == 0:
        print(f"No data to plot for {filename}")
        return
    
    # Filter data for both time periods
    morning_mask = (data['recorded_at_time'].dt.time >= datetime.strptime('08:00', '%H:%M').time()) & \
                  (data['recorded_at_time'].dt.time < datetime.strptime('09:30', '%H:%M').time())
    midday_mask = (data['recorded_at_time'].dt.time >= datetime.strptime('09:30', '%H:%M').time()) & \
                  (data['recorded_at_time'].dt.time < datetime.strptime('16:00', '%H:%M').time())
    
    morning_data = data.loc[morning_mask, 'implied_speed']
    midday_data = data.loc[midday_mask, 'implied_speed']
    
    if len(morning_data) == 0 or len(midday_data) == 0:
        print("No data for one or both time periods")
        return

    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Create evaluation points
    max_speed = int(max(morning_data.max(), midday_data.max()) + 1)
    x_range = np.linspace(0, max_speed, 200)
    
    # Calculate KDE for both periods
    morning_kde = stats.gaussian_kde(morning_data)
    midday_kde = stats.gaussian_kde(midday_data)
    
    # Calculate CDFs by integrating the KDEs
    morning_cdf = np.array([morning_kde.integrate_box_1d(0, x) for x in x_range])
    midday_cdf = np.array([midday_kde.integrate_box_1d(0, x) for x in x_range])
    
    # Plot CDFs
    plt.plot(x_range, morning_cdf, 'b-', linewidth=2,
            label='Morning Peak (08:00-09:30)')
    plt.plot(x_range, midday_cdf, 'r-', linewidth=2,
            label='Midday (09:30-16:00)')
    
    plt.title(title)
    plt.xlabel('Speed (km/h)')
    plt.ylabel('Cumulative Probability')
    
    # Add vertical line for slow threshold
    plt.axvline(x=SLOW_THRESHOLD, color='red', linestyle=':', 
                label=f'Slow threshold ({SLOW_THRESHOLD} km/h)')
    
    # Add horizontal grid lines at 0.25, 0.5, 0.75
    for p in [0.25, 0.5, 0.75]:
        plt.axhline(y=p, color='gray', linestyle='--', alpha=0.3)
    
    # Add statistics
    morning_slow_prob = morning_kde.integrate_box_1d(0, SLOW_THRESHOLD)
    midday_slow_prob = midday_kde.integrate_box_1d(0, SLOW_THRESHOLD)
    
    stats_text = (f'Probability of slow speed:\n'
                 f'Morning Peak: {morning_slow_prob:.1%}\n'
                 f'Midday: {midday_slow_prob:.1%}')
    
    plt.text(0.98, 0.02, stats_text,
             transform=ax.transAxes,
             verticalalignment='bottom',
             horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left', bbox_to_anchor=(0.02, 0.98))
    
    # Set axis limits
    plt.xlim(0, max_speed)
    plt.ylim(0, 1)
    
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


create_speed_cdf_plot(
    data=grouped,
    title='Cumulative Speed Distribution',
    filename='plots/speed_cdf.png'
)

create_dual_histogram(
    data=grouped,
    title=f'Speed Distribution - {LOCATION}',
    filename=f'plots/speed_histogram_{LOCATION}.png'
)

create_histogram(
    data=grouped,
    start_time='08:00',
    end_time='09:30',
    title=f'Morning Peak Speed Distribution - {LOCATION}',
    filename=f'plots/morning_speed_histogram_{LOCATION}.png'
)

create_histogram(
    data=grouped,
    start_time='09:30',
    end_time='16:00',
    title=f'Midday Speed Distribution - {LOCATION}',
    filename=f'plots/midday_speed_histogram_{LOCATION}.png'
)

create_scatter_plot(
    data=grouped,
    x='recorded_at_time',
    y='implied_speed',
    hue='line_ref',
    style='source_date',
    title=f'Average Speed - Inbound - {LOCATION}',
    filename=f'plots/average_speed_{LOCATION}.png'
)

print("Script completed. Check the console output for data statistics.")
