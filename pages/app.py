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
import copy
import plotly.express as px
import plotly.graph_objects as go


from functions import load_chat, find_chat_object, count_wednesdays, add_hbar, render_svg

# --- Streamlit page config ---
st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")
st.title("Wednesday Waffle Tracker")


# --- Load matplotlib stile ---
plt.style.use('matplotlib_style.mpstyle')



# --- Session state initialization ---
conn = st.connection("gsheets", type=GSheetsConnection)
if "start_date_waffles" not in st.session_state:
    st.session_state.start_date_waffles = "2025-06-11"

# Update drinks_done in session state
if "drinks_done" not in st.session_state:
    df_adjes = conn.read(worksheet="adjes_gedaan")
    st.session_state.drinks_done = df_adjes

# Update timeseries in session state
df_ts = conn.read(worksheet="score")
st.session_state.timeseries = df_ts

# Add total number of wednesdays to session state
if "wednesdays" not in st.session_state:
    # Convert string to date if needed
    start_date_str = st.session_state.start_date_waffles
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    
    if st.session_state.timeseries is not None and not st.session_state.timeseries.empty:
        series = pd.to_datetime(st.session_state.timeseries.timestamp, format="%d-%m-%Y %H:%M:%S")
        end_date = series.max().date()
    else:
        end_date = None
        
    st.session_state.wednesdays = count_wednesdays(start_date, 
                                                   end_date=end_date)

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



# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Opties en Navigatie")
    # Backt to login
    go_back = st.button("Terug naar login")
    if go_back:
        st.switch_page("main.py")
    
    # Calender view
    editor_page = st.button("Atjes invoeren")
    if editor_page:
        st.switch_page("pages/editor.py")
    
    refresh = st.button("Refresh", type="primary")
    if refresh:
        st.cache_data.clear()
        st.rerun()  


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
            
            # Only keep timestamp and person
            df = df[["timestamp", "person"]]
            df.timestamp.astype(str)
            
            
            # Update timeseries 
            old_ts = st.session_state.timeseries
            updated_ts = pd.concat([old_ts, df])
            updated_ts = updated_ts.drop_duplicates(subset=["timestamp", "person"]).reset_index(drop=True)
            
            # Update session state and Gsheets
            st.session_state.timeseries = updated_ts
            conn.update(data=updated_ts, worksheet="score")
            
            
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
    if st.session_state.timeseries is not None and not st.session_state.timeseries.empty:
        events_loaded = True

        
        # Create dataframe
        df_waffles = copy.deepcopy(st.session_state.timeseries)
        df_waffles.timestamp = pd.to_datetime(df_waffles.timestamp, format="%d-%m-%Y %H:%M:%S")
        
        
        # Determine which day of the week the video was sent
        df_waffles["day"] = df_waffles.timestamp.dt.day_name()
        df_waffles["date"] = df_waffles.timestamp.dt.date
        
        
        
        # Group waffles by calendar week
        df_waffles["week_nr"] = (
            df_waffles['timestamp'].dt.isocalendar().year.astype(str) + '-' +
            df_waffles['timestamp'].dt.isocalendar().week.astype(str).str.zfill(2))
        


        # Flag waffles that were sent on Wednesday as on time
        df_waffles["wednesday_entries"] = (df_waffles["day"] == "Wednesday").astype(int)

        df_waffles["not_wednesday_entries"] = (df_waffles["day"] != "Wednesday").astype(int)
        
        # Check if multiple waffels are sent in one week
        df_waffles_grouped = df_waffles.groupby(["week_nr", "person"]).agg(
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
        sort_order = df_waffles_grouped.groupby("person")["on_time_waffles"].sum().reset_index()
        sort_order.on_time_waffles =  sort_order.on_time_waffles * -1
        sort_order = sort_order.sort_values(
            by=["on_time_waffles", "person"], ascending=True)["person"].reset_index(drop=True).tolist()
        
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
            filtered_df = df_waffles_grouped[df_waffles_grouped["person"]
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

    st.markdown("---")
    if events_loaded:
        # --- Show statistics
        st.header("Statistieken")
        # Load from json
        df_events = copy.deepcopy(st.session_state.timeseries)
        df_events.timestamp = pd.to_datetime(df_events.timestamp, format="%d-%m-%Y %H:%M:%S")
        
    # Determine which day of the week the video was sent
        df_events["day"] = df_events.timestamp.dt.day_name()
        df_events["day_nr"] = df_events.timestamp.dt.dayofweek
        df_events["date"] = df_events.timestamp.dt.date
        df_events["time"] = df_events.timestamp.dt.time
        
        # Group waffles by calendar week
        df_events["week_nr"] = (
            df_waffles['timestamp'].dt.isocalendar().year.astype(str) + '-' +
            df_waffles['timestamp'].dt.isocalendar().week.astype(str).str.zfill(2))
        
        df_wednesday = df_events.loc[df_events.day == "Wednesday"]

        
        # --- Everybody sent waffle on time
        st.subheader("Iedereen Optijd")
        # Put to group
        df_all_sent = df_wednesday[["person", "week_nr"]].groupby("week_nr")["person"].apply(set).reset_index()
        # Filter on all persons sent
        df_all_sent = df_all_sent[df_all_sent['person'].apply(len) == len(st.session_state.persons)]
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
        col1.image(st.session_state.persons[earliest_waffle.person]["picture_url"],
                 width=200,
                 caption =f"Verstuurd om { earliest_waffle.time}")
        
        # --- Latest Waffle
        col2.subheader("Laatste Waffle")
        # Get the latest timestemp per week
        df_latest_waffle = df_events.sort_values(by=["timestamp"]).drop_duplicates("week_nr", keep="last")
        
        latest_waffle = df_latest_waffle.sort_values(by=["day_nr", "timestamp"]).reset_index(drop=True).loc[len(df_latest_waffle) - 1]
        
        col2.image(st.session_state.persons[latest_waffle.person]["picture_url"],
                   width=200,
                 caption =f"Verstuurd op {latest_waffle.day}, om {latest_waffle.time}")
        
         # --- Most often First (Vaakst als Eerst)
        col3.subheader("Vaakst als Eerste")
        # Count how many times each person was the earliest per day
        first_counts = df_wednesday.sort_values("timestamp").groupby("week_nr").first()["person"].value_counts()
        most_first_person = first_counts.idxmax()
        col3.image(
            st.session_state.persons[most_first_person]["picture_url"],
            width=200,
            caption=f"{first_counts.max()} keer"
        )
        
         # --- Last person 
        col4.subheader("Vaakst als Laatste")
        # Count how many times each person was the latest per week (only Wednesday)
        last_counts = df_events.sort_values("timestamp").groupby("week_nr").last()["person"].value_counts()
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
        col1.subheader("Verdeling")
        col1.pyplot(fig_bar)
    
        # --- Display "Waffle" chart ---
        drinks_to_go = {}
        df_adjes = st.session_state.drinks_done
        for name in st.session_state.drinks_done.name.unique():
            filtered_df = df_waffles_grouped[df_waffles_grouped["person"]== name]

            # Count valid Wednesday waffles
            on_time_waffles = np.sum(
                filtered_df["wednesday_count"] - filtered_df["double_wednesday_waffles"])

            df_person_grouped = df_adjes[df_adjes["name"] == name].groupby("name").sum().reset_index() 
            drinks_to_go[df_person_grouped.name.values[0]] = st.session_state.wednesdays - \
                                                             on_time_waffles + \
                                                             df_person_grouped.drinks_done.values[0] 

        # Sort
        drinks_to_go = sorted(drinks_to_go.items(), key=lambda x: x[1], reverse=True)
        
        # Show number of drinks
        col2.subheader("Atjes te gaan")
        with col2:
            for item in drinks_to_go:
                if item[1] > 0:
                    string = "🍾" * int(item[1])
                    st.write(f"**{item[0]}**: {string} ({item[1]:.0f})")

st.markdown("---")
# Timeseries
st.title("Tijdreeksen")

# Radar for adjes waffles
chart_select = st.radio("Selecteer Meassure", ["Gemiste Waffles", "Straf Atjes"], horizontal=True)

date_range = pd.date_range(start=st.session_state.start_date_waffles, end=datetime.date.today(), freq="W-WED")
df_xaxis = pd.DataFrame(data={"dates" : date_range})

df_xaxis["week_nr"] = (
            df_xaxis['dates'].dt.isocalendar().year.astype(str) + '-' +
            df_xaxis['dates'].dt.isocalendar().week.astype(str).str.zfill(2))
df_xaxis["value"] = 0
df_xaxis = df_xaxis.drop(columns=["dates"])

# st.write(df_xaxis)

if chart_select == "Gemiste Waffles":
    data = df_events
    fig_ts = go.Figure()

    for name in st.session_state.persons.keys():
        df_person = data[data["person"] == name].drop(columns=["person"])
        df_person = df_person[df_person["day"] == "Wednesday"]
        df_person = df_person.drop_duplicates(subset=["week_nr"], keep="first")
        df_person = df_person.sort_values(by="week_nr").reset_index(drop=True)
        df_person["value"] = 1

        df_person_full = pd.merge(
            left=df_xaxis[["week_nr", "value"]],
            right=df_person[["week_nr", "value"]],
            on="week_nr",
            how="left"
        )

        df_person_full.fillna(0, inplace=True)
        df_person_full["value"] = df_person_full.value_x + df_person_full.value_y
        df_person_full.drop(columns=["value_x", "value_y"], inplace=True)
        df_person_full["cummulative"] = df_person_full.value.cumsum()
        
        df_person_full["week_date"] = pd.to_datetime(
            df_person_full["week_nr"] + "-1", 
            format="%G-%V-%u"
        )

        fig_ts.add_trace(
            go.Scatter(
                x=df_person_full["week_date"],
                y=df_person_full["cummulative"],
                mode="lines+markers",
                name=name
            )
        )

        fig_ts.update_layout(
        width=700,
        dragmode="pan",
        xaxis=dict(
            rangeslider=dict(visible=True)
        ),
        legend=dict(
            x=1,
            y=1,
            xanchor="left",
            yanchor="top"
        )
    )

    fig_ts.update_xaxes(tickformat="%Y-%V")
    fig_ts.update_yaxes(fixedrange=False)

    st.plotly_chart(fig_ts, use_container_width=True)
    
    
else:
    data = df_adjes
    data.drinks_done = abs(data.drinks_done)
    
    data = data.sort_values(["name", "datum"])
    data["cumulative"] = data.groupby("name")["drinks_done"].cumsum()
    
    fig_ts = go.Figure()
    
    for name, df_person in data.groupby("name"):
        fig_ts.add_trace(
            go.Scatter(
                x=df_person["datum"],
                y=df_person["cumulative"],
                mode="lines+markers",
                name=name,
                marker=dict(size=6)
            )
        )

    fig_ts.update_layout(
            width=700,
            dragmode="pan",
            xaxis=dict(
                rangeslider=dict(visible=True)
            ),
            legend=dict(
                x=1,
                y=1,
                xanchor="left",
                yanchor="top"
            )
        )

    fig_ts.update_yaxes(fixedrange=False)

    st.plotly_chart(fig_ts, use_contaiter_width=True)
    

    
    
    

