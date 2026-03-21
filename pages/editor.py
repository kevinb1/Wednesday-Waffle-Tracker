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
import datetime

st.set_page_config(page_title="Wednesday Waffle Tracker",
                   layout="wide", page_icon=":waffle:")

st.title("Voortgang bijwerken")
# --- Sidebar for navigation ---
with st.sidebar:
    st.header("Opties en Navigatie")        
    dev_acces = st.button("Terug naar app")
    if dev_acces:
        st.switch_page("pages/app.py")

cols = st.columns(2, width="stretch")
cols[1].link_button("Ga naar Google Sheets","https://docs.google.com/spreadsheets/d/1sGugpoTuMUUzrRqjs2R-K-Av695rqk4VXY3gPLmUN6A/edit?gid=0#gid=0")

refresh = cols[0].button("Refresh", type="primary")
if refresh:
    st.cache_data.clear()
    st.rerun()  

conn = st.connection("gsheets", type=GSheetsConnection)
df_adjes = conn.read(worksheet="adjes_gedaan")
df_score = conn.read(worksheet="score")

col1, col2, col3 = st.columns(3)
name = col1.selectbox(label="Selecteer persoon", options=df_adjes.name.unique())
drinks_added = -col2.number_input(label="Vul uitgevoerde (+) if straf (-) adjes in", step=1)
datum_done = col3.date_input(label="Datum atjes gedaan", value=datetime.date.today()).strftime("%d-%m-%Y")


apply_changes = st.button("Toepassen")

if apply_changes:
    new_row = {"name": name, "drinks_subtracted": drinks_added, "datum": datum_done}
    df_adjes = pd.concat([df_adjes, pd.DataFrame([new_row])], ignore_index=True)
    
    conn.update(data=df_adjes)
    st.success("Atjes toegevoegd")
    time.sleep(3)
    df_adjes = conn.read()
    if "drinks_subtracted"  in st.session_state:        
        st.session_state.drinks_subtracted = df_adjes
    st.cache_data.clear()
    st.rerun()

    
st.data_editor(df_adjes)
st.markdown("----")
st.title("Atjes Database")
st.data_editor(df_score)