#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
import csv
from datetime import datetime
import time
from authentication import init_auth, authenticate, get_request_headers

# Initialize authentication
auth_config = init_auth()
projectId = auth_config['projectId']
prospectId = auth_config['prospectId']
workflow_id = auth_config['workflow_id']
api_key = auth_config['api_key']
api_endpoint = auth_config['api_endpoint']
use_api_key = auth_config['use_api_key']
use_credentials = auth_config['use_credentials']

# Create timestamp for log files
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Create directory structure if it doesn't exist
log_dir = "logs/execute_batch/logs"
result_dir = "logs/execute_batch/success"
os.makedirs(log_dir, exist_ok=True)
os.makedirs(result_dir, exist_ok=True)

# Set file paths
log_file = f"{log_dir}/batch_processing_log_{timestamp}.txt"
success_file = f"{result_dir}/successful_images_{timestamp}.csv"
failed_file = f"{result_dir}/failed_images_{timestamp}.csv"



def get_all_images(projectId, prospectId, accessToken=None):
    """
    Get all images for a specific project and prospect
    """
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)

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
    Returns:
        - On success: Response object
        - On failure: Tuple(None, error_details)
    """
    url = f"{api_endpoint}/services/app/Image/ProcessImage"

    payload = json.dumps({
        "imageId": image_id,
        "workflowId": workflow_id
    })
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)

    error_details = {
        'error_type': None,
        'error_message': None,
        'status_code': None,
        'response_content': None,
        'request_url': url,
        'request_payload': payload
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        return response, None

    except requests.exceptions.Timeout:
        error_details.update({
            'error_type': 'Timeout',
            'error_message': f"Request timed out after 30 seconds for image {image_id}"
        })
        return None, error_details

    except requests.exceptions.ConnectionError as e:
        error_details.update({
            'error_type': 'ConnectionError',
            'error_message': f"Connection failed for image {image_id}: {str(e)}"
        })
        return None, error_details

    except requests.exceptions.HTTPError as e:
        error_details.update({
            'error_type': 'HTTPError',
            'error_message': f"HTTP error occurred for image {image_id}: {str(e)}",
            'status_code': e.response.status_code,
            'response_content': e.response.text
        })
        return None, error_details

    except requests.exceptions.RequestException as e:
        error_details.update({
            'error_type': 'RequestException',
            'error_message': f"Request failed for image {image_id}: {str(e)}"
        })
        if hasattr(e, 'response') and e.response is not None:
            error_details.update({
                'status_code': e.response.status_code,
                'response_content': e.response.text
            })
        return None, error_details

# Initialize logger
with open(log_file, 'w') as f:
    f.write(f"=== Batch Image Processing Log ===\n")
    f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Project ID: {projectId}\n")
    f.write(f"Prospect ID: {prospectId}\n")
    f.write(f"Workflow ID: {workflow_id}\n")
    f.write(f"Authentication method: {'API Key' if use_api_key else 'Username/Password'}\n\n")

# Get authentication token
token = authenticate(auth_config)

# Log authentication status
with open(log_file, 'a') as f:
    if use_credentials and token:
        f.write(f"Authentication successful with username/password\n")
    elif token is None and use_credentials:
        f.write(f"Authentication failed\n")
        exit(1)
    else:
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
print(f"Total images to process: {total_images}")
print("Progress: 0/{} (0%)".format(total_images))
with open(log_file, 'a') as f:
    f.write(f"\nStarting image processing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total images to process: {total_images}\n")

for i, image in enumerate(images_data):
    image_id = image['id']
    filename = image['files'][0]['fileName'] if image['files'] else 'Unknown'
    drill_hole_name = image['drillHole']['name'] if image['drillHole'] else 'Unknown'
    depth_from = image.get('depthFrom', 'Unknown')
    depth_to = image.get('depthTo', 'Unknown')
    
    # Calculate completion percentage
    completion_percentage = round((i+1) / total_images * 100, 1)
    
    # Clear previous line and show progress
    print(f"\rProgress: {i+1}/{total_images} ({completion_percentage}%) - Processing: {filename}", end="")
    
    # Every 10 images or on the last image, print a newline for better readability
    if (i+1) % 10 == 0 or i+1 == total_images:
        print()  # Print a newline
        
    with open(log_file, 'a') as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing image {i+1}/{total_images}: {filename}\n")
        f.write(f"  Image ID: {image_id}\n")
        f.write(f"  Drill Hole: {drill_hole_name}\n")
        f.write(f"  Depth Range: {depth_from} - {depth_to}\n")
    
    # Process the image with the workflow
    process_response, error_details = process_image(image_id, workflow_id, token)
    
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
        # Log detailed error information
        with open(log_file, 'a') as f:
            f.write(f"  ✗ Failed to process image. Details:\n")
            f.write(f"    Error Type: {error_details['error_type']}\n")
            f.write(f"    Error Message: {error_details['error_message']}\n")
            if error_details['status_code']:
                f.write(f"    Status Code: {error_details['status_code']}\n")
            if error_details['response_content']:
                f.write(f"    Response Content: {error_details['response_content']}\n")
            f.write(f"    Request URL: {error_details['request_url']}\n")
            f.write(f"    Request Payload: {error_details['request_payload']}\n")
        
        # Create user-friendly error message
        error_msg = f"{error_details['error_type']}: {error_details['error_message']}"
        print(f"  ✗ Failed to process image: {filename}")
        print(f"    Error: {error_msg}")
        
        image_info['Error'] = error_msg
        image_info['Error Type'] = error_details['error_type']
        failed_images.append(image_info)
    # Add a small delay to avoid overwhelming the API
    time.sleep(0.5)
    
    # Print progress summary every 20 images
    if (i+1) % 20 == 0:
        print(f"\n--- Progress Summary ---")
        print(f"Processed: {i+1}/{total_images} images ({completion_percentage}%)")
        print(f"Success: {len(successful_images)}, Failed: {len(failed_images)}")
        print(f"------------------------\n")
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
print(f"\n=== Processing Complete! ===")
print(f"Total Images: {total_images}")
print(f"Successfully Processed: {len(successful_images)} ({round(len(successful_images)/total_images*100, 1)}%)")
print(f"Failed to Process: {len(failed_images)} ({round(len(failed_images)/total_images*100, 1)}%)")
print(f"Log file: {log_file}")

if len(failed_images) > 0:
    print(f"\nSome images failed to process. Check {failed_file} for details.")