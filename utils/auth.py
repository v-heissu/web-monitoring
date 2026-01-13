"""
Simple authentication for Streamlit
"""

import streamlit as st
import hashlib
import os


def hash_password(password: str) -> str:
    """Hash password with SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password():
    """
    Returns True if user has correct password
    """

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        username = st.session_state["username"]
        password = st.session_state["password"]

        # Get from env
        admin_user = os.getenv("ADMIN_USER", "admin")
        admin_pass = os.getenv("ADMIN_PASS", "changeme")

        if username == admin_user and password == admin_pass:
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["authenticated"] = False

    # Check if already authenticated
    if st.session_state.get("authenticated", False):
        return True

    # Show login form
    st.markdown("## Login")
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.button("Login", on_click=password_entered)

    if "authenticated" in st.session_state and not st.session_state["authenticated"]:
        st.error("Username o password errati")

    return False
