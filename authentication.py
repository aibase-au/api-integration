#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path
import sys

# Get the directory where the script is located
def init_auth():
    """Initialize authentication by loading environment variables"""
    # Get the directory of the calling script
    caller_frame = sys._getframe(1)
    caller_file = caller_frame.f_code.co_filename
    script_dir = Path(caller_file).parent.absolute()
    env_path = script_dir / '.env'
    
    # Load environment variables from the .env file
    print(f"Loading .env file from: {env_path}")
    load_dotenv(env_path, override=True)
    
    # Debug print environment variables
    print("\nEnvironment variables loaded:")
    print(f"PROJECT_ID: {os.getenv('PROJECT_ID')}")
    print(f"PROSPECT_ID: {os.getenv('PROSPECT_ID')}")
    print(f"API_KEY: {os.getenv('API_KEY')}")
    print(f"USERNAME: {os.getenv('USERNAME')}")
    print(f"PASSWORD: {os.getenv('PASSWORD')}")
    print(f"API_ENDPOINT: {os.getenv('API_ENDPOINT')}")
    
    # Setup configuration from environment variables
    auth_config = {
        'projectId': int(os.getenv('PROJECT_ID', '0')),
        'prospectId': int(os.getenv('PROSPECT_ID', '0')),
        'workflow_id': int(os.getenv('WORKFLOW_ID', '0')) if os.getenv('WORKFLOW_ID') else None,
        'api_key': os.getenv('API_KEY'),
        'username': os.getenv('USERNAME'),
        'password': os.getenv('PASSWORD'),
        'api_endpoint': os.getenv('API_ENDPOINT', 'https://api-portal1.fastgeo.com.au/api')
    }
    
    # Check if we have valid authentication options
    auth_config['use_api_key'] = auth_config['api_key'] is not None and auth_config['api_key'].strip() != ""
    auth_config['use_credentials'] = (auth_config['username'] is not None and 
                                     auth_config['password'] is not None and 
                                     auth_config['username'].strip() != "" and 
                                     auth_config['password'].strip() != "")
    
    if not (auth_config['use_api_key'] or auth_config['use_credentials']):
        raise ValueError("Please set either API_KEY or both USERNAME and PASSWORD in .env file")
    
    return auth_config

def login(username, password, api_endpoint):
    """
    Authenticate with username and password to get an access token
    """
    url = f"{api_endpoint}/TokenAuth/Authenticate"

    payload = json.dumps({
        "userNameOrEmailAddress": username,
        "password": password
    })
    # Extract the base URL for Origin and Referer headers
    base_url = api_endpoint.replace('/api', '')
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Authorization': '',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': base_url,
        'Pragma': 'no-cache',
        'Referer': f"{base_url}/",
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response
    except requests.exceptions.RequestException as e:
        print(f"Login request failed: {str(e)}")
        if 'response' in locals():
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return None

def get_request_headers(api_key, use_api_key, api_endpoint, accessToken=None):
    """
    Create headers with either Bearer token or API key authentication
    """
    # Extract the base URL for Origin and Referer headers
    base_url = api_endpoint.replace('/api', '')
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': base_url,
        'Pragma': 'no-cache',
        'Referer': f"{base_url}/",
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    # Add authentication - either Bearer token or API key
    if use_api_key:
        headers['x-api-key'] = api_key
    elif accessToken:
        headers['Authorization'] = f'Bearer {accessToken}'
    
    return headers

def authenticate(auth_config):
    """
    Perform authentication based on configuration and return auth token
    """
    token = None
    
    # Only perform login if using username/password authentication
    if auth_config['use_credentials']:
        print("Authenticating with username and password...")
        login_response = login(auth_config['username'], auth_config['password'], auth_config['api_endpoint'])
        if login_response is None:
            print("Login failed. Please check your credentials and try again.")
            return None
    
        try:
            token = login_response.json()["result"]["accessToken"]
            print("Login successful!")
            return token
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Failed to parse login response: {str(e)}")
            print(f"Response content: {login_response.text}")
            return None
    else:
        print("Using API key authentication")
        return None  # No token needed for API key authentication