import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

API_URL = "http://localhost:5002"

def user_remotes_view():
    st.title("🎮 Twoje piloty")

    response = get_remotes(st.session_state.mode, st.session_state.username, st.session_state.token)

    if response.status_code == 200:
        for remote in response.json():
            with st.expander(f"Pilot: {remote['name']}"):
                st.markdown(f"**Właściciel:** {remote['user_id']}")
                st.markdown(f"**Brama:** {remote['barrier_id']}")
                st.markdown(f"**Utworzony dnia:** {remote['created_at']}")
    else:
        st.error("Błąd pobierania danych.")


def get_remotes(mode, username, token):
    headers = {}
    if mode == 'user':
        auth = HTTPBasicAuth(username, token)
        return requests.get(f"{API_URL}/api/my/remotes", auth=auth)
    elif mode == 'admin':
        headers["Authorization"] = f"Bearer {token}"
        return requests.get(f"{API_URL}/api/my/remotes", headers=headers)