# pylint: disable=missing-module-docstring, missing-function-docstring

import os
from collections import Counter
from datetime import datetime

import dotenv
import matplotlib.pyplot as plt
import pytz
import seaborn as sns
from azure.storage.blob import BlobClient, ContentSettings
from matplotlib.dates import DateFormatter

dotenv.load_dotenv()


def visualize_dates(datetimes, file_name):
    dates = [dt.date() for dt in datetimes]
    date_counts = Counter(dates)

    unique_dates = sorted(date_counts.keys())
    task_counts = [date_counts[date] for date in unique_dates]

    sns.set(style="darkgrid")
    plt.figure(figsize=(10, 6))

    plt.bar(unique_dates, task_counts, width=0.8, alpha=0.8)

    plt.title("Pages Read by Date")
    plt.xlabel("Date")
    plt.ylabel("Number of Pages Read")

    plt.gcf().autofmt_xdate()
    plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))

    plt.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.savefig(file_name)
    plt.close()


def visualize_dates_by_date_and_time(dates, file_name):
    copenhagen_tz = pytz.timezone("Europe/Copenhagen")

    dates_only = []
    times_only = []

    for date in dates:
        if date.tzinfo is None:
            date = pytz.utc.localize(date).astimezone(copenhagen_tz)
        elif date.tzinfo != copenhagen_tz:
            date = date.astimezone(copenhagen_tz)

        dates_only.append(date.date())

        time = date.time()
        fractional_hour = time.hour + time.minute/60.0 + time.second/3600.0
        times_only.append(fractional_hour)

    sns.set(style="darkgrid")
    plt.figure(figsize=(12, 8))

    plt.scatter(dates_only, times_only, alpha=0.6)

    plt.title("Pages Read by Date and Time (Copenhagen)")
    plt.xlabel("Date")
    plt.ylabel("Time of Day (24-hour)")

    plt.yticks(range(0, 25, 2))
    plt.ylim(24, 0)

    plt.xticks(rotation=45)

    plt.grid(True, linestyle="--", alpha=0.7)

    plt.tight_layout()

    plt.savefig(file_name)
    plt.close()


def upload_to_blob(file_name):
    blob_client = BlobClient.from_connection_string(
        os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        container_name="public",
        blob_name=file_name)
    if blob_client.exists():
        blob_client.delete_blob()
    with open(file_name, "rb") as data:
        blob_client.upload_blob(
            data, content_settings=ContentSettings(content_type="image/png"))


def main():
    todo_files = []
    for root, _, files in os.walk("todos"):
        for file in files:
            if file.endswith(".todo"):
                todo_files.append(os.path.join(root, file))

    done_tasks = []
    for file in todo_files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("✔") and "@done(" in line:
                    done_tasks.append(line)

    dates = []
    for task in done_tasks:
        date = task.split("@done(")[1].split(")")[0]
        date = datetime.strptime(date, "%y-%m-%d %H:%M")
        dates.append(date)

    dates.sort()

    tasks_done_png = "images/tasks_done.png"
    visualize_dates(dates, tasks_done_png)
    upload_to_blob(tasks_done_png)

    tasks_done_by_date_and_time_png = "images/tasks_done_by_date_and_time.png"
    visualize_dates_by_date_and_time(dates, tasks_done_by_date_and_time_png)
    upload_to_blob(tasks_done_by_date_and_time_png)


if __name__ == "__main__":
    main()
