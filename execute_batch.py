#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
import csv
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import time

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
print(f"WORKFLOW_ID: {os.getenv('WORKFLOW_ID')}")
print(f"API_KEY: {os.getenv('API_KEY')}")
print(f"USERNAME: {os.getenv('USERNAME')}")
print(f"PASSWORD: {os.getenv('PASSWORD')}")
print(f"API_ENDPOINT: {os.getenv('API_ENDPOINT')}")

# Setup configuration from environment variables
projectId = int(os.getenv('PROJECT_ID', '0'))
prospectId = int(os.getenv('PROSPECT_ID', '0'))
workflow_id = int(os.getenv('WORKFLOW_ID', '0'))
api_key = os.getenv('API_KEY')
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')
api_endpoint = os.getenv('API_ENDPOINT', 'https://api-portal1.fastgeo.com.au/api')

# Check if we have valid authentication options
use_api_key = api_key is not None and api_key.strip() != ""
use_credentials = username is not None and password is not None and username.strip() != "" and password.strip() != ""

if not (use_api_key or use_credentials):
    raise ValueError("Please set either API_KEY or both USERNAME and PASSWORD in .env file")

# Create timestamp for log files
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"batch_processing_log_{timestamp}.txt"
success_file = f"successful_images_{timestamp}.csv"
failed_file = f"failed_images_{timestamp}.csv"

def login(username, password):
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

def get_request_headers(accessToken=None):
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

def get_all_images(projectId, prospectId, accessToken=None):
    """
    Get all images for a specific project and prospect
    """
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(accessToken)

    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching images: {str(e)}")
        if 'response' in locals():
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return None

def process_image(image_id, workflow_id, accessToken=None):
    """
    Process an image with the specified workflow
    """
    url = f"{api_endpoint}/services/app/Image/ProcessImage"

    payload = json.dumps({
        "imageId": image_id,
        "workflowId": workflow_id
    })
    headers = get_request_headers(accessToken)

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error processing image {image_id}: {str(e)}")
        if 'response' in locals():
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return None

# Initialize logger
with open(log_file, 'w') as f:
    f.write(f"=== Batch Image Processing Log ===\n")
    f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Project ID: {projectId}\n")
    f.write(f"Prospect ID: {prospectId}\n")
    f.write(f"Workflow ID: {workflow_id}\n")
    f.write(f"Authentication method: {'API Key' if use_api_key else 'Username/Password'}\n\n")

# Set token to None initially
token = None

# Only perform login if using username/password authentication
if use_credentials:
    print("Authenticating with username and password...")
    login_response = login(username, password)
    if login_response is None:
        print("Login failed. Please check your credentials and try again.")
        exit(1)

    try:
        token = login_response.json()["result"]["accessToken"]
        print("Login successful!")
        with open(log_file, 'a') as f:
            f.write(f"Authentication successful with username/password\n")
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Failed to parse login response: {str(e)}")
        print(f"Response content: {login_response.text}")
        with open(log_file, 'a') as f:
            f.write(f"Authentication failed: {str(e)}\n")
        exit(1)
else:
    print("Using API key authentication")
    with open(log_file, 'a') as f:
        f.write(f"Using API key authentication\n")

# Get all images
print(f"Fetching images for Project ID: {projectId}, Prospect ID: {prospectId}...")
images_response = get_all_images(projectId, prospectId, token)
if images_response is None:
    print("Failed to fetch images. Check the log file for details.")
    with open(log_file, 'a') as f:
        f.write(f"Failed to fetch images at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    exit(1)

try:
    images_data = images_response.json()['result']['items']
    total_images = len(images_data)
    print(f"Found {total_images} images to process")
    with open(log_file, 'a') as f:
        f.write(f"Found {total_images} images to process\n")
except (KeyError, json.JSONDecodeError) as e:
    print(f"Failed to parse images response: {str(e)}")
    with open(log_file, 'a') as f:
        f.write(f"Failed to parse images response: {str(e)}\n")
    exit(1)

# Initialize success and failure counters
successful_images = []
failed_images = []

# Process all images
print("\nStarting image processing...")
with open(log_file, 'a') as f:
    f.write(f"\nStarting image processing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

for i, image in enumerate(images_data):
    image_id = image['id']
    filename = image['files'][0]['fileName'] if image['files'] else 'Unknown'
    drill_hole_name = image['drillHole']['name'] if image['drillHole'] else 'Unknown'
    depth_from = image.get('depthFrom', 'Unknown')
    depth_to = image.get('depthTo', 'Unknown')
    
    print(f"Processing image {i+1}/{total_images}: {filename}")
    with open(log_file, 'a') as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing image {i+1}/{total_images}: {filename}\n")
        f.write(f"  Image ID: {image_id}\n")
        f.write(f"  Drill Hole: {drill_hole_name}\n")
        f.write(f"  Depth Range: {depth_from} - {depth_to}\n")
    
    # Process the image with the workflow
    process_response = process_image(image_id, workflow_id, token)
    
    image_info = {
        'Image ID': image_id,
        'Filename': filename,
        'Drill Hole': drill_hole_name,
        'Depth From': depth_from,
        'Depth To': depth_to,
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if process_response and process_response.status_code == 200:
        print(f"  ✓ Successfully processed image: {filename}")
        with open(log_file, 'a') as f:
            f.write(f"  ✓ Successfully processed\n")
        successful_images.append(image_info)
    else:
        error_msg = "Unknown error"
        if process_response:
            try:
                error_json = process_response.json()
                error_msg = error_json.get('error', {}).get('message', 'Unknown error')
            except:
                error_msg = f"Status Code: {process_response.status_code}"
        
        print(f"  ✗ Failed to process image: {filename}. Error: {error_msg}")
        with open(log_file, 'a') as f:
            f.write(f"  ✗ Failed to process. Error: {error_msg}\n")
        
        image_info['Error'] = error_msg
        failed_images.append(image_info)
    
    # Add a small delay to avoid overwhelming the API
    time.sleep(0.5)

# Write summary to log
with open(log_file, 'a') as f:
    f.write(f"\n=== Processing Summary ===\n")
    f.write(f"Total Images: {total_images}\n")
    f.write(f"Successfully Processed: {len(successful_images)}\n")
    f.write(f"Failed to Process: {len(failed_images)}\n")
    f.write(f"Completion Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Save successful and failed images to CSV files
if successful_images:
    with open(success_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=successful_images[0].keys())
        writer.writeheader()
        writer.writerows(successful_images)
    print(f"\nSuccessful images saved to: {success_file}")

if failed_images:
    with open(failed_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=failed_images[0].keys())
        writer.writeheader()
        writer.writerows(failed_images)
    print(f"Failed images saved to: {failed_file}")

# Print final summary
print(f"\nProcessing complete!")
print(f"Total Images: {total_images}")
print(f"Successfully Processed: {len(successful_images)}")
print(f"Failed to Process: {len(failed_images)}")
print(f"Log file: {log_file}")

if len(failed_images) > 0:
    print(f"\nSome images failed to process. Check {failed_file} for details.")