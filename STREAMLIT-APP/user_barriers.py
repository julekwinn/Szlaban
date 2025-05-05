import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

API_URL = "http://localhost:5002"

def user_barriers_view():
    st.title("🚧 Twoje szlabany")

    response = get_barriers(st.session_state.mode, st.session_state.username, st.session_state.token)

    if response.status_code == 200:
        for barrier in response.json():
            with st.expander(f"Szlaban: {barrier['barrier_id']} ({barrier['permission_level']})"):
                st.markdown(f"**URL kontrolera:** {barrier['controller_url']}")
                if st.button(f"Otwórz szlaban {barrier['barrier_id']}", key=f"open_{barrier['barrier_id']}"):
                    open_response = open_barrier(barrier['barrier_id'], st.session_state.username, st.session_state.token)
                    if open_response.status_code == 200:
                        st.success("Szlaban został otwarty.")
                    else:
                        st.error("Nie udało się otworzyć szlabanu.")
                if st.button(f"Zamknij szlaban {barrier['barrier_id']}", key=f"close_{barrier['barrier_id']}"):
                    close_response = close_barrier(barrier['barrier_id'], st.session_state.username, st.session_state.token)
                    if close_response.status_code == 200:
                        st.success("Szlaban został zamknięty.")
                    else:
                        st.error("Nie udało się zamknąć szlabanu.")
                st.markdown("Tryb serwisowy")
                if st.button("Włącz"):
                    start_response = service_start(barrier['barrier_id'], st.session_state.username, st.session_state.token)
                    if start_response.status_code == 200:
                        st.success("Szlaban został otwarty.")
                    elif start_response.status_code == 403:
                        st.info("Brak uprawnień. Akcja dostępna dla użytkownika z rangą: obsługa techniczna")
                    else:
                        st.error("Nie udało się otworzyć szlabanu.")
                if st.button("Wyłącz"):
                    stop_response = service_stop(barrier['barrier_id'], st.session_state.username, st.session_state.token)
                    if stop_response.status_code == 200:
                        st.success("Szlaban został zamknięty.")
                    elif stop_response.status_code == 403:
                        st.info("Brak uprawnień. Akcja dostępna dla użytkownika z rangą: obsługa techniczna")
                    else:
                        st.error("Nie udało się zamknąć szlabanu.")
    else:
        st.error("Błąd pobierania danych.")

def get_barriers(mode, username, token):
    headers = {}
    if mode == 'user':
        auth = HTTPBasicAuth(username, token)
        return requests.get(f"{API_URL}/api/my/barriers", auth=auth)
    elif mode == 'admin':
        headers["Authorization"] = f"Bearer {token}"
        return requests.get(f"{API_URL}/api/my/remotes", headers=headers)

def open_barrier(barrier_id, username, token):
    from base64 import b64encode

    # Przygotuj nagłówek Basic Auth
    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/barriers/{barrier_id}/open"
    return requests.post(url, headers=headers, data="")

def close_barrier(barrier_id, username, token):
    from base64 import b64encode

    # Przygotuj nagłówek Basic Auth
    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/barriers/{barrier_id}/close"
    return requests.post(url, headers=headers, data="")

def service_start(barrier_id, username, token):
    from base64 import b64encode

    # Przygotuj nagłówek Basic Auth
    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/barriers/{barrier_id}/service/start"
    return requests.post(url, headers=headers, data="")

def service_stop(barrier_id, username, token):
    from base64 import b64encode

    # Przygotuj nagłówek Basic Auth
    credentials = f"{username}:{token}"
    encoded = b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "accept": "application/json"
    }

    url = f"{API_URL}/api/barriers/{barrier_id}/service/end"
    return requests.post(url, headers=headers, data="")
