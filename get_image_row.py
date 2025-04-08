# %%
import pandas as pd
import requests
import json
import os
import csv
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
projectId = int(os.getenv('PROJECT_ID', '1'))
prospectId = int(os.getenv('PROSPECT_ID', '11'))
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

# Create log file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# %%
def login(username, password):
    """
    Authenticate with username and password to get an access token
    """
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

def get_image_row_data(projectId, prospectId, accessToken=None):
    """
    Get image row data from the API
    This includes manual corrections by the user adjusting line segments and block depths
    """
    url = f"{api_endpoint}/services/app/Image/GetDetailByRow?projectId={projectId}&prospectId={prospectId}"
    
    payload = {}
    headers = get_request_headers(accessToken)
    
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response
    except requests.exceptions.RequestException as e:
        print(f"Get image row data request failed: {str(e)}")
        if 'response' in locals():
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return None

# Make the API call to get image row data
response = get_image_row_data(projectId, prospectId, token)  # token will be None if using API key

if response is None:
    print("Failed to get image row data. Please check your parameters and try again.")
    exit(1)

# Process the response
try:
    data = response.json()
    
    # Save the raw response for debugging
    with open(f"image_row_data_raw_{timestamp}.json", "w") as f:
        json.dump(data, f, indent=4)
        
    print(f"Raw data saved to image_row_data_raw_{timestamp}.json")
    
    # Extract relevant data for the summary
    items = data['result']['items']
    
    # Prepare a structured summary
    summary_data = []
    
    for item in items:
        project_name = item.get('projectName', '')
        prospect_name = item.get('prospectName', '')
        drill_hole_name = item.get('drillHoleName', '')
        image_id = item.get('imageId', 0)
        crop_polygon = item.get('cropPolygon', '')
        
        # Process OCRs if available
        ocrs = item.get('ocrs', [])
        for ocr in ocrs:
            ocr_id = ocr.get('id', '')
            ocr_type = ocr.get('type', '')
            ocr_x = ocr.get('x', 0)
            ocr_original_x = ocr.get('originalX', 0)
            ocr_y = ocr.get('y', 0)
            ocr_width = ocr.get('width', 0)
            ocr_height = ocr.get('height', 0)
            ocr_text = ocr.get('text', '')
            ocr_row_index = ocr.get('rowIndex', 0)
            
            # Add to summary data
            summary_data.append({
                'projectName': project_name,
                'prospectName': prospect_name,
                'drillHoleName': drill_hole_name,
                'imageId': image_id,
                'ocrId': ocr_id,
                'ocrType': ocr_type,
                'ocrText': ocr_text,
                'rowIndex': ocr_row_index,
                'x': ocr_x,
                'y': ocr_y,
                'width': ocr_width,
                'height': ocr_height,
                'originalX': ocr_original_x
            })
    
    # Create a DataFrame for easier manipulation
    df = pd.DataFrame(summary_data)
    
    # Create CSV summary
    output_csv = f"image_row_summary_{timestamp}.csv"
    df.to_csv(output_csv, index=False)
    
    print(f"Image row data summary saved to {output_csv}")
    
    # Create a more detailed summary with core outlines information
    detailed_summary = []
    
    for item in items:
        project_name = item.get('projectName', '')
        prospect_name = item.get('prospectName', '')
        drill_hole_name = item.get('drillHoleName', '')
        image_id = item.get('imageId', 0)
        
        # Process core outlines if available
        core_outlines = item.get('coreOutlines', [])
        for outline in core_outlines:
            outline_name = outline.get('name', '')
            is_poly_complete = outline.get('isPolyComplete', False)
            
            # Process points data by finding min and max Y values to determine rows
            points = outline.get('points', [])
            if points:
                # Extract y-coordinates to find row boundaries
                y_values = [point[1] for point in points]
                min_y = min(y_values) if y_values else 0
                max_y = max(y_values) if y_values else 0
                
                detailed_summary.append({
                    'projectName': project_name,
                    'prospectName': prospect_name,
                    'drillHoleName': drill_hole_name,
                    'imageId': image_id,
                    'outlineName': outline_name,
                    'isPolyComplete': is_poly_complete,
                    'rowFrom': min_y,
                    'rowTo': max_y,
                    'numPoints': len(points)
                })
    
    # Create DataFrame for detailed summary
    df_detailed = pd.DataFrame(detailed_summary)
    
    # Create detailed CSV summary
    detailed_output_csv = f"image_row_detailed_{timestamp}.csv"
    df_detailed.to_csv(detailed_output_csv, index=False)
    
    print(f"Detailed image row data with row boundaries saved to {detailed_output_csv}")
    
except (KeyError, json.JSONDecodeError) as e:
    print(f"Failed to parse response: {str(e)}")
    print(f"Response content: {response.text}")
    exit(1)