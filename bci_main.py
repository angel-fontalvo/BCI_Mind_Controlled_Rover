from bci_controls import authenticate, get_headset, create_session, subscribe, start_training, update_session


def main():
    # Authenticate user
    auth_token = authenticate()

    # Validate a headset is connected
    get_headset()

    # Open an active session with Emotiv
    session_id = create_session(auth_token)

    try:
        # Subscribe to the system stream
        subscribe(auth_token, 'sys')
        start_training(auth_token, 'mentalCommand', session_id)

    finally:
        update_session(auth_token, session_id, 'close')


main()
