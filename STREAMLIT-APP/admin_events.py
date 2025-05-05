import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from user_barriers import get_barriers

API_URL = "http://localhost:5002"

def admin_history_view():
    st.title("📜 Historia zdarzeń")

    if 'event_limit' not in st.session_state:
        st.session_state.event_limit = 50

    limit = st.number_input("Liczba zdarzeń do pobrania:", min_value=1, max_value=1000, value=st.session_state.event_limit, step=10)

    if st.button("Pobierz zdarzenia"):
        st.session_state.event_limit = limit

        response = get_admin_events(limit)
        
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

def get_admin_events(limit=50):

    headers = {
        "accept": "application/json",
        "X-Admin-API-Key": st.session_state.auth_key
    }

    url = f"{API_URL}/api/events?limit={limit}"
    return requests.get(url, headers=headers)