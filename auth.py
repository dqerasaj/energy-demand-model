"""Single shared username/password gate, checked against Streamlit secrets."""

import streamlit as st


def check_password() -> bool:
    if st.session_state.get("authenticated", False):
        return True

    st.title("LDV Sales Forecast - Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if (
            username == st.secrets["auth"]["username"]
            and password == st.secrets["auth"]["password"]
        ):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password")

    return False
