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


from functions import load_chat, find_chat_object, df_to_json, get_instagram_profile_picture, \
    count_wednesdays, add_hbar, render_svg

# --- Streamlit page config ---
st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")
st.title("Wednesday Waffle Tracker")

# if "authentication_status" not in st.session_state or st.session_state["authentication_status"] is not True:
#     st.warning("You must log in first. Redirecting…")
#     st.rerun()

# --- Load matplotlib stile ---
plt.style.use('matplotlib_style.mpstyle')


# --- Session state initialization ---
if "start_date_waffles" not in st.session_state:
    st.session_state.start_date_waffles = "2025-06-11"


if "wednesdays" not in st.session_state:
    # Convert string to date if needed
    start_date_str = st.session_state.start_date_waffles
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()

    st.session_state.wednesdays = count_wednesdays(start_date)

if "persons" not in st.session_state:
    usernames_dict = st.secrets["credentials"]["usernames"]

    # Build a dictionary with extra fields
    persons = {
        person: {
            "name": usernames_dict[person]["name"],
            "color": usernames_dict[person].get("color", "not set"),
            "instagram": usernames_dict[person].get("instagram", "not set")
        }
        for person in usernames_dict
    }
    st.session_state.persons = persons

if "events" not in st.session_state:
        st.session_state.events = []

# # --- Load calendar options and CSS ---
# with open("calendar_options.json") as f:
#     calendar_options = json.load(f)

# with open("custom.css") as f:
#     custom_css = f.read()

# --- Helper: preload and cache images locally ---
IMAGE_DIR = "cached_images"
os.makedirs(IMAGE_DIR, exist_ok=True)


def get_local_image(person):
    username = person["instagram"]
    url = get_instagram_profile_picture(username)
    return url


# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Options and Navigation")
    go_back = st.button("Go to Login")
    if go_back:
        st.switch_page("main.py")


# --- File upload and processing inside a form to avoid reruns ---
with st.form("chat_form"):
    chat_file = st.file_uploader("Upload WhatsApp chat export", type=["txt"])
    submit = st.form_submit_button("Process Chat")
    st.session_state.chat_file = chat_file

    if submit:
        if chat_file is None:
            msg = st.warning("Please upload a chat export file.")
            time.sleep(3)
            msg.empty()
        else:
            pattern = r"^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}) - (.*?): (.*)$"
            df = load_chat(chat_file, pattern)
            df = find_chat_object(
                df, "Video note", start_date=st.session_state.start_date_waffles)
            
            events_json = df_to_json(df, st.session_state.persons, st.session_state.events)

            # Update session states.json", "r", encoding="utf-8") as f:
            st.session_state.events = events_json

            msg = st.success("Waffles added to database")
            time.sleep(3)
            msg.empty()

# --- Display mathematties ---
st.header("Mathematties Statistics")
n = len(st.session_state.persons)
if n > 0:
    cols = st.columns(n)

    fig_bar, axs_bar = plt.subplots(1, 1, figsize=(6, 3))
    # st.pyplot(fig)

    events_loaded = False
    if "events" in st.session_state and st.session_state.events and "chat_file" in st.session_state:
        events_loaded = True
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
        
        df_waffles_grouped["on_time_waffles"]  = df_waffles_grouped["wednesday_count"] \
            - df_waffles_grouped["double_wednesday_waffles"]
        
        sort_order = df_waffles_grouped.groupby("title")["on_time_waffles"].sum().reset_index()
        sort_order.on_time_waffles =  sort_order.on_time_waffles * -1
        sort_order = sort_order.sort_values(
            by=["on_time_waffles", "title"], ascending=True)["title"].reset_index(drop=True).tolist()
        
        sort_order_reverse = {i : -i for i in range(n)}

        punishments = {}
    else:
        sort_order = st.session_state.persons
        
    for  i, name  in enumerate(sort_order):
        person  = st.session_state.persons[name]
        image = get_local_image(person)

        cols[i].image(image, use_container_width=True)
        cols[i].markdown(
            f"""
                <div style="display:flex; align-items:center; gap:6px;">
                    <div style="width:14px; height:14px; border-radius:50%; background:{person['color']};"></div>
                    <span><b>{name}</b></span>
                </div>
                """,
            unsafe_allow_html=True
        )
        break

        if events_loaded:
            filtered_df = df_waffles_grouped[df_waffles_grouped["title"]
                                            == name]

            # Count valid Wednesday waffles
            on_time_waffles = np.sum(
                filtered_df["wednesday_count"] - filtered_df["double_wednesday_waffles"])

            delta_waffles = int(on_time_waffles) - st.session_state.wednesdays

            late_waffles = np.sum(filtered_df.late_waffles)
            missed_waffles = st.session_state.wednesdays - (on_time_waffles + late_waffles)
            double_waffles = np.sum(filtered_df.double_wednesday_waffles)
            
            punishments[name] = late_waffles + missed_waffles + double_waffles
            # st.data_editor(filtered_df)

            cols[i].metric(
                label="On time Waffels",
                value=on_time_waffles,
                delta=int(on_time_waffles) - st.session_state.wednesdays,
                delta_color="normal"
            )

    #         # Populate bar chart
    #         add_hbar(axs_bar, 
    #                  name, 
    #                  missed_waffles, 
    #                  "#FF4B4B", 
    #                  "Waffles missed")
            
    #         add_hbar(axs_bar, 
    #                  name, 
    #                  late_waffles,
    #                  "#FF904B", 
    #                  "Waffles too late", 
    #                  left=missed_waffles)
            
    #         add_hbar(axs_bar, 
    #                  name, 
    #                  double_waffles, 
    #                  "#E6D947", 
    #                  "Double Waffles", 
    #                  left=missed_waffles + late_waffles, alpha=0.4)
            

    # col1, col2 = st.columns(2)
    
    # # --- Display bar cahart for punishment score ---
    # axs_bar.set_xlabel("Number of Waffels")
    # axs_bar.set_title("Punishment Score")
    # axs_bar.xaxis.set_major_locator(MaxNLocator(integer=True))
    # xmax = axs_bar.get_xlim()[1]
    # axs_bar.set_xlim(right=xmax * 1.1)
    
    # handles, labels = axs_bar.get_legend_handles_labels()
    # unique_labels = dict(zip(labels, handles))
    # axs_bar.legend(
    #     unique_labels.values(),
    #     unique_labels.keys(),
    #     loc="upper center",
    #     bbox_to_anchor=(0.5, -0.2),
    #     ncol=len(unique_labels)
    #     )
    # col1.pyplot(fig_bar)
    
    # --- Display "Waffle" chart ---
    # beer_path, attributes = svg2paths('beer-svgrepo-com.svg')
    # beer_marker = parse_path(attributes[0]['d'])
    # beer_marker.vertices -= beer_marker.vertices.mean(axis=0)
    # beer_marker = beer_marker.transformed(mpl.transforms.Affine2D().rotate_deg(180))
    # beer_marker = beer_marker.transformed(mpl.transforms.Affine2D().scale(-1,1))
    
    # fig_waffle, axs_waffle =plt.subplots(1, 1, figsize=(6, 3))
    # axs_waffle.scatter(0,
    #                    0, 
    #                    marker=beer_marker,
    #                    s=300)
    
    # col2.pyplot(fig_waffle)



# # --- Display calendar ---
# st.header("Calender")
# if st.session_state.events:
#     calendar(events=st.session_state.events,
#              options=calendar_options,
#              custom_css=custom_css,
#              key='calendar')
# else:
#     st.info("No events found. Please upload and process a chat export.")
