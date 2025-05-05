import streamlit as st
import requests
from user_barriers import user_barriers_view
from user_barriers import get_barriers
from user_remotes import user_remotes_view
from user_events import user_history_view
from admin_events import admin_history_view
from admin_user_manage import manage_users
from admin_barrier_manage import add_barrier_view
from admin_remotes_manage import manage_remotes


def profile_view():
    st.title("Profil użytkownika")
    st.markdown(f"**Zalogowany jako:** `{st.session_state.username}`")
    st.markdown(f"**Tryb:** `{st.session_state.mode}`")

    api_token = st.text_input("Wprowadź swój token autoryzacyjny:", type="password")

    if api_token:

        headers = {
            "accept": "application/json",
            "X-Admin-API-Key": api_token
        }

        response = requests.get('http://localhost:5002/api/events?limit=50', headers=headers)

        if response.status_code == 200:
            st.session_state.auth_key = api_token
            st.write("Token autoryzacyjny poprawny.")
            st.rerun()
        else:
            st.error(f"Niepoprawny token")

    else:
        st.warning("Podaj token autoryzacyjny, aby uzyskać dostęp do dodatkowych funkcji.")


def logout_view():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.token = ""
    st.session_state.auth_token = ""
    st.session_state.auth_key = ""
    st.session_state.mode = ""
    st.success("Wylogowano pomyślnie.")
    st.stop()

# ===== Główna funkcja =====
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        st.sidebar.title("Nawigacja")

        if 'auth_key' not in st.session_state:
            page = st.sidebar.radio("Wybierz akcję", ["Historia zdarzeń", "Twoje szlabany", "Twoje piloty", "Profil", "Wyloguj"])

            if page == "Historia zdarzeń":
                user_history_view()
            elif page == "Twoje szlabany":
                user_barriers_view()
            elif page == "Twoje piloty":
                user_remotes_view()
            elif page == "Profil":
                profile_view()
            elif page == "Wyloguj":
                logout_view()
        else:
            page = st.sidebar.radio("Wybierz akcję", ["Historia zdarzeń", "Szlabany", "Piloty", "Użytkownicy", "Profil", "Wyloguj"])

            if page == "Historia zdarzeń":
                admin_history_view()
            elif page == "Szlabany":
                add_barrier_view()
            elif page == "Piloty":
                manage_remotes()
            elif page == "Użytkownicy":
                manage_users()
            elif page == "Profil":
                profile_view()
            elif page == "Wyloguj":
                logout_view()


    else:
        # Logowanie
        st.title("Logowanie do systemu")
        username = st.text_input("Login")
        password = st.text_input("Hasło", type="password")
        mode = st.selectbox("Rodzaj dostępu", ["Użytkownik", "Administrator"])

        mode_map = {
            "Użytkownik": "user",
            "Administrator": "admin"
        }

        if st.button("Zaloguj się"):
            if mode_map[mode] == "user":
                response = get_barriers("user", username, password)
                if response.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.token = password
                    st.session_state.auth_token = f"{username}:{password}"
                    st.session_state.mode = "user"
                    st.rerun()
                else:
                    st.error("Nieprawidłowe dane logowania.")
            else:
                response = get_barriers("admin", "", password)
                if response.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.username = "admin"
                    st.session_state.token = password
                    st.session_state.auth_token = password
                    st.session_state.mode = "admin"
                    st.rerun()
                else:
                    st.error("Nieprawidłowy token administratora.")

if __name__ == "__main__":
    main()
