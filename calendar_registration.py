#!/usr/bin/env python3
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import urllib.parse
import socket

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def load_config():
    with open('config/config.json', 'r') as f:
        return json.load(f)

def save_credentials(creds, token_path):
    # Save the credentials for the next run
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)

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
        print("4. Configure the OAuth consent screen")
        print("5. Create OAuth 2.0 credentials (Desktop application)")
        print("6. Download the credentials and save as credentials.json")
        return

    # Create the flow using the client secrets file from the Google API Console
    flow = InstalledAppFlow.from_client_secrets_file(
        creds_file, SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Use out-of-band flow for headless environment
    )

    # Generate URL for authorization
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print("\nPlease visit this URL to authorize this application:")
    print(auth_url)
    print("\nAfter authorizing, you will receive a code. Enter that code below:")
    
    code = input("Enter the authorization code: ")
    
    # Exchange the authorization code for credentials
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Save the credentials
    save_credentials(creds, token_file)
    print(f"\nCredentials saved successfully to {token_file}")
    print("You can now run the LED Matrix display with calendar integration!")

if __name__ == '__main__':
    main() 