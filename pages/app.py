import streamlit as st
from streamlit_calendar import calendar
import json
import os
import requests
from PIL import Image
from io import BytesIO
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.ticker import MaxNLocator
from svgpathtools import svg2paths
from svgpath2mpl import parse_path
import datetime
import numpy as np
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_gsheets import GSheetsConnection


from functions import load_chat, find_chat_object, df_to_json, count_wednesdays, add_hbar, render_svg

# --- Streamlit page config ---
st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")
st.title("Wednesday Waffle Tracker")


# --- Load matplotlib stile ---
plt.style.use('matplotlib_style.mpstyle')


# --- Session state initialization ---
if "start_date_waffles" not in st.session_state:
    st.session_state.start_date_waffles = "2025-06-11"

# Add total number of wednesdays to session state
if "wednesdays" not in st.session_state:
    # Convert string to date if needed
    start_date_str = st.session_state.start_date_waffles
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()

    st.session_state.wednesdays = count_wednesdays(start_date)

# Add persons to session state
if "persons" not in st.session_state:
    usernames_dict = st.secrets["credentials"]["usernames"]

    # Build a dictionary with extra fields
    persons = {
        person: {
            "name": usernames_dict[person]["name"],
            "color": usernames_dict[person].get("color", "not set"),
            "picture_url": usernames_dict[person].get("picture_url", "not set")
        }
        for person in usernames_dict
    }
    st.session_state.persons = persons

# Add events to session state
if "events" not in st.session_state:
        st.session_state.events = []

# Update drinks_done in session state
if "drinks_done" not in st.session_state:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    
    st.session_state.drinks_done = dict(zip(df['name'], df['drinks_done']))


# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Opties en Navigatie")
    # Backt to login
    go_back = st.button("Terug naar login")
    if go_back:
        st.switch_page("main.py")
    
    # Calender view
    calender_page = st.button("Naar Kalender")
    if calender_page:
        st.switch_page("pages/calender.py")


# --- File upload and processing inside a form to avoid reruns ---
with st.form("chat_form"):
    # Create file uploader and add to sesion state
    chat_file = st.file_uploader("Upload WhatsApp chat export", type=["txt"])
    submit = st.form_submit_button("Chat verwerken")
    st.session_state.chat_file = chat_file

    # Submit button pressed
    if submit:
        # Check if file is uploaded
        if chat_file is None:
            # No file uploaded, show message
            msg = st.warning("Upload een bestand")
            time.sleep(3)
            msg.empty()
        else:
            # File uploaded, so create message pattern
            pattern = r"^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}) - (.*?): (.*)$"
            # Split txt into messages and create df
            df = load_chat(chat_file, pattern)
            # Filter video notes
            df = find_chat_object(
                df, "Video note", start_date=st.session_state.start_date_waffles)
            
            # Create a json for the calender
            events_json = df_to_json(df, st.session_state.persons, st.session_state.events)

            # Update session states.json", "r", encoding="utf-8") as f:
            st.session_state.events = events_json

            msg = st.success("Chat verwerkt en toegevoegd")
            time.sleep(3)
            msg.empty()

# --- Display mathematties ---
st.header("Mathematties Ranking")
n = len(st.session_state.persons)
if n > 0:
    cols = st.columns(n)

    fig_bar, axs_bar = plt.subplots(1, 1, figsize=(6, 3))
    # st.pyplot(fig)

    # Check for loaded events
    events_loaded = False
    if "events" in st.session_state and st.session_state.events and "chat_file" in st.session_state:
        events_loaded = True
        
        # Create dataframe
        df_waffles = pd.DataFrame(st.session_state.events)
        df_waffles.drop(columns=["end"], inplace=True)
        df_waffles.start = pd.to_datetime(df_waffles.start)
        
        # Determine which day of the week the video was sent
        df_waffles["day"] = df_waffles.start.dt.day_name()
        df_waffles["date"] = df_waffles.start.dt.date
        
        # Group waffles by calendar week
        df_waffles["week_nr"] = df_waffles.start.dt.isocalendar().week

        # Flag waffles that were sent on Wednesday as on time
        df_waffles["wednesday_entries"] = (
            df_waffles["day"] == "Wednesday").astype(int)

        df_waffles["not_wednesday_entries"] = (
            df_waffles["day"] != "Wednesday").astype(int)

        # Check if multiple waffels are sent in one week
        df_waffles_grouped = df_waffles.groupby(["week_nr", "title"]).agg(
            wednesday_count=("wednesday_entries", "sum"),
            not_wednesday_count=("not_wednesday_entries", "sum")).reset_index()

        # Late waffles: no Wednesday video, but there are non-Wednesday videos
        df_waffles_grouped["late_waffles"] = 0
        df_waffles_grouped.loc[
            (df_waffles_grouped["wednesday_count"] == 0) & (
                df_waffles_grouped["not_wednesday_count"] > 0),
            "late_waffles"
        ] = 1

        # Double Wednesday waffles: count how many extra Wednesday videos there are beyond the first one
        df_waffles_grouped["double_wednesday_waffles"] = 0
        df_waffles_grouped.loc[
            df_waffles_grouped["wednesday_count"] > 1,
            "double_wednesday_waffles"
        ] = df_waffles_grouped["wednesday_count"] - 1

        # Other waffles: at least one Wednesday video AND at least one non-Wednesday video in the same week
        df_waffles_grouped["other_waffles"] = 0
        df_waffles_grouped.loc[
            (df_waffles_grouped["wednesday_count"] > 0) & (
                df_waffles_grouped["not_wednesday_count"] > 0),
            "other_waffles"
        ] = 1
        
        # Calcualte the number of on time waffles
        df_waffles_grouped["on_time_waffles"]  = df_waffles_grouped["wednesday_count"] \
            - df_waffles_grouped["double_wednesday_waffles"]
        
        # Determine sort order by on time waffles
        sort_order = df_waffles_grouped.groupby("title")["on_time_waffles"].sum().reset_index()
        sort_order.on_time_waffles =  sort_order.on_time_waffles * -1
        sort_order = sort_order.sort_values(
            by=["on_time_waffles", "title"], ascending=True)["title"].reset_index(drop=True).tolist()
        
        # Create reverse sort order
        sort_order_reverse = {i : -i for i in range(n)}

        # Initiate dictionary for punishment score
        punishments = {}
    else:
        sort_order = st.session_state.persons
    
    # Show mathematties
    for  i, name  in enumerate(sort_order):
        cols[i].image(st.session_state.persons[name]["picture_url"],
                 use_container_width=True,
        )
        
        cols[i].markdown(
            f"""
                <div style="display:flex; align-items:center; gap:6px;">
                    <div style="width:14px; height:14px; border-radius:50%; background:{st.session_state.persons[name]['color']};"></div>
                    <span><b>{name}</b></span>
                </div>
                """,
            unsafe_allow_html=True
        )

        # Check for loaded events
        if events_loaded:
            # Filter on name
            filtered_df = df_waffles_grouped[df_waffles_grouped["title"]
                                            == name]

            # Count valid Wednesday waffles
            on_time_waffles = np.sum(
                filtered_df["wednesday_count"] - filtered_df["double_wednesday_waffles"])

            delta_waffles = int(on_time_waffles) - st.session_state.wednesdays

            late_waffles = np.sum(filtered_df.late_waffles)
            missed_waffles = st.session_state.wednesdays - (on_time_waffles + late_waffles)
            double_waffles = np.sum(filtered_df.double_wednesday_waffles)
            
            # Add punishment score
            punishments[name] = late_waffles + missed_waffles + double_waffles

            # Create metric
            cols[i].metric(
                label="Optijd verstuurt",
                value=on_time_waffles,
                delta=int(on_time_waffles) - st.session_state.wednesdays,
                delta_color="normal",
                border=True
            )

            # Populate bar chart
            add_hbar(axs_bar, 
                     name, 
                     missed_waffles, 
                     "#FF4B4B", 
                     "Gemist")
            
            add_hbar(axs_bar, 
                     name, 
                     late_waffles,
                     "#FF904B", 
                     "Te laat", 
                     left=missed_waffles)
            
            add_hbar(axs_bar, 
                     name, 
                     double_waffles, 
                     "#E6D947", 
                     "Andere video notes", 
                     left=missed_waffles + late_waffles, alpha=0.4)
    st.markdown("---")
    if events_loaded:
        # --- Show statistics
        st.header("Statistieken")
        # Load from json
        df_events = pd.DataFrame(st.session_state.events)
        df_events = df_events.rename(columns={"start": "timestamp"})
        df_events.timestamp = pd.to_datetime(df_events.timestamp)
        df_events = df_events.drop(["end", "color"], axis=1)
        
    # Determine which day of the week the video was sent
        df_events["day"] = df_events.timestamp.dt.day_name()
        df_events["day_nr"] = df_events.timestamp.dt.dayofweek
        df_events["date"] = df_events.timestamp.dt.date
        df_events["time"] = df_events.timestamp.dt.time
        
        # Group waffles by calendar week
        df_events["week_nr"] = df_events.timestamp.dt.isocalendar().week
        
        
        df_wednesday = df_events.loc[df_events.day == "Wednesday"]

        
        # --- Everybody sent waffle on time
        st.subheader("Iedereen Optijd")
        # Put to group
        df_all_sent = df_wednesday[["title", "week_nr"]].groupby("week_nr")["title"].apply(set).reset_index()
        # Filter on all persons sent
        df_all_sent = df_all_sent[df_all_sent['title'].apply(len) == len(st.session_state.persons)]
        st.metric(
            label="Aantal weken",
                value=len(df_all_sent),
                delta=len(df_all_sent) - st.session_state.wednesdays,
                delta_color="normal",
            )
        
        col1, col2, col3, col4 = st.columns(4)
        # --- Earliest Waffle
        col1.subheader("Vroegste Waffle")
        earliest_waffle = df_wednesday.sort_values(by="time").reset_index(drop=True).loc[0]
        col1.image(st.session_state.persons[earliest_waffle.title]["picture_url"],
                 width=200,
                 caption =f"Verstuurd om { earliest_waffle.time}")
        
        # --- Latest Waffle
        col2.subheader("Laatste Waffle")
        # Get the latest timestemp per week
        df_latest_waffle = df_events.sort_values(by=["timestamp"]).drop_duplicates("week_nr", keep="last")
        
        latest_waffle = df_latest_waffle.sort_values(by=["day_nr", "timestamp"]).reset_index(drop=True).loc[len(df_latest_waffle) - 1]
        
        col2.image(st.session_state.persons[latest_waffle.title]["picture_url"],
                   width=200,
                 caption =f"Verstuurd op {latest_waffle.day}, om {latest_waffle.time}")
        
         # --- Most often First (Vaakst als Eerst)
        col3.subheader("Vaakst als Eerste")
        # Count how many times each person was the earliest per day
        first_counts = df_wednesday.sort_values("timestamp").groupby("week_nr").first()["title"].value_counts()
        most_first_person = first_counts.idxmax()
        col3.image(
            st.session_state.persons[most_first_person]["picture_url"],
            width=200,
            caption=f"{first_counts.max()} keer"
        )
        
         # --- Last person 
        col4.subheader("Vaakst als Laatste")
        # Count how many times each person was the latest per week (only Wednesday)
        last_counts = df_events.sort_values("timestamp").groupby("week_nr").last()["title"].value_counts()
        most_last_person = last_counts.idxmax()

        col4.image(
            st.session_state.persons[most_last_person]["picture_url"],
            width=200,
            caption=f"{last_counts.max()} keer"
        )
        st.markdown("---")
        # --- Show how many drinks must be done
        st.header("Straf Atjes")
        col1, col2 = st.columns(2)

        # --- Display bar cahart for punishment score ---
        axs_bar.set_xlabel("Straf Atjes")
        axs_bar.xaxis.set_major_locator(MaxNLocator(integer=True))
        xmax = axs_bar.get_xlim()[1]
        axs_bar.set_xlim(right=xmax * 1.1)
        
        handles, labels = axs_bar.get_legend_handles_labels()
        unique_labels = dict(zip(labels, handles))
        axs_bar.legend(
            unique_labels.values(),
            unique_labels.keys(),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.2),
            ncol=len(unique_labels)
            )
        col1.subheader("Penalties")
        col1.pyplot(fig_bar)
    
        # --- Display "Waffle" chart ---
        drinks_to_go = {}
        for key, value in st.session_state.drinks_done.items():
            filtered_df = df_waffles_grouped[df_waffles_grouped["title"]
                                            == key]

            # Count valid Wednesday waffles
            on_time_waffles = np.sum(
                filtered_df["wednesday_count"] - filtered_df["double_wednesday_waffles"])

            drinks_to_go[key] = (st.session_state.wednesdays - int(on_time_waffles)) - value
            
        # Sort
        drinks_to_go = sorted(drinks_to_go.items(), key=lambda x: x[1], reverse=True)
        
        # Show number of drinks
        col2.subheader("Atjes te gaan")
        with col2:
            for item in drinks_to_go:
                if item[1] > 0:
                    string = "🍾" * int(item[1])
                    st.write(f"**{item[0]}**: {string}")
