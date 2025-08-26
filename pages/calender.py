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

# --- Streamlit page config ---
st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")
st.title("Wednesday Waffle Tracker")

# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Opties en Navigatie")        
    dev_acces = st.button("Terug naar app")
    if dev_acces:
        st.switch_page("pages/app.py")

# --- Load calendar options and CSS ---
with open("calendar_options.json") as f:
    calendar_options = json.load(f)

with open("custom.css") as f:
    custom_css = f.read()
    
# --- Display calendar ---
st.header("Calender")
if st.session_state.events:
    calendar(events=st.session_state.events,
             options=calendar_options,
             custom_css=custom_css,
             key='calendar')
else:
    st.info("No events found. Please upload and process a chat export.")