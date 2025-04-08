# %%
import pandas as pd
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
debug = True

# Get the directory where the script is located
script_dir = Path(__file__).parent.absolute()
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

# %%
projectId = int(os.getenv('PROJECT_ID', '12'))
prospectId = int(os.getenv('PROSPECT_ID', '12'))
num_errors = 1
api_key = os.getenv('API_KEY')
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')
# Default API endpoint if not specified in .env
api_endpoint = os.getenv('API_ENDPOINT', 'https://api-portal1.fastgeo.com.au/api')

# Check if we have valid authentication options
use_api_key = api_key is not None and api_key.strip() != ""
use_credentials = username is not None and password is not None and username.strip() != "" and password.strip() != ""

if not (use_api_key or use_credentials):
    raise ValueError("Please set either API_KEY or both USERNAME and PASSWORD in .env file")

# %%

# Create log file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# %%
def login(username, password):
    url = f"{api_endpoint}/TokenAuth/Authenticate"

    payload = json.dumps({
        "userNameOrEmailAddress": username,
        "password": password
    })
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Authorization': '',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://portal1.fastgeo.com.au',
        'Pragma': 'no-cache',
        'Referer': 'https://portal1.fastgeo.com.au/',
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

# %%
# Set token to None initially
token = None

# Only perform login if using username/password authentication
if use_credentials:
    login_response = login(username, password)
    if login_response is None:
        print("Login failed. Please check your credentials and try again.")
        exit(1)

    try:
        token = login_response.json()["result"]["accessToken"]
        print("Login successful!")
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Failed to parse login response: {str(e)}")
        print(f"Response content: {login_response.text}")
        exit(1)
else:
    print("Using API key authentication")

# %%
def get_request_headers(accessToken=None):
    """Create headers with either Bearer token or API key authentication"""
    # Extract the base URL for Origin and Referer headers
    # Remove '/api' from the end of the API endpoint to get the base URL
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

def get_all_images(projectId, prospectId, accessToken=None):
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(accessToken)

    response = requests.request("GET", url, headers=headers, data=payload)

    return response

res = get_all_images(projectId, prospectId, token)  # token will be None if using API key

data = res.json()['result']['items']
image_data = [[x['files'][0]['fileName'], x['depthFrom'], x['depthTo'], x['standardType'], x['imageClass'], x['type'],x['drillHole']['id']] for x in data]
uploaded_files = ([x[0].replace(f"_{x[0].split('_')[-1]}", "")+f"_{x[1]}" for x in image_data])

tmp = {}
for i in uploaded_files:
    if i not in tmp:
        tmp[i] = 1
    else:
        tmp[i] += 1

duplicated_files = []
for i in tmp:
    if tmp[i] > 1:
        duplicated_files.append(i)

import csv

# Specify the output CSV file name
output_csv = f"duplicated_files_{timestamp}.csv"

with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["File Name"])  # Add a header row
    for file_name in duplicated_files:
        writer.writerow([file_name])

print(f"Duplicated files saved to {output_csv}")

# Specify the output CSV file name
output_csv = f"uploaded_files_{timestamp}.csv"

# Write the uploaded_files list to the CSV file
with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["File Name","depthFrom","depthTo","standardType","imageClass","type","drillHoleID"])  # Add a header row
    for file_name,depthFrom,depthTo,standardType,imageClass,type,drillHoleID in image_data:
        writer.writerow([file_name,depthFrom,depthTo,standardType,imageClass,type,drillHoleID])

print(f"Uploaded files saved to {output_csv}")

def get_all_holes(accessToken=None):
    url = f"{api_endpoint}/services/app/DrillHole/GetAll?MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(accessToken)
    response = requests.request("GET", url, headers=headers, data=payload)

    return response

res = get_all_holes(token)  # token will be None if using API key
data = res.json()['result']['items']
drill_holes = [[x['name'], x['id'], x['drillHoleStatus'], x['elevation'], x['northing'],\
                x['easting'], x['longitude'], x['latitude'], x['dip'], x['azimuth'], x['rl'], x['maxDepth']] for x in data]

import csv

# Specify the output CSV file name
output_csv = f"drill_holses_{timestamp}.csv"

# Write the uploaded_files list to the CSV file
with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Hole Name","ID","drillHoleStatus","elevation","northing","easting","longitude","latitude","dip","azimuth","rl","maxDepth"])  # Add a header row
    for name,id,drillHoleStatus,elevation,northing,easting,longitude,latitude,dip,azimuth,rl,maxDepth in drill_holes:
        writer.writerow([name,id,drillHoleStatus,elevation,northing,easting,longitude,latitude,dip,azimuth,rl,maxDepth])

print(f"Drill holes files saved to {output_csv}")