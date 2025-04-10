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
debug = True

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

# Create log file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


# Get authentication token
token = authenticate(auth_config)
if token is None and use_credentials:
    print("Authentication failed. Please check your credentials and try again.")
    exit(1)


def get_all_images(projectId, prospectId, accessToken=None):
    url = f"{api_endpoint}/services/app/Image/GetAll?ProjectIds={projectId}&ProspectIds={prospectId}&MaxResultCount=100000"

    payload = {}
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)

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
    headers = get_request_headers(api_key, use_api_key, api_endpoint, accessToken)
    response = requests.request("GET", url, headers=headers, data=payload)

    return response

res = get_all_holes(token)  # token will be None if using API key
data = res.json()['result']['items']
drill_holes = [[x['name'], x['id'], x['drillHoleStatus'], x['elevation'], x['northing'],\
                x['easting'], x['longitude'], x['latitude'], x['dip'], x['azimuth'], x['rl'], x['maxDepth']] for x in data]

import csv

# Specify the output CSV file name
output_csv = f"drill_holes_{timestamp}.csv"

# Write the uploaded_files list to the CSV file
with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Hole Name","ID","drillHoleStatus","elevation","northing","easting","longitude","latitude","dip","azimuth","rl","maxDepth"])  # Add a header row
    for name,id,drillHoleStatus,elevation,northing,easting,longitude,latitude,dip,azimuth,rl,maxDepth in drill_holes:
        writer.writerow([name,id,drillHoleStatus,elevation,northing,easting,longitude,latitude,dip,azimuth,rl,maxDepth])

print(f"Drill holes files saved to {output_csv}")