#!/usr/bin/env python
# -*- coding: utf-8 -*-
# coding: utf-8

# %%
import pandas as pd
import requests
import json
import os
from datetime import datetime
from authentication import init_auth, authenticate, get_request_headers
import pathlib

# Initialize authentication
auth_config = init_auth()
projectId = auth_config['projectId']
prospectId = auth_config['prospectId']
api_key = auth_config['api_key']
api_endpoint = auth_config['api_endpoint']
use_api_key = auth_config['use_api_key']
use_credentials = auth_config['use_credentials']
num_errors = 1

# %%
df = pd.read_csv('filestoupload.csv')

hole_names = df['HoleID'].values
depth_from = df["BoxFrom"].values
depth_to = df["BoxTo"].values
image_types = df["ImageType"].values
paths = df["Full Path"].values

# Create necessary directories for logs and results
logs_dir = os.path.join("logs", "upload_image", "logs")
success_dir = os.path.join("logs", "upload_image", "success")
fail_dir = os.path.join("logs", "upload_image", "fail")

# Create directories if they don't exist
pathlib.Path(logs_dir).mkdir(parents=True, exist_ok=True)
pathlib.Path(success_dir).mkdir(parents=True, exist_ok=True)
pathlib.Path(fail_dir).mkdir(parents=True, exist_ok=True)

# Create a timestamp for this run
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Create a single log file for the entire process
log_file = os.path.join(logs_dir, f"upload_image_log_{timestamp}.txt")
log = open(log_file, 'w', encoding='utf-8')

# Write initial log information
log.write(f"=== Upload Kobold Process Log ===\n")
log.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

# Log file summary information
log.write(f"=== File Processing Order ===\n")
log.write(f"Total files to process: {len(df)}\n")
log.write("\nFiles in Processing Order:\n")
log.write("-" * 50 + "\n")

# Process files in the order they appear in the CSV
for index, row in df.iterrows():
    line_number = index + 2  # +2 because of 0-based index and header row
    log.write(f"{index + 1}. File: {row['Original Filename']}\n")
    log.write(f"   Line Number: {line_number}\n")
    log.write(f"   Drill Hole: {row['HoleID']}\n")
    log.write(f"   Image Type: {row['ImageType']}\n")
    log.write(f"   Full Path: {row['Full Path']}\n")
    log.write(f"   Depth Range: {row['BoxFrom']} - {row['BoxTo']}\n")
    log.write("\n")

log.write("\n=== Processing Summary ===\n")
log.write(f"Total Files: {len(df)}\n")
log.write(f"Total Drill Holes: {len(df['HoleID'].unique())}\n")
log.write(f"Unique Image Types: {set(df['ImageType'].values)}\n\n")

print(f"Log file created: {log_file}")

# %%

# Get authentication token
token = authenticate(auth_config)
if token is None and use_credentials:
    print("Authentication failed. Please check your credentials and try again.")
    exit(1)


# %%
def get_all_images(projectId, prospectId, accessToken=None):
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)

    response = requests.request("GET", url, headers=headers, data=payload)

    return response

def log_response_details(response, log_file=None):
    """
    Log detailed information about a response to help debug JSON parsing issues
    """
    details = [
        "\n=== API RESPONSE DETAILS ===",
        f"Status Code: {response.status_code}",
        f"URL: {response.url}",
        f"Reason: {response.reason}",
        "\nResponse Headers:"
    ]
    
    for header, value in response.headers.items():
        details.append(f"  {header}: {value}")
    
    details.append("\nResponse Content (first 1000 chars):")
    content = response.text[:1000] + ("..." if len(response.text) > 1000 else "")
    details.append(content)
    
    details_str = "\n".join(details)
    
    # Print to console
    print(details_str)
    
    # Also write to log file if provided
    if log_file:
        log_file.write(details_str + "\n")
    
    return details_str

res = get_all_images(projectId, prospectId, token)

# Try to parse JSON with detailed error handling
try:
    data = res.json()['result']['items']
except json.decoder.JSONDecodeError as e:
    print(f"ERROR: Failed to decode JSON response: {str(e)}")
    details = log_response_details(res, log)
    log.write(f"\n=== JSON DECODE ERROR ===\n{str(e)}\n")
    print("Request failed. See logs for details.")
    exit(1)
except KeyError as e:
    print(f"ERROR: JSON response missing expected keys: {str(e)}")
    log.write(f"\n=== JSON STRUCTURE ERROR ===\nMissing expected key: {str(e)}\n")
    
    # Log the actual JSON structure we received
    try:
        json_data = res.json()
        log.write("Actual JSON structure received:\n")
        log.write(json.dumps(json_data, indent=2) + "\n")
        print(f"Response didn't contain the expected structure. Full JSON written to log.")
    except Exception as inner_e:
        log_response_details(res, log)
        print(f"Failed to parse response as JSON: {str(inner_e)}")
    
    exit(1)
uploaded_files_data = []
missing_field_errors = []

for idx, item in enumerate(data):
    try:
        # Check if all required fields exist
        if 'drillHole' not in item or not item['drillHole'] or 'name' not in item['drillHole']:
            missing_field_errors.append(f"Missing 'drillHole.name' in item {idx}")
            continue
            
        if 'depthFrom' not in item:
            missing_field_errors.append(f"Missing 'depthFrom' in item {idx}")
            continue
            
        if 'depthTo' not in item:
            missing_field_errors.append(f"Missing 'depthTo' in item {idx}")
            continue
            
        if 'standardType' not in item:
            missing_field_errors.append(f"Missing 'standardType' in item {idx}")
            continue
        
        # All required fields exist, add to our list
        uploaded_files_data.append({
            'hole_name': item['drillHole']['name'],
            'depth_from': item['depthFrom'],
            'depth_to': item['depthTo'],
            'standard_type': item['standardType']  # 1 for Dry, 2 for Wet
        })
    except Exception as e:
        # Catch any other unexpected errors
        missing_field_errors.append(f"Error processing item {idx}: {str(e)}")
        continue

# Log any errors encountered
if missing_field_errors:
    print("\nWARNING: Some items in the API response were missing required fields:")
    for error in missing_field_errors:
        print(f"  - {error}")
    print(f"Total errors: {len(missing_field_errors)} out of {len(data)} items")
    
    # Also log to the log file
    log.write("\n=== API Response Field Errors ===\n")
    log.write(f"Some items in the API response were missing required fields:\n")
    for error in missing_field_errors:
        log.write(f"  - {error}\n")
    log.write(f"Total errors: {len(missing_field_errors)} out of {len(data)} items\n\n")

# The duplicate detection logic has been replaced with a field-by-field comparison approach
# which will be applied during the file upload process

# Log duplicate check method
log.write("\n=== Duplicate Check Method ===\n")
log.write("Files are checked for duplicates by comparing:\n")
log.write("1. Drill hole name\n")
log.write("2. Depth from value\n")
log.write("3. Depth to value\n")
log.write("4. Image type (Dry/Wet)\n\n")

print(f"Duplicated IDs logged to: {log_file}")

# %%
def create_drill_hole(accessToken, name, projectId, prospectId):
    """
    Create a drill hole with detailed error handling.
    
    Args:
        accessToken: Authentication token
        name: Drill hole name
        projectId: Project ID
        prospectId: Prospect ID
        
    Returns:
        Response object from the API
    """
    url = f"{api_endpoint}/services/app/DrillHole/Create"

    payload = json.dumps({
        "name": name,
        "rl": 0,
        "maxDepth": 0,
        "projectId": projectId,
        "prospectId": prospectId,
        "isActive": True
    })
    
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Network error when creating drill hole {name}: {str(e)}")
        # Create a mock response to return with error details
        error_response = requests.Response()
        error_response.status_code = 0
        error_response._content = str(e).encode('utf-8')
        error_response.reason = f"Network Error: {type(e).__name__}"
        error_response.url = url
        return error_response

# create_drill_hole(token, "test", 4, 4)

# %%
def upload_image(img_path, projectId, prospectId, holeId, standard_type, start, end, accessToken=None):
    """
    Upload an image to the API with detailed error handling.
    
    Returns:
        tuple: (response, error_details) where error_details is None on success
               or a formatted error string on failure
    """
    url = f"{api_endpoint}/services/app/Image/Create"

    # Get headers without content-type to let requests set the correct multipart boundary
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)
    
    # Remove content-type if present as requests will add the correct one
    if 'Content-Type' in headers:
        del headers['Content-Type']
    
    # Create a multipart form with all fields together
    multipart_form = {
        'Type': (None, '1'),
        'ImageClass': (None, '1'),
        'StandardType': (None, str(standard_type)),
        'ProjectId': (None, str(projectId)),
        'ProspectId': (None, str(prospectId)),
        'HoleId': (None, str(holeId)),
        'image': (os.path.basename(img_path), open(img_path, 'rb'), 'application/octet-stream'),
        'DepthFrom': (None, str(start)),
        'DepthTo': (None, str(end)),
    }
    
    try:
        response = requests.request("POST", url, headers=headers, files=multipart_form)
        
        # If response is not successful, extract and format error details
        if response.status_code != 200:
            error_details = format_error_details(response, url)
            return response, error_details
        
        return response, None
    except Exception as e:
        # Handle request exceptions (network issues, timeouts, etc.)
        error_msg = f"Request failed with exception: {str(e)}"
        return None, error_msg

def format_error_details(response, url):
    """Format detailed error information from a failed API response."""
    error_info = [
        "=== API REQUEST ERROR DETAILS ===",
        f"Status Code: {response.status_code}",
        f"Reason: {response.reason}",
        f"URL: {url}",
        f"Request Method: {response.request.method if response.request else 'Unknown'}",
    ]
    
    # Add request headers (with authentication info redacted)
    if response.request and response.request.headers:
        error_info.append("\nRequest Headers:")
        for key, value in response.request.headers.items():
            if key.lower() in ('authorization', 'cookie', 'api-key'):
                display_value = "[REDACTED]"
            else:
                display_value = value
            error_info.append(f"  {key}: {display_value}")
    
    # Try to parse response JSON for more details
    try:
        error_json = response.json()
        error_info.append("\nResponse JSON:")
        error_info.append(json.dumps(error_json, indent=2))
        
        # Extract specific error messages if available
        if "error" in error_json:
            if "message" in error_json["error"]:
                error_info.append(f"\nError Message: {error_json['error']['message']}")
            if "details" in error_json["error"]:
                error_info.append(f"Error Details: {error_json['error']['details']}")
            if "validationErrors" in error_json["error"]:
                error_info.append("\nValidation Errors:")
                for error in error_json["error"]["validationErrors"]:
                    error_info.append(f"  - {error.get('message', 'Unknown error')}")
    except json.JSONDecodeError as je:
        # Detailed info for JSON decode errors
        error_info.append(f"\nJSON Decode Error: {str(je)}")
        error_info.append(f"Error at position: {je.pos}, line: {je.lineno}, column: {je.colno}")
        error_info.append("\nResponse Text Around Error Position:")
        # Show more context around the error position
        start_pos = max(0, je.pos - 50)
        end_pos = min(len(response.text), je.pos + 50)
        context = response.text[start_pos:end_pos]
        error_info.append(f"...{context}...")
        error_info.append("\nFull Response (first 1000 chars):")
        error_info.append(response.text[:1000] + ("..." if len(response.text) > 1000 else ""))
    except ValueError:
        # If response is not JSON
        error_info.append("\nResponse Text (non-JSON):")
        error_info.append(response.text[:1000] + ("..." if len(response.text) > 1000 else ""))
    except Exception as e:
        error_info.append(f"\nError parsing response: {str(e)}")
        error_info.append(f"Exception type: {type(e).__name__}")
    
    # Add response headers for debugging
    error_info.append("\nResponse Headers:")
    for key, value in response.headers.items():
        error_info.append(f"  {key}: {value}")
    
    # Add content type information
    content_type = response.headers.get('Content-Type', 'Unknown')
    error_info.append(f"\nContent Type: {content_type}")
    
    return "\n".join(error_info)

# %%
# Create all drill holes
list_of_drill_holes = {}
print("Creating drill holes...")
log.write("\n=== Drill Hole Creation Log ===\n")

for name in set(hole_names):
   try:
       response = create_drill_hole(token, name, projectId, prospectId)
       
       # Check if the response was successful
       if response.status_code != 200:
           error_details = format_error_details(response, f"{api_endpoint}/services/app/DrillHole/Create")
           print(f"Failed to create drill hole {name}:")
           print(error_details)
           log.write(f"[{datetime.now()}] Failed to create drill hole {name}:\n{error_details}\n")
           continue
       
       # Try to extract the ID from the JSON response
       try:
           holeId = response.json()["result"]["id"]
           list_of_drill_holes[name] = holeId
           print(f"Created drill hole: {name} with ID: {holeId}")
           log.write(f"[{datetime.now()}] Created drill hole: {name} with ID: {holeId}\n")
       except (json.JSONDecodeError, KeyError) as je:
           print(f"Error parsing response for drill hole {name}: {str(je)}")
           log_response_details(response, log)
           log.write(f"[{datetime.now()}] Error parsing response for drill hole {name}: {str(je)}\n")
   except Exception as ex:
       print(f"Exception when creating drill hole {name}: {str(ex)}")
       log.write(f"[{datetime.now()}] Exception when creating drill hole {name}: {str(ex)}\n")

# %%
e = 0
total_files = len(df)
uploaded_count = 0
skipped_count = 0
failed_uploads = [] # List to store information about failed uploads

# Start file upload section in log
log.write("\n=== File Upload Log ===\n")

print("\nStarting file uploads...")
for index, row in df.iterrows():
    try:
        hole_name = row['HoleID']
        img_path = row['Full Path']
        start = row['BoxFrom']
        end = row['BoxTo']
        image_type = row['ImageType']
        image_type = str(image_type).strip()
        standard_type = 1 if image_type.lower() == "dry" else 2
        # Check if file is already uploaded using field-by-field comparison
        is_duplicate = False
        for idx, uploaded_file in enumerate(uploaded_files_data):
            try:
                # Ensure we're comparing the same data types
                hole_name_match = uploaded_file['hole_name'] == hole_name
                
                # Convert string values to float for depth comparison if needed
                try:
                    api_depth_from = float(uploaded_file['depth_from'])
                    api_depth_to = float(uploaded_file['depth_to'])
                    file_depth_from = float(start)
                    file_depth_to = float(end)
                    
                    depth_from_match = abs(api_depth_from - file_depth_from) < 0.0001
                    depth_to_match = abs(api_depth_to - file_depth_to) < 0.0001
                except (ValueError, TypeError):
                    # If we can't convert to float, do exact string comparison
                    print(f"Warning: Could not convert depth values to float for comparison at index {idx}.")
                    depth_from_match = str(uploaded_file['depth_from']) == str(start)
                    depth_to_match = str(uploaded_file['depth_to']) == str(end)
                
                # Convert standard_type to integers for comparison if needed
                try:
                    api_standard_type = int(uploaded_file['standard_type'])
                    file_standard_type = int(standard_type)
                    standard_type_match = api_standard_type == file_standard_type
                except (ValueError, TypeError):
                    # If we can't convert to int, do exact string comparison
                    print(f"Warning: Could not convert standard_type values to int for comparison at index {idx}.")
                    standard_type_match = str(uploaded_file['standard_type']) == str(standard_type)
                    
                # Check if all four fields match
                if hole_name_match and depth_from_match and depth_to_match and standard_type_match:
                    is_duplicate = True
                    break
                    
            except Exception as e:
                # Log any unexpected errors during comparison
                print(f"Error comparing file with uploaded data at index {idx}: {str(e)}")
                log.write(f"[{datetime.now()}] Error comparing file with uploaded data at index {idx}: {str(e)}\n")
                continue  # Continue to the next item
                
        if is_duplicate:
            print(f"File already uploaded (matching hole, depth range and image type): {img_path}. Skipped.")
            skipped_count += 1
            log.write(f"[{datetime.now()}] File already uploaded (matching hole, depth range and image type): {img_path}. Skipped.\n")
            continue
        # Log the upload attempt
        print(f"Going to upload: {os.path.basename(img_path)}, Raw Image Type: '{image_type}', StandardType: {standard_type}")
        log.write(f"[{datetime.now()}] Going to upload: {os.path.basename(img_path)}, Raw Image Type: '{image_type}', StandardType: {standard_type}\n")
        
        # Perform the upload
        response, error_details = upload_image(img_path, projectId, prospectId, list_of_drill_holes[hole_name], standard_type, start, end, token )
        
        if response is not None and response.status_code == 200:
            uploaded_count += 1
            print(f"+ Successfully uploaded {os.path.basename(img_path)} ({uploaded_count}/{total_files})")
            log.write(f"[{datetime.now()}] Successfully uploaded {os.path.basename(img_path)}\n")
        else:
            e += 1
            # Pretty print the detailed error information
            if error_details:
                print(f"\n- ERROR uploading {os.path.basename(img_path)} for {hole_name}:")
                print(error_details)
                print("-" * 80)  # Add a separator line for better readability
            else:
                print(f"Error uploading {os.path.basename(img_path)} for {hole_name}")
                
                # If we have a response but no error details, try to get more diagnostic info
                if response:
                    try:
                        # Log response details to help diagnose the issue
                        details = log_response_details(response, log)
                        print("Additional diagnostics logged to file")
                    except Exception as log_ex:
                        print(f"Failed to log response details: {str(log_ex)}")
            
            # Log the error details
            log.write(f"[{datetime.now()}] Error uploading {os.path.basename(img_path)} for {hole_name}\n")
            if error_details:
                log.write(f"Error details:\n{error_details}\n")
            
            # Add to failed uploads list with the same format as file_summary.csv plus error details
            failed_uploads.append({
                'HoleID': hole_name,
                'BoxFrom': start,
                'BoxTo': end,
                'Range': end - start,
                'ImageType': image_type,
                'Original Filename': os.path.basename(img_path),
                'Full Path': img_path,
                'Error': error_details[:100] + '...' if error_details and len(error_details) > 100 else (error_details or f"Status code: {response.status_code if response else 'No response'}")
            })
            
            # Still log error details to the log file, but separately
            if error_details:
                log.write(f"Error details: {error_details}\n")
            else:
                status_code = response.status_code if response else "No response"
                log.write(f"API Error: Status code {status_code}\n")
    except Exception as ex:
        e += 1
        print(f"Error when uploading images for {hole_name}: {str(ex)}")
        log.write(f"[{datetime.now()}] Error when uploading images for {hole_name}: {str(ex)}\n")
        
        # Add to failed uploads list with the same format as file_summary.csv
        failed_uploads.append({
            'HoleID': hole_name,
            'BoxFrom': start,
            'BoxTo': end,
            'Range': end - start,
            'ImageType': image_type,
            'Original Filename': os.path.basename(img_path),
            'Full Path': img_path,
            'Error': f"Exception: {str(ex)[:100]}..." if len(str(ex)) > 100 else f"Exception: {str(ex)}"
        })
        
        # Log detailed exception information
        log.write(f"Exception details: {str(ex)}\n")
        log.write(f"Exception type: {type(ex).__name__}\n")
        
        # Include traceback if available
        import traceback
        tb_str = traceback.format_exc()
        log.write(f"Traceback:\n{tb_str}\n")

print(f"\nUpload complete. Successfully uploaded {uploaded_count}/{total_files} files.")
print(f"Skipped {skipped_count} files already uploaded.")
print(f"Failed to upload {len(failed_uploads)} files.")
log.write(f"\nUpload complete. Successfully uploaded {uploaded_count}/{total_files} files.\n")
log.write(f"Skipped {skipped_count} files already uploaded.\n")
log.write(f"Failed to upload {len(failed_uploads)} files.\n")

# Create failed uploads CSV file if there are any failures
if failed_uploads:
    fail_file = os.path.join(fail_dir, f"file_summary_fail_{timestamp}.csv")
    print(f"Writing failed uploads to: {fail_file}")
    fail_df = pd.DataFrame(failed_uploads)
    # Save the fail file with the same format as file_summary.csv for reuse in future uploads
    fail_df.to_csv(fail_file, index=False)
    print(f"Failed uploads saved to: {fail_file} (same format as file_summary.csv for reuse)")

# Log summary section
log.write("\n=== Final Summary ===\n")
log.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
log.write(f"Total files processed: {total_files}\n")
log.write(f"Successfully uploaded: {uploaded_count}\n")
log.write(f"Skipped (already uploaded): {skipped_count}\n")
log.write(f"Failed uploads: {len(failed_uploads)}\n")

# Add Data Quality Summary
log.write("\n=== Data Quality Summary ===\n")
if missing_field_errors:
    log.write(f"API Response had {len(missing_field_errors)} items with missing fields out of {len(data)} total items.\n")
    log.write(f"This could affect duplicate detection accuracy. See '=== API Response Field Errors ===' section above for details.\n")
else:
    log.write("API Response data quality was good - no missing fields detected.\n")

# Close the log file
log.close()
print(f"All processing logged to: {log_file}")



