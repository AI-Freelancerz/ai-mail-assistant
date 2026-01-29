# streamlit_login.py
import streamlit as st
import time
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.exceptions import LoginError

def render_login_form():
    """
    Renders the login form and handles authentication.

    Returns:
        bool: True if the user is authenticated, False otherwise.
    """
    # 1. Load credentials and cookie config from secrets
    try:
        # Load and convert credentials to ensure they are mutable
        credentials = dict(st.secrets.get('credentials', {}))
        if 'usernames' in credentials:
            credentials['usernames'] = {
                username: dict(user_data)
                for username, user_data in credentials['usernames'].items()
            }
        
        # Ensure preauthorized list is included if present
        if 'preauthorized' in st.secrets.get('credentials', {}):
            credentials['preauthorized'] = list(st.secrets['credentials']['preauthorized'])
        
        cookie_config = st.secrets.get('cookie', {})
        
        # Validation
        if not credentials.get('usernames'):
            st.error("No users defined in secrets.toml")
            return False
            
    except Exception as e:
        st.error(f"Error loading configuration: {str(e)}")
        return False

    # 2. Instantiate the authenticator
    try:
        authenticator = stauth.Authenticate(
            credentials,
            cookie_config.get('name', 'some_cookie_name'),
            cookie_config.get('key', 'some_cookie_key'),
            cookie_config.get('expiry_days', 30)
        )
    except Exception as e:
        st.error(f"Error initializing authenticator: {str(e)}")
        return False

    # 3. Render the login widget
    try:
        authenticator.login()
    except LoginError:
        # If cookie authentication fails, we catch it and allow the code to proceed.
        # This prevents infinite loops if the error persists.
        pass
    except Exception as e:
        # Catch other errors during login rendering
        st.error(f"Login error: {str(e)}")
        return False

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
