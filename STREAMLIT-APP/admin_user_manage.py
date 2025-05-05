import streamlit as st
import requests

API_BASE_URL = "http://localhost:5002/api"

def manage_users():
    st.title("Zarządzanie użytkownikami i uprawnieniami")

    with st.expander("➕ Dodaj nowego użytkownika", expanded=True):
        add_user_view()

    with st.expander("🔑 Przypisz uprawnienia do szlabanu", expanded=True):
        assign_permission_view()


def add_user_view():
    st.subheader("➕ Dodaj użytkownika")

    username = st.text_input("Nazwa użytkownika", key="add_user_username")
    password = st.text_input("Hasło", type="password", key="add_user_password")

    if st.button("Dodaj użytkownika", key="add_user_btn"):
        if not username or not password:
            st.error("Uzupełnij wszystkie pola.")
            return

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key,
            "Content-Type": "application/json"
        }

        data = {
            "username": username,
            "password": password
        }

        response = requests.post(f"{API_BASE_URL}/users", headers=headers, json=data)

        if response.status_code == 201:
            st.success(f"Użytkownik `{username}` został dodany.")
        elif response.status_code == 422:
            st.error("Użytkownik o takiej nazwie już istnieje.")
        else:
            st.error(f"Błąd: {response.status_code} - {response.text}")


def assign_permission_view():
    st.subheader("🔑 Przypisz uprawnienia użytkownikowi")

    username = st.text_input("Nazwa użytkownika", key="perm_username")
    barrier_id = st.text_input("ID szlabanu", key="perm_barrier_id")
    permission_level = st.selectbox("Poziom uprawnień", ["operator", "technician"], key="perm_level")

    if st.button("Przypisz uprawnienie", key="assign_permission_btn"):
        if not username or not barrier_id:
            st.error("Wszystkie pola są wymagane.")
            return

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": st.session_state.auth_key,
            "Content-Type": "application/json"
        }

        data = {
            "username": username,
            "barrier_id": barrier_id,
            "permission_level": permission_level
        }

        response = requests.post(f"{API_BASE_URL}/permissions", headers=headers, json=data)

        if response.status_code == 201:
            st.success(f"Użytkownik `{username}` otrzymał uprawnienie `{permission_level}` do szlabanu `{barrier_id}`.")
        elif response.status_code == 404:
            st.error("Nie znaleziono użytkownika lub szlabanu.")
        elif response.status_code == 409:
            st.error("Takie uprawnienie już istnieje.")
        else:
            st.error(f"Błąd: {response.status_code} - {response.text}")



