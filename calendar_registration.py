#!/usr/bin/env python3
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import requests

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def load_config():
    with open('config/config.json', 'r') as f:
        return json.load(f)

def save_credentials(creds, token_path):
    # Save the credentials for the next run
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)

def get_device_code(client_id, client_secret):
    """Get device code for TV and Limited Input Device flow."""
    url = 'https://oauth2.googleapis.com/device/code'
    data = {
        'client_id': client_id,
        'scope': ' '.join(SCOPES)
    }
    response = requests.post(url, data=data)
    return response.json()

def poll_for_token(client_id, client_secret, device_code):
    """Poll for token using device code."""
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
    }
    response = requests.post(url, data=data)
    return response.json()

def main():
    config = load_config()
    calendar_config = config.get('calendar', {})
    
    creds_file = calendar_config.get('credentials_file', 'credentials.json')
    token_file = calendar_config.get('token_file', 'token.pickle')
    
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists(token_file):
        print("Existing token found, but you may continue to generate a new one.")
        choice = input("Generate new token? (y/n): ")
        if choice.lower() != 'y':
            print("Keeping existing token. Exiting...")
            return

    # If there are no (valid) credentials available, let the user log in.
    if not os.path.exists(creds_file):
        print(f"Error: No credentials file found at {creds_file}")
        print("Please download the credentials file from Google Cloud Console")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create a project or select existing project")
        print("3. Enable the Google Calendar API")
        print("4. Configure the OAuth consent screen (select TV and Limited Input Device)")
        print("5. Create OAuth 2.0 credentials (TV and Limited Input Device)")
        print("6. Download the credentials and save as credentials.json")
        return

    # Load client credentials
    with open(creds_file, 'r') as f:
        client_config = json.load(f)
    
    client_id = client_config['installed']['client_id']
    client_secret = client_config['installed']['client_secret']

    # Get device code
    device_info = get_device_code(client_id, client_secret)
    
    print("\nTo authorize this application, visit:")
    print(device_info['verification_url'])
    print("\nAnd enter the code:")
    print(device_info['user_code'])
    print("\nWaiting for authorization...")

    # Poll for token
    while True:
        token_info = poll_for_token(client_id, client_secret, device_info['device_code'])
        
        if 'access_token' in token_info:
            # Create credentials object
            creds = Credentials(
                token=token_info['access_token'],
                refresh_token=token_info.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            # Save the credentials
            save_credentials(creds, token_file)
            print(f"\nCredentials saved successfully to {token_file}")
            print("You can now run the LED Matrix display with calendar integration!")
            break
        elif token_info.get('error') == 'authorization_pending':
            import time
            time.sleep(device_info['interval'])
        else:
            print(f"\nError during authorization: {token_info.get('error')}")
            print("Please try again.")
            return

if __name__ == '__main__':
    main() 