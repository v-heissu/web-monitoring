"""
Simple authentication for Streamlit
Pro Web Consulting Branding
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
    Shows styled login page if not authenticated
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

    # Custom CSS for login page
    st.markdown("""
    <style>
        /* Hide Streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none;}
        div[data-testid="stToolbar"] {display: none;}
        div[data-testid="stDecoration"] {display: none;}
        div[data-testid="stStatusWidget"] {display: none;}
        .viewerBadge_container__r5tak {display: none;}
        .styles_viewerBadge__CvC9N {display: none;}

        /* Background */
        .stApp {
            background: linear-gradient(135deg, #0a1628 0%, #1a1a3e 50%, #0f2744 100%);
        }

        /* Login container */
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            margin-top: 10vh;
        }

        .login-logo {
            text-align: center;
            margin-bottom: 2rem;
        }

        .login-logo img {
            max-width: 200px;
        }

        .login-title {
            color: white;
            text-align: center;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .login-subtitle {
            color: rgba(255,255,255,0.6);
            text-align: center;
            font-size: 0.875rem;
            margin-bottom: 2rem;
        }

        /* Input styling */
        .stTextInput > div > div > input {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 8px !important;
            color: white !important;
            padding: 0.75rem 1rem !important;
        }

        .stTextInput > div > div > input:focus {
            border-color: #6B1AC7 !important;
            box-shadow: 0 0 0 2px rgba(107, 26, 199, 0.2) !important;
        }

        .stTextInput > label {
            color: rgba(255,255,255,0.7) !important;
        }

        /* Button */
        .stButton > button {
            width: 100%;
            background: linear-gradient(135deg, #6B1AC7 0%, #5a15a8 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
            margin-top: 1rem !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(107, 26, 199, 0.4);
        }

        /* Error message */
        .stAlert {
            background: rgba(231, 76, 60, 0.1) !important;
            border: 1px solid #E74C3C !important;
            border-radius: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Centered login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        <div class="login-logo">
            <img src="https://ai-landscape.prowebconsulting.net/assets/pwc-logo.svg" alt="Pro Web Consulting">
        </div>
        <h2 class="login-title">Web Monitor</h2>
        <p class="login-subtitle">Accedi per gestire i tuoi progetti di monitoraggio</p>
        """, unsafe_allow_html=True)

        st.text_input("Username", key="username", placeholder="Inserisci username")
        st.text_input("Password", type="password", key="password", placeholder="Inserisci password")
        st.button("Accedi", on_click=password_entered, use_container_width=True)

        if "authenticated" in st.session_state and not st.session_state["authenticated"]:
            st.error("Username o password non validi")

        st.markdown("""
        <p style="text-align: center; color: rgba(255,255,255,0.4); font-size: 0.75rem; margin-top: 2rem;">
            Pro Web Consulting - Web Monitor v2.0
        </p>
        """, unsafe_allow_html=True)

    return False
