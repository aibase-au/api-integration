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

# %%
projectId = int(os.getenv('PROJECT_ID', '12'))
prospectId = int(os.getenv('PROSPECT_ID', '12'))
num_errors = 1
api_key = os.getenv('API_KEY')
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')
api_endpoint = os.getenv('API_ENDPOINT', 'https://api-portal1.fastgeo.com.au/api')

# Check if we have valid authentication options
use_api_key = api_key is not None and api_key.strip() != ""
use_credentials = username is not None and password is not None and username.strip() != "" and password.strip() != ""

if not (use_api_key or use_credentials):
    raise ValueError("Please set either API_KEY or both USERNAME and PASSWORD in .env file")

# %%
df = pd.read_csv('file_summary.csv')

hole_names = df['Folder'].values
depth_from = df["Start Number"].values
depth_to = df["End Number"].values
conditions = df["Condition"].values
paths = df["Full Path"].values

# Create log file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"logdata_{timestamp}.txt"

with open(log_file, 'w') as f:
    f.write(f"=== File Processing Order ===\n")
    f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total files to process: {len(df)}\n")
    f.write("\nFiles in Processing Order:\n")
    f.write("-" * 50 + "\n")

    # Process files in the order they appear in the CSV
    for index, row in df.iterrows():
        line_number = index + 2  # +2 because of 0-based index and header row
        f.write(f"{index + 1}. File: {row['Original Filename']}\n")
        f.write(f"   Line Number: {line_number}\n")
        f.write(f"   Drill Hole: {row['Folder']}\n")
        f.write(f"   Condition: {row['Condition']}\n")
        f.write(f"   Full Path: {row['Full Path']}\n")
        f.write(f"   Depth Range: {row['Start Number']} - {row['End Number']}\n")
        f.write("\n")

    f.write("\n=== Processing Summary ===\n")
    f.write(f"Total Files: {len(df)}\n")
    f.write(f"Total Drill Holes: {len(df['Folder'].unique())}\n")
    f.write(f"Unique Conditions: {set(df['Condition'].values)}\n")

print(f"Log file created: {log_file}")

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

# Create a unified header generation function
def get_request_headers(accessToken=None):
    """Create headers with either Bearer token or API key authentication"""
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

# %%
def get_all_images(projectId, prospectId, accessToken=None):
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(accessToken)

    response = requests.request("GET", url, headers=headers, data=payload)

    return response

res = get_all_images(projectId, prospectId, token)

data = res.json()['result']['items']
uploaded_files = [[x['files'][0]['fileName'], x['standardType']] for x in data]
uploaded_files = ([x[0].replace(f"_{x[0].split('_')[-1]}", "")+f"_{x[1]}" for x in uploaded_files])

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

import numpy as np

all_duplicated_id = []
for file in duplicated_files:
    duplicated_idx = np.where(np.array(uploaded_files) == file)[0]
    list_id = [data[idx]['id'] for idx in duplicated_idx]
    all_duplicated_id += list_id[1:]

# Save all duplicated IDs to a file
duplicated_ids_file = f"duplicated_ids_{timestamp}.txt"
with open(duplicated_ids_file, 'w') as f:
    f.write("Duplicated IDs:\n")
    for dup_id in all_duplicated_id:
        f.write(f"{dup_id},\n")

print(f"Duplicated IDs saved to: {duplicated_ids_file}")

# %%
def create_drill_hole(accessToken, name, projectId, prospectId):
    url = f"{api_endpoint}/services/app/DrillHole/Create"

    payload = json.dumps({
        "name": name,
        "rl": 0,
        "maxDepth": 0,
        "projectId": projectId,
        "prospectId": prospectId,
        "isActive": True
    })
    headers = get_request_headers(accessToken)

    response = requests.request("POST", url, headers=headers, data=payload)

    return response

# create_drill_hole(token, "test", 4, 4)

# %%
def upload_image(img_path, projectId, prospectId, holeId, c, accessToken=None):
    url = f"{api_endpoint}/services/app/Image/Create"

    payload = {
        'Type': '1',
        'ImageClass': '1',
        'StandardType': c,
        'ProjectId': projectId,
        'ProspectId': prospectId,
        'HoleId': holeId
    }
    files=[
        ('image',(os.path.basename(img_path),open(img_path,'rb'),'image/png'))
    ]
    headers = get_request_headers(accessToken)

    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    return response

# %%
# Create all drill holes
list_of_drill_holes = {}
print("Creating drill holes...")
for name in set(hole_names):
   response = create_drill_hole(token, name, projectId, prospectId)
   holeId = response.json()["result"]["id"]
   list_of_drill_holes[name] = holeId
   print(f"Created drill hole: {name}")

# %%
e = 0
total_files = len(df)
uploaded_count = 0
skipped_count = 0

file = open(f"log_{timestamp}.txt", "w")
file.write(f"=== File Upload Log ===\n")

print("\nStarting file uploads...")
for index, row in df.iterrows():
    try:
        hole_name = row['Folder']
        img_path = row['Full Path']
        start = row['Start Number']
        end = row['End Number']
        c = row['Condition']
        c = str(c).strip()
        image_class = 1 if c.lower() == "dry" else 2
        name = f"{hole_name}_{str(start).rstrip('0').rstrip('.')}_{str(end).rstrip('0').rstrip('.')}_{image_class}"
        if name in uploaded_files:
            print(f"File already uploaded: {img_path}. Skipped.")
            skipped_count += 1
            file.write(f"[{datetime.now()}] File already uploaded: {img_path}. Skipped.\n")
            continue
        if debug:
            print(f"Going to upload: {os.path.basename(img_path)}, Raw Condition: '{c}', ImageClass: {image_class}")
            file.write(f"[{datetime.now()}] Going to upload: {os.path.basename(img_path)}, Raw Condition: '{c}', ImageClass: {image_class}\n")
        else:
            response = upload_image(img_path, projectId, prospectId, list_of_drill_holes[hole_name], image_class, token)
            if response.status_code == 200:
                uploaded_count += 1
                print(f"Successfully uploaded {os.path.basename(img_path)} ({uploaded_count}/{total_files})")
                file.write(f"[{datetime.now()}]Successfully uploaded {os.path.basename(img_path)}\n")
            else:
                e += 1
                print(f"Error uploading {os.path.basename(img_path)} for {name}")
                file.write(f"[{datetime.now()}]Error uploading {os.path.basename(img_path)} for {name}\n")
                if e == num_errors:
                    break
    except Exception as ex:
        e += 1
        print(f"Error when uploading images for {name}: {str(ex)}")
        file.write(f"[{datetime.now()}]Error when uploading images for {name}: {str(ex)}\n")
        if e == num_errors:
            break

print(f"\nUpload complete. Successfully uploaded {uploaded_count}/{total_files} files.")
print(f"Skipped {skipped_count} files already uploaded.")
file.write(f"\nUpload complete. Successfully uploaded {uploaded_count}/{total_files} files.\n")
file.write(f"Skipped {skipped_count} files already uploaded.\n")
file.close()

# %%


# %%


# %%



