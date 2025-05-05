import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from user_barriers import get_barriers

API_URL = "http://localhost:5002"

def user_history_view():
    st.title("📜 Historia zdarzeń")

    if 'event_limit' not in st.session_state:
        st.session_state.event_limit = 50

    limit = st.number_input("Liczba zdarzeń do pobrania:", min_value=1, max_value=1000, value=st.session_state.event_limit, step=10)

    # Pobierz listę szlabanów dla rozwijanej listy
    barrier_response = get_barriers(st.session_state.mode, st.session_state.username, st.session_state.token)
    barrier_options = []
    if barrier_response.status_code == 200:
        barrier_data = barrier_response.json()
        barrier_options = ["Wszystkie"] + [b["barrier_id"] for b in barrier_data]

    selected_barrier = st.selectbox("Wybierz szlaban:", barrier_options)

    if st.button("Pobierz zdarzenia"):
        st.session_state.event_limit = limit

        if selected_barrier == "Wszystkie":
            response = get_user_events(st.session_state.username, st.session_state.token, limit)
        else:
            response = get_barrier_events(selected_barrier, st.session_state.username, st.session_state.token, limit)

        if response.status_code == 200:
            events = response.json()
            if events:
                df = pd.DataFrame(events)
                df = df.drop(columns=["details", "failed_action", "id", "received_at"], errors="ignore")

                column_translation = {
                    "barrier_id": "Szlaban",
                    "event_type": "Typ zdarzenia",
                    "trigger_method": "Sposób wywołania",
                    "timestamp": "Czas zdarzenia",
                    "user_id": "ID użytkownika",
                    "success": "Sukces"
                }

                df = df.rename(columns=column_translation)
                st.dataframe(df)
            else:
                st.info("Brak zdarzeń do wyświetlenia.")
        else:
            st.error(f"Błąd podczas pobierania zdarzeń: {response.status_code}")

def get_user_events(username, token, limit=50):
    from base64 import b64encode

    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/my/events?limit={limit}"
    return requests.get(url, headers=headers)

def get_barrier_events(barrier_id, username, token, limit=50):
    from base64 import b64encode

    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/barriers/{barrier_id}/events?limit={limit}"
    return requests.get(url, headers=headers)