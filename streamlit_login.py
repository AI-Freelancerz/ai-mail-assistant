# streamlit_login.py
import streamlit as st
import streamlit_authenticator as stauth

def render_login_form():
    """
    Renders the login form and handles authentication.

    Returns:
        bool: True if the user is authenticated, False otherwise.
    """
    # 1. Load credentials and cookie config from secrets
    #    THE FIX IS HERE: Convert the secrets object to a mutable dict.
    credentials = dict(st.secrets.get('credentials', {}))
    if 'usernames' in credentials:
        credentials['usernames'] = {
            username: dict(user_data)
            for username, user_data in credentials['usernames'].items()
        }
    cookie_config = st.secrets.get('cookie', {})

    # 2. Instantiate the authenticator
    authenticator = stauth.Authenticate(
        credentials,
        cookie_config.get('name', 'some_cookie_name'),
        cookie_config.get('key', 'some_cookie_key'),
        cookie_config.get('expiry_days', 30)
    )

    # 3. Render the login widget
    authenticator.login()

    # 4. Check authentication status
    if st.session_state.get("authentication_status"):
        # If authenticated, show a logout button in the sidebar
        with st.sidebar:
            st.write(f'Welcome *{st.session_state["name"]}*')
            authenticator.logout('Logout', 'main')
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error('Username/password is incorrect')
        return False
    elif st.session_state.get("authentication_status") is None:
        st.info('Please enter your username and password to continue.')
        return False
    
    return False
