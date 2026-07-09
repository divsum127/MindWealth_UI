"""Streamlit login gate via FastAPI auth API."""

from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE = os.getenv("MW_AUTH_API_BASE", "http://127.0.0.1:8506").rstrip("/")
API_KEY = os.getenv("API_KEY", "").strip()


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ensure_streamlit_login() -> bool:
    """Return True when user is authenticated; renders login form otherwise."""
    if st.session_state.get("mw_auth_token") and st.session_state.get("mw_auth_user"):
        return True

    st.title("MindWealth Sign in")
    st.caption("Invite-only. Set your password via the website invite link if this is your first time.")

    with st.form("streamlit_login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if not submitted:
        st.stop()

    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"email": email.strip(), "password": password},
            headers=_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach auth API: {exc}")
        st.stop()

    if resp.status_code != 200:
        st.error("Invalid email or password")
        st.stop()

    body = resp.json()
    token = body.get("access_token")
    if not token:
        st.error("Login failed")
        st.stop()

    me = requests.get(f"{API_BASE}/api/v1/auth/me", headers=_headers(token), timeout=30)
    if me.status_code != 200:
        st.error("Login failed")
        st.stop()

    st.session_state["mw_auth_token"] = token
    st.session_state["mw_auth_user"] = me.json()
    st.rerun()
    return False
