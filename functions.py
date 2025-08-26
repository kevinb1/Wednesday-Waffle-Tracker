import pandas as pd
import numpy as np
import re
import datetime
import json
import io
import requests
from bs4 import BeautifulSoup
import base64
import streamlit as st


def load_chat(file, pattern):
    # Store records temporarily in a list
    records = []

    if isinstance(file, str):
        f = open(file, encoding="utf-8")
    else:
        f = io.TextIOWrapper(file, encoding="utf-8")

    with f:
        for line in f:
            line = line.strip()
            matched = re.match(pattern, line)
            if matched:
                groups = matched.groups()

                # Handle cases with or without person
                if len(groups) == 3:
                    timestamp, person, message = groups
                else:  # if person is missing (system messages)
                    timestamp, person, message = groups[0], None, groups[1]

                records.append([timestamp, person, message])

    # Create DataFrame
    df = pd.DataFrame(records, columns=["timestamp", "person", "message"])

    return df


def find_chat_object(df, text_obj, start_date=None):
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%m-%Y %H:%M")
    if start_date:
        df = df[df["timestamp"] >= pd.to_datetime(start_date)]
    filterd_df = df[df["message"].str.contains(text_obj, case=False, na=False)]
    if filterd_df.empty:
        return df
    else:
        return filterd_df.reset_index(drop=True)


def df_to_json(df, persons, output_json=None):
    # Load person-color mapping
    color_lookup = {key: value["color"] for key, value in persons.items()}

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%m-%Y %H:%M")

    # Build events for calendar
    events = []
    for _, row in df.iterrows():
        person = row["person"]
        color = color_lookup.get(person, "gray")

        ts = row["timestamp"]
        start_iso = ts.strftime("%Y-%m-%dT%H:%M:%S")
        # Assuming each event lasts 1 minute
        end_iso = ts + datetime.timedelta(minutes=1)
        if end_iso.day > ts.day:
            end_iso = ts - datetime.timedelta(minutes=2)
        end_iso = end_iso.strftime("%Y-%m-%dT%H:%M:%S")

        events.append({
            "title": person,
            "start": start_iso,
            "end": end_iso,
            "color": color
        })

    # Load existing events if output_json provided
    existing_events = []
    # Keep only unique person+date combinations
    existing_keys = {(e["title"], e["start"][:10]) for e in existing_events}
    unique_new_events = [
        e for e in events if (e["title"], e["start"][:10]) not in existing_keys
    ]

    existing_events.extend(unique_new_events)

    # Return combined events instead of writing to a file
    return existing_events


def count_wednesdays(start_date, end_date=None):
    if end_date is None:
        end_date = datetime.date.today()

    # Ensure start_date <= end_date
    if start_date > end_date:
        return 0

    # Find the weekday of the start date (Monday=0, ..., Sunday=6)
    start_weekday = start_date.weekday()

    # Days until next Wednesday from start_date
    days_to_next_wed = (2 - start_weekday) % 7

    # First Wednesday on or after start_date
    first_wed = start_date + datetime.timedelta(days=days_to_next_wed)

    # Total days between first Wednesday and end_date
    total_days = (end_date - first_wed).days

    if total_days < 0:
        # start_date itself is after end_date
        return 0

    # Number of Wednesdays = 1 (first_wed) + every 7 days
    num_wednesdays = 1 + total_days // 7
    return num_wednesdays

def add_hbar(ax, y_label, value, color, label, left=0, alpha=1.0):
    bar = ax.barh(y_label, value, color=color, label=label, left=left, alpha=alpha)
    if value > 0:
        ax.bar_label(bar, label_type='center')
    return bar

def render_svg(svg):
    """Renders the given svg string."""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    html = r'<img src="data:image/svg+xml;base64,%s"/>' % b64
    st.write(html, unsafe_allow_html=True)

def link_to_google_sheets():
    pass


if __name__ == "__main__":
    pass