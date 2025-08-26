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

st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")

st.title("Read Google Sheet as DataFrame")
# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Opties en Navigatie")        
    dev_acces = st.button("Terug naar app")
    if dev_acces:
        st.switch_page("pages/app.py")

conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()

col1, col2 = st.columns(2)
name = col1.selectbox(label="Selecteer persoon", options=df.name.unique())
drinks_added = col2.number_input(label="Vul aantal atjes in", step=1)
df.loc[df["name"] == name, "drinks_done"] += drinks_added

apply_changes = st.button("Toepassen")

if apply_changes:
    conn.update(data=df)
    st.success("Atjes toegevoegd")
    time.sleep(3)
    df = conn.read()
    if "drinks_done"  in st.session_state:        
        st.session_state.drinks_done = dict(zip(df['name'], df['drinks_done']))

    
st.data_editor(df)