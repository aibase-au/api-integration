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
df = pd.read_csv('FilesToUpload.csv')

hole_names = df['Folder'].values
depth_from = df["BoxFrom"].values
depth_to = df["BoxTo"].values
conditions = df["Condition"].values
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
log = open(log_file, 'w')

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
    log.write(f"   Drill Hole: {row['Folder']}\n")
    log.write(f"   Condition: {row['Condition']}\n")
    log.write(f"   Full Path: {row['Full Path']}\n")
    log.write(f"   Depth Range: {row['BoxFrom']} - {row['BoxTo']}\n")
    log.write("\n")

log.write("\n=== Processing Summary ===\n")
log.write(f"Total Files: {len(df)}\n")
log.write(f"Total Drill Holes: {len(df['Folder'].unique())}\n")
log.write(f"Unique Conditions: {set(df['Condition'].values)}\n\n")

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

# Log duplicated IDs
log.write("\n=== Duplicated IDs ===\n")
if all_duplicated_id:
    for dup_id in all_duplicated_id:
        log.write(f"{dup_id},\n")
else:
    log.write("No duplicated IDs found.\n")

print(f"Duplicated IDs logged to: {log_file}")

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
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)

    response = requests.request("POST", url, headers=headers, data=payload)

    return response

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
        f"URL: {url}",
    ]
    
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
    except ValueError:
        # If response is not JSON
        error_info.append("\nResponse Text (non-JSON):")
        error_info.append(response.text[:500] + ("..." if len(response.text) > 500 else ""))
    except Exception as e:
        error_info.append(f"\nError parsing response: {str(e)}")
    
    # Add response headers for debugging
    error_info.append("\nResponse Headers:")
    for key, value in response.headers.items():
        error_info.append(f"  {key}: {value}")
    
    return "\n".join(error_info)

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
failed_uploads = [] # List to store information about failed uploads

# Start file upload section in log
log.write("\n=== File Upload Log ===\n")

print("\nStarting file uploads...")
for index, row in df.iterrows():
    try:
        hole_name = row['Folder']
        img_path = row['Full Path']
        start = row['BoxFrom']
        end = row['BoxTo']
        c = row['Condition']
        c = str(c).strip()
        standard_type = 1 if c.lower() == "dry" else 2
        name = f"{hole_name}_{str(start).rstrip('0').rstrip('.')}_{str(end).rstrip('0').rstrip('.')}_{standard_type}"
        if name in uploaded_files:
            print(f"File already uploaded: {img_path}. Skipped.")
            skipped_count += 1
            log.write(f"[{datetime.now()}] File already uploaded: {img_path}. Skipped.\n")
            continue
        # Log the upload attempt
        print(f"Going to upload: {os.path.basename(img_path)}, Raw Condition: '{c}', StandardType: {standard_type}")
        log.write(f"[{datetime.now()}] Going to upload: {os.path.basename(img_path)}, Raw Condition: '{c}', StandardType: {standard_type}\n")
        
        # Perform the upload
        response, error_details = upload_image(img_path, projectId, prospectId, list_of_drill_holes[hole_name], standard_type, start, end, token )
        
        if response is not None and response.status_code == 200:
            uploaded_count += 1
            print(f"Successfully uploaded {os.path.basename(img_path)} ({uploaded_count}/{total_files})")
            log.write(f"[{datetime.now()}] Successfully uploaded {os.path.basename(img_path)}\n")
        else:
            e += 1
            # Pretty print the detailed error information
            if error_details:
                print(f"\nERROR uploading {os.path.basename(img_path)} for {name}:")
                print(error_details)
                print("-" * 80)  # Add a separator line for better readability
            else:
                print(f"Error uploading {os.path.basename(img_path)} for {name}")
            
            # Log the error details
            log.write(f"[{datetime.now()}] Error uploading {os.path.basename(img_path)} for {name}\n")
            if error_details:
                log.write(f"Error details:\n{error_details}\n")
            
            # Add to failed uploads list with the same format as file_summary.csv (without error details)
            failed_uploads.append({
                'Folder': hole_name,
                'BoxFrom': start,
                'BoxTo': end,
                'Range': end - start,
                'Condition': c,
                'Original Filename': os.path.basename(img_path),
                'Full Path': img_path
            })
            
            # Still log error details to the log file, but separately
            if error_details:
                log.write(f"Error details: {error_details}\n")
            else:
                status_code = response.status_code if response else "No response"
                log.write(f"API Error: Status code {status_code}\n")
    except Exception as ex:
        e += 1
        print(f"Error when uploading images for {name}: {str(ex)}")
        log.write(f"[{datetime.now()}] Error when uploading images for {name}: {str(ex)}\n")
        # Add to failed uploads list with the same format as file_summary.csv (without error details)
        failed_uploads.append({
            'Folder': hole_name,
            'BoxFrom': start,
            'BoxTo': end,
            'Range': end - start,
            'Condition': c,
            'Original Filename': os.path.basename(img_path),
            'Full Path': img_path
        })
        
        # Log exception details to the log file
        log.write(f"Exception details: {str(ex)}\n")

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

# Close the log file
log.close()
print(f"All processing logged to: {log_file}")



