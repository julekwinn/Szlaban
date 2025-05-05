import streamlit as st
import requests
import json

def manage_remotes():
    st.title("Zarządzanie pilotami i konfiguracją")

    with st.expander("➕ Dodaj nowy pilot", expanded=True):
        create_remote_view()

    with st.expander("📥 Wygeneruj plik konfiguracyjny config.c", expanded=True):
        download_remote_config_view()
    
    with st.expander("📥 Wygeneruj plik konfiguracyjny config.h", expanded=True):
        download_config_h_view()

    with st.expander("🗑️ Usuń pilota"):
        delete_remote_view()


def create_remote_view():
    st.subheader("➕ Dodaj nowy pilot")
    name = st.text_input("Nazwa pilota")
    user_id = st.number_input("ID użytkownika", min_value=1, step=1)
    barrier_id = st.text_input("ID szlabanu")

    if st.button("Utwórz pilota"):
        if not name or not user_id or not barrier_id:
            st.error("Wszystkie pola są wymagane.")
            return

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key,
            "Content-Type": "application/json"
        }

        data = {
            "name": name,
            "user_id": user_id,
            "barrier_id": barrier_id
        }

        response = requests.post("http://localhost:5002/api/remotes", headers=headers, json=data)

        if response.status_code == 201:
            st.success("Pilot został utworzony.")
            remote_data = response.json()

            st.subheader("Dane konfiguracyjne pilota:")

            st.write(f"**ID pilota:** {remote_data['remote_id']}")
            st.write(f"**Nazwa:** {remote_data['name']}")
            st.write(f"**ID użytkownika:** {remote_data['user_id']}")
            st.write(f"**ID szlabanu:** {remote_data['barrier_id']}")
            st.write(f"**Data utworzenia:** {remote_data['created_at']}")

        elif response.status_code == 404:
            st.error("Nie znaleziono użytkownika lub szlabanu.")
        else:
            st.error(f"Błąd: {response.status_code} - {response.text}")

def download_remote_config_view():
    st.subheader("📥 Wygeneruj plik konfiguracyjny config.c")

    remote_id = st.text_input("Wprowadź identyfikator pilota")

    if st.button("Utwórz config.c"):
        if not remote_id:
            st.error("Podaj identyfikator pilota.")
            return

        url = f"http://localhost:5002/api/remotes/{remote_id}/config.c"
        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            config_content = response.text
            st.success("Plik został utworzony.")

            # Pobieranie jako plik
            st.download_button(
                label="📄 Pobierz config.c",
                data=config_content,
                file_name="config.c",
                mime="text/plain"
            )
        elif response.status_code == 404:
            st.error("Nie znaleziono pilota o podanym identyfikatorze.")
        else:
            st.error(f"Błąd: {response.status_code} - {response.text}")

def download_config_h_view():
    st.subheader("📥 Wygeneruj plik konfiguracyjny config.h")

    remote_id = st.text_input("Wprowadź identyfikator pilota")

    if st.button("Utwórz config.h"):
        if not remote_id:
            st.warning("Podaj identyfikator pilota.")
            return

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key
        }

        url = f"http://localhost:5002/api/remotes/{remote_id}/config.h"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            st.success("Plik config.h został utworzony.")
            st.download_button(
                label="📄 Pobierz config.h",
                data=response.content,
                file_name="config.h",
                mime="text/x-c"
            )
        elif response.status_code == 404:
            st.error("Nie znaleziono pilota o podanym identyfikatorze.")
        else:
            st.error(f"Błąd podczas pobierania pliku: {response.status_code} - {response.text}")


def delete_remote_view():
    st.header("🗑️ Usuń pilota")

    remote_id = st.text_input("Wprowadź identyfikator pilota")

    if st.button("Usuń pilota"):
        if not remote_id:
            st.warning("Podaj identyfikator pilota.")
            return

        headers = {
            "accept": "*/*",
            "X-Admin-API-Key": st.session_state.auth_key
        }

        url = f"http://localhost:5002/api/remotes/{remote_id}"
        response = requests.delete(url, headers=headers)

        if response.status_code == 204:
            st.success(f"Pilot o identyfikatorze `{remote_id}` został usunięty.")
        elif response.status_code == 404:
            st.error("Nie znaleziono pilota o podanym identyfikatorze.")
        else:
            st.error(f"Błąd {response.status_code}: {response.text}")


