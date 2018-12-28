from app_properties import emotiv_endpoint, username, password, client_id, client_secret, rover_endpoint
from websocket import create_connection
import json
import ssl
import time
import requests

conn = create_connection(emotiv_endpoint, sslopt={'cert_reqs': ssl.CERT_NONE})


def authenticate():
    response = get_login()
    if len(response['result']) == 0:
        login()
    return authorize()


def get_login():
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'getUserLogin',
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response


def login():
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'login',
        'params': {
            'username': username,
            'password': password,
            'client_id': client_id,
            'client_secret': client_secret
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response


def authorize():
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'authorize',
        'params': {
            'client_id': client_id,
            'client_secret': client_secret
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response['result']['_auth']


def get_headset():
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'queryHeadsets',
        'params': {
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])
    elif len(response['result']) == 0:
        raise ConnectionError('No devices found. Please connect your eeg device before continuing.')

    device_list = response['result']

    # I only have 1 device, thus we only get the data for that one device.
    return device_list[0]['id']


def create_session(auth_token):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'createSession',
        'params': {
            '_auth': auth_token,
            'status': 'open'
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response['result']['id']


def update_session(auth_token, session_id, status):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'updateSession',
        'params': {
            '_auth': auth_token,
            'session': session_id,
            'status': status
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    print('Session successfully closed.')


def subscribe(auth_token, sub_type):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'subscribe',
        'params': {
            '_auth': auth_token,
            'streams': [
                sub_type
            ]
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response


def unsubscribe(auth_token, sub_type):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'unsubscribe',
        'params': {
            '_auth': auth_token,
            'streams': [
                sub_type
            ]
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response


def mental_command_detection_info():
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'getDetectionInfo',
        'params': {
            'detection': 'mentalCommand',
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    actions = response['result']['actions']
    controls = response['result']['controls']
    events = response['result']['events']

    return actions, controls, events


def start_training(auth_token, detection_type, session_id):
    print('\nStarting training procedure, please make sure you are in a quiet environment.\n')

    # actions = ['neutral', 'push', 'left', 'right']
    actions = ['neutral', 'push']
    total = 3

    for action in actions:
        print('{}: training command, think of a mental picture that will invoke this action'.format(action))

        for x in range(total):
            # Pause to give user time to think of mental picture that will be used for training.
            time.sleep(3)

            train(auth_token, detection_type, session_id, action, 'start')

            response = json.loads(conn.recv())

            if 'error' in response:
                raise ConnectionError(response['error']['message'])

            while 'result' in response:
                print('[{}/{}] {}: preparing to start training '.format(str(x), str(total), action))
                time.sleep(1)
                response = json.loads(conn.recv())

            if 'sys' in response:
                current_event = response['sys'][1]
                while current_event == 'MC_Started':
                    print('[{}/{}] {}: training IN-PROGRESS'.format(str(x), str(total), action))
                    response = json.loads(conn.recv())
                    current_event = response['sys'][1]

                if current_event == 'MC_Succeeded':
                    print('[{}/{}] {}: training SUCCEEDED, saving training data to profile'.format(str(x), str(total), action))
                    train(auth_token, detection_type, session_id, action, 'accept')
                    response = json.loads(conn.recv())
                elif current_event == 'MC_Failed':
                    print('[{}/{}] {}: training FAILED, discarding training data'.format(str(x), str(total), action))
                    train(auth_token, detection_type, session_id, action, 'reject')
                    response = json.loads(conn.recv())

                while 'result' in response:
                    time.sleep(1)
                    response = json.loads(conn.recv())

                current_event = response['sys'][1]
                while current_event != 'MC_Completed':
                    response = json.loads(conn.recv())
                    current_event = response['sys'][1]
                    print(current_event)

                print('{}: training for action COMPLETED.\n'.format(action))

        # Validate training results
        stream_type = 'com'
        if action != 'neutral':
            subscribe(auth_token, stream_type)
            connect_to_vehicle()
            unsubscribe(auth_token, stream_type)


def train(auth_token, detection_type, session_id, action, status):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'training',
        'params': {
            '_auth': auth_token,
            'detection': detection_type,
            'session': session_id,
            'action': action,
            'status': status
        },
        'id': 1
    }))


def setup_profile(auth_token, headset_id, profile_name, status):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'setupProfile',
        'params': {
            '_auth': auth_token,
            'headset': headset_id,
            'profile': profile_name,
            'status': status
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])

    return response


def get_profile(auth_token, headset_id):
    conn.send(json.dumps({
        'jsonrpc': '2.0',
        'method': 'getCurrentProfile',
        'params': {
            '_auth': auth_token,
            'headset': headset_id
        },
        'id': 1
    }))

    response = json.loads(conn.recv())
    if 'error' in response:
        raise ConnectionError(response['error']['message'])
    elif len(response['result']) == 0:
        raise ValueError('No profile has been created.')
    else:
        profile_name = response['result']

    return profile_name


def connect_to_vehicle():
    print('Establishing connection to vehicle...')
    total = 50
    for i in range(1, total):
        thought = json.loads(conn.recv())['com'][0]
        print('[{}/{}] {}'.format(str(i), str(total), thought))

        if thought == 'push':
            requests.get(rover_endpoint.format('forward'))
        time.sleep(1)
