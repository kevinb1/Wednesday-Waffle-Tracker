import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml import SafeLoader
import copy
from streamlit_authenticator.utilities import (CredentialsError,
                                               ForgotError,
                                               Hasher,
                                               LoginError,
                                               RegisterError,
                                               ResetError,
                                               UpdateError)

# --- Streamlit page config ---
def main():
    st.set_page_config(page_title="Login Pagina",
                   layout="wide", page_icon=":waffle:")

    # --- Authentication ---
    authenticator = stauth.Authenticate(
        st.secrets['credentials'].to_dict(),
        st.secrets['cookie']['name'],
        st.secrets['cookie']['key'],
        st.secrets['cookie']['expiry_days'],
    )
    
    try:
        authenticator.login()
    except LoginError as e:
        st.error(e)

    if st.session_state["authentication_status"]:
        st.write('___')
        st.header(f'Fakka {st.session_state["name"]}')
        
        match st.session_state["name"]:
            case "Vina":
                st.subheader("Ga eens wat doen!")
                dev_acces = st.button("Development")
                if dev_acces:
                    st.switch_page("pages/editor.py")
            case "Paupau":
                st.subheader("Paula, je kan niet ALTIJD Jelle de schuld geven")
            case "Jelliebellie":
                st.subheader("Jelle, houdt je broek aan!")
                st.write("##")
                st.write("Viespeuk...")
            case "Khonnor":
                st.subheader("HEY! Tik tik, appeltje eitje")
            case "Titi":
                st.subheader("Laat ook ff aan Nienke zien")
            case "Nini":
                st.subheader("Waarschijnlijk lees je dit nooit, maar zo wel")
                st.subheader("Ben je op tijd?")
            case "Murt":
                st.subheader("Het spijt me dat je weer een facist bent")
            case "Ankie":
                st.subheader("Sorry, hier vind je geen jongens met een J")
            case _:
                st.subheader("Hoe kom jij hier?")
        
        col1, col2 =  st.columns(2)
        with col1:
            authenticator.logout()
        go_to_app = col2.button("Naar Site")
        st.write('___')
        if go_to_app:
            st.switch_page("pages/app.py")
        
    elif st.session_state["authentication_status"] is False:
        st.error('Onjuiste gebruikesrnaam/wachtwoord')
    elif st.session_state["authentication_status"] is None:
        st.warning('Vul een correcte gebruikersnaam/wachtwoord in')



if __name__ == "__main__":
    main()