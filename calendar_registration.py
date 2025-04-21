#!/usr/bin/env python3
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
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

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the query parameters
        query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        
        if 'code' in query_components:
            # Store the authorization code
            self.server.auth_code = query_components['code'][0]
            
            # Send success response to browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            # Send error response
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization failed! Please try again.")

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

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

    # Get a free port for the local server
    port = get_free_port()
    redirect_uri = f'http://localhost:{port}'

    # Create the flow using the client secrets file from the Google API Console
    flow = InstalledAppFlow.from_client_secrets_file(
        creds_file, SCOPES,
        redirect_uri=redirect_uri
    )

    # Start local server to receive the OAuth callback
    server = HTTPServer(('localhost', port), OAuthHandler)
    server.auth_code = None
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Generate URL for authorization
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print("\nOpening your browser to authorize this application...")
    webbrowser.open(auth_url)
    
    print("\nWaiting for authorization...")
    while server.auth_code is None:
        pass
    
    # Stop the server
    server.shutdown()
    server.server_close()
    
    # Exchange the authorization code for credentials
    flow.fetch_token(code=server.auth_code)
    creds = flow.credentials

    # Save the credentials
    save_credentials(creds, token_file)
    print(f"\nCredentials saved successfully to {token_file}")
    print("You can now run the LED Matrix display with calendar integration!")

if __name__ == '__main__':
    main() 