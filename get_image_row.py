# %%
import pandas as pd
import requests
import json
import os
import csv
from datetime import datetime
from authentication import init_auth, authenticate, get_request_headers

debug = True

# Initialize authentication
auth_config = init_auth()
projectId = auth_config['projectId']
prospectId = auth_config['prospectId']
api_key = auth_config['api_key']
api_endpoint = auth_config['api_endpoint']
use_api_key = auth_config['use_api_key']
use_credentials = auth_config['use_credentials']

# Create log file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Create necessary directories for logs and results
logs_dir = os.path.join("logs", "get_image_row", "logs")
success_dir = os.path.join("logs", "get_image_row", "success")

# Create directories if they don't exist
os.makedirs(logs_dir, exist_ok=True)
os.makedirs(success_dir, exist_ok=True)


# Get authentication token
token = authenticate(auth_config)
if token is None and use_credentials:
    print("Authentication failed. Please check your credentials and try again.")
    exit(1)


def get_image_row_data(projectId, prospectId, accessToken=None):
    """
    Get image row data from the API
    This includes manual corrections by the user adjusting line segments and block depths
    """
    url = f"{api_endpoint}/services/app/Image/GetDetailByRow?projectId={projectId}&prospectId={prospectId}"
    
    payload = {}
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)
    
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
    log_file_path = os.path.join(logs_dir, f"image_row_data_raw_{timestamp}.json")
    with open(log_file_path, "w") as f:
        json.dump(data, f, indent=4)
        
    print(f"Raw data saved to {log_file_path}")
    
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
    output_csv = os.path.join(success_dir, f"image_row_summary_{timestamp}.csv")
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
    detailed_output_csv = os.path.join(success_dir, f"image_row_detailed_{timestamp}.csv")
    df_detailed.to_csv(detailed_output_csv, index=False)
    
    print(f"Detailed image row data with row boundaries saved to {detailed_output_csv}")
    
except (KeyError, json.JSONDecodeError) as e:
    error_message = f"Failed to parse response: {str(e)}"
    print(error_message)
    
    # Save error to log file
    error_log_path = os.path.join(logs_dir, f"error_log_{timestamp}.txt")
    with open(error_log_path, "w") as f:
        f.write(f"{error_message}\n")
        f.write(f"Response content: {response.text}")
    
    print(f"Error log saved to {error_log_path}")
    print(f"Response content: {response.text}")
    exit(1)