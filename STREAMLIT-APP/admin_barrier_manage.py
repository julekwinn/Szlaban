import streamlit as st
import requests

def add_barrier_view():
    st.title("➕ Dodaj nowy szlaban")

    barrier_id = st.text_input("ID szlabanu (unikalne)")
    controller_url = st.text_input("URL kontrolera", value="http://")

    if st.button("Dodaj szlaban"):
        if not barrier_id or not controller_url:
            st.error("Uzupełnij wszystkie pola.")
            return

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key,
            "Content-Type": "application/json"
        }

        data = {
            "barrier_id": barrier_id,
            "controller_url": controller_url
        }

        response = requests.post("http://localhost:5002/api/barriers", headers=headers, json=data)

        if response.status_code == 201:
            st.success(f"Szlaban `{barrier_id}` został dodany.")
        elif response.status_code == 422:
            st.error("Szlaban o takim ID już istnieje.")
        else:
            st.error(f"Błąd: {response.status_code} - {response.text}")