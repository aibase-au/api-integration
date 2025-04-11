#!/usr/bin/env python
# -*- coding: utf-8 -*-
# coding: utf-8

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

def load_drill_holes_from_csv(csv_path="sendtobatch.csv"):
    """
    Read the sendtobatch.csv file and extract drill hole IDs.
    
    Args:
        csv_path: Path to the CSV file containing drill hole IDs
        
    Returns:
        List of drill hole IDs
    """
    try:
        df = pd.read_csv(csv_path)
        # Check if 'HoleID' column exists
        if 'HoleID' not in df.columns:
            print(f"Error: CSV file does not contain 'HoleID' column. Columns found: {df.columns}")
            return []
        
        # Extract and return hole IDs as a list
        hole_ids = df['HoleID'].tolist()
        print(f"Loaded {len(hole_ids)} drill hole IDs from {csv_path}: {', '.join(hole_ids)}")
        return hole_ids
    except Exception as e:
        print(f"Error loading drill holes from CSV: {str(e)}")
        return []

def get_image_row_data(projectId, prospectId, accessToken=None, skip_count=0, max_result_count=100, drill_hole_name=None):
    """
    Get image row data from the API
    This includes manual corrections by the user adjusting line segments and block depths
    
    Args:
        projectId: Project ID
        prospectId: Prospect ID
        accessToken: Authentication token
        skip_count: Number of records to skip
        max_result_count: Maximum number of records to return per request
        drill_hole_name: Optional filter by drill hole name
        
    Returns:
        Response JSON data if successful, None otherwise
    """
    # Build the URL with optional drill hole name filter
    url = f"{api_endpoint}/services/app/Image/GetDetailByRow?projectId={projectId}&prospectId={prospectId}&SkipCount={skip_count}&MaxResultCount={max_result_count}"
    
    # Add drill hole name filter if provided
    if drill_hole_name:
        url += f"&drillHoleName={drill_hole_name}"
        print(f"Filtering results by drill hole: {drill_hole_name}")
    
    payload = {}
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)
    
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Get image row data request failed: {str(e)}")
        if 'response' in locals():
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return None

def get_all_image_row_data(projectId, prospectId, accessToken=None, batch_size=100, drill_hole_name=None):
    """
    Get all image row data by making multiple API calls until all results are retrieved
    
    Args:
        projectId: Project ID
        prospectId: Prospect ID
        accessToken: Authentication token
        batch_size: Number of records to retrieve per API call
        drill_hole_name: Optional filter by drill hole name
        
    Returns:
        Combined results from all API calls
    """
    all_items = []
    skip_count = 0
    total_count = None
    
    print(f"Retrieving image row data for {drill_hole_name if drill_hole_name else 'all drill holes'}...")
    
    while total_count is None or skip_count < total_count:
        print(f"Fetching batch: skip={skip_count}, max={batch_size}")
        
        # Get the current batch of results
        response_data = get_image_row_data(
            projectId,
            prospectId,
            accessToken,
            skip_count=skip_count,
            max_result_count=batch_size,
            drill_hole_name=drill_hole_name
        )
        
        if response_data is None:
            print("Failed to get image row data. Please check your parameters and try again.")
            return None
        
        # Update the total count
        if total_count is None:
            total_count = response_data['result']['totalCount']
            print(f"Total records to retrieve: {total_count}")
        
        # Add the items from this batch to our collection
        items = response_data['result']['items']
        all_items.extend(items)
        print(f"Retrieved {len(items)} items. Total so far: {len(all_items)}/{total_count}")
        
        # Increment the skip count for the next batch
        skip_count += len(items)
        
        # If we didn't get as many items as we requested, we're done
        if len(items) < batch_size:
            break
    
    # Create a result structure similar to the original API response
    combined_result = {
        'result': {
            'totalCount': total_count,
            'items': all_items
        }
    }
    
    return combined_result

def process_image_row_data(response_data, timestamp, drill_hole_name=None):
    """
    Process the image row data and save summaries to files
    
    Args:
        response_data: The API response data
        timestamp: Timestamp for file naming
        drill_hole_name: Optional drill hole name for file naming
        
    Returns:
        Tuple containing summary_data and detailed_summary
    """
    try:
        data = response_data
        
        # File name suffix for specific drill hole
        file_suffix = f"_{drill_hole_name}" if drill_hole_name else ""
        
        # Save the raw response for debugging
        log_file_path = os.path.join(logs_dir, f"image_row_data_raw{file_suffix}_{timestamp}.json")
        with open(log_file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        print(f"Raw data saved to {log_file_path}")
        print(f"Retrieved a total of {data['result']['totalCount']} records")
        
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
        output_csv = os.path.join(success_dir, f"image_row_summary{file_suffix}_{timestamp}.csv")
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
        detailed_output_csv = os.path.join(success_dir, f"image_row_detailed{file_suffix}_{timestamp}.csv")
        df_detailed.to_csv(detailed_output_csv, index=False)
        
        print(f"Detailed image row data with row boundaries saved to {detailed_output_csv}")
        
        # Return the processed data for merging
        return summary_data, detailed_summary, items
        
    except (KeyError, json.JSONDecodeError) as e:
        error_message = f"Failed to parse response: {str(e)}"
        print(error_message)
        
        # Save error to log file
        error_log_path = os.path.join(logs_dir, f"error_log{file_suffix}_{timestamp}.txt")
        with open(error_log_path, "w", encoding='utf-8') as f:
            f.write(f"{error_message}\n")
            f.write(f"Response content: {json.dumps(response_data) if response_data else 'No response data'}")
        
        print(f"Error log saved to {error_log_path}")
        if response_data:
            print(f"Response content: {json.dumps(response_data, indent=2)}")
        return [], [], []

# Main execution
def main():
    # Load drill hole IDs from sendtobatch.csv
    drill_holes = load_drill_holes_from_csv()
    
    if not drill_holes:
        print("No drill holes found in sendtobatch.csv. Please check the file and try again.")
        exit(1)
    
    # Initialize containers for merged data
    all_summary_data = []
    all_detailed_summary = []
    all_items = []
    total_records = 0
    
    # Process each drill hole
    for drill_hole in drill_holes:
        print(f"\n--- Processing drill hole: {drill_hole} ---")
        
        # Make the API call to get image row data for this drill hole
        response_data = get_all_image_row_data(projectId, prospectId, token, drill_hole_name=drill_hole)
        
        if response_data is None:
            print(f"Failed to get image row data for {drill_hole}. Skipping to next drill hole.")
            continue
        
        # Process the response data and get the results
        summary_data, detailed_summary, items = process_image_row_data(response_data, timestamp, drill_hole)
        
        # Add to merged data
        all_summary_data.extend(summary_data)
        all_detailed_summary.extend(detailed_summary)
        all_items.extend(items)
        total_records += len(items)
    
    # Create merged result structure
    merged_result = {
        'result': {
            'totalCount': total_records,
            'items': all_items
        }
    }
    
    # Save merged JSON file
    merged_json_path = os.path.join(success_dir, f"merged_image_row_data_{timestamp}.json")
    with open(merged_json_path, "w", encoding='utf-8') as f:
        json.dump(merged_result, f, indent=4)
    
    print(f"\nMerged JSON data saved to {merged_json_path}")
    
    # Create merged CSV files
    if all_summary_data:
        merged_summary_csv = os.path.join(success_dir, f"merged_image_row_summary_{timestamp}.csv")
        pd.DataFrame(all_summary_data).to_csv(merged_summary_csv, index=False)
        print(f"Merged summary CSV saved to {merged_summary_csv}")
    
    if all_detailed_summary:
        merged_detailed_csv = os.path.join(success_dir, f"merged_image_row_detailed_{timestamp}.csv")
        pd.DataFrame(all_detailed_summary).to_csv(merged_detailed_csv, index=False)
        print(f"Merged detailed CSV saved to {merged_detailed_csv}")
    
    print("\nAll drill holes processed successfully.")

if __name__ == "__main__":
    main()