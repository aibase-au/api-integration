# Drill Core Image Management

This project is a set of Python scripts for managing, uploading, and processing drill core images in the FastGeo system. The scripts help with operations like uploading images, processing batches, retrieving image data, and managing drill hole information.

## Project Overview

The project includes several scripts for different operations:

- `upload_image.py`: Uploads drill core images to the FastGeo API
- `execute_batch.py`: Processes uploaded images through a specific workflow
- `get_image_row.py`: Retrieves row-specific data for images, including OCR text, core outlines, polygon, v.v
- `get_upload_list.py`: Gets lists of uploaded files and drill holes

## Prerequisites

- Python 3.7+
- Required Python packages (listed in requirements section)
- Access to the FastGeo API 
    - API key (RECOMMENDED) 
    - Username/password

## API Documentation

The FastGeo API documentation is available through Postman:
[FastGeo API Documentation](https://documenter.getpostman.com/view/14342098/2sAYJ1m31h)

This documentation covers:
- Authentication methods
- Available endpoints
- Request/response formats
- Example API calls
- Data structures and schemas

Please refer to this documentation for detailed information about the API endpoints used by these scripts.

## Setup Instructions

### 1. Clone the Repository

Clone this repository to your local machine.

### 2. Create a Virtual Environment (Recommended)

```bash
# Create a virtual environment
python -m venv myenv

# Activate the virtual environment
# On Windows
myenv\Scripts\activate
# On macOS/Linux
source myenv/bin/activate
```
### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` File

Create a `.env` file in the project root directory with the following variables:

```
PROJECT_ID=<your_project_id>
PROSPECT_ID=<your_prospect_id>
WORKFLOW_ID=<your_workflow_id>
API_KEY=<your_api_key>
USERNAME=<your_username>
PASSWORD=<your_password>
API_ENDPOINT=https://api-portal1.fastgeo.com.au/api
```

Replace the values with your actual credentials. You can use either API_KEY or USERNAME/PASSWORD for authentication.

## Usage Instructions

### Preparing Data for Upload

Before uploading images, you need to create a CSV file named `file_summary.csv` with the following columns:

- `Folder`: Drill hole name
- `Start Number`: Depth from
- `End Number`: Depth to
- `Condition`: Image condition (e.g., "Dry" or "Wet")
- `Original Filename`: Original filename
- `Full Path`: Full path to the image file

### Uploading Images

Run the upload script to upload images to the FastGeo API:

```bash
python upload_image.py
```

This will:
1. Read the `file_summary.csv` file
2. Create drill holes in the system
3. Upload images for each drill hole
4. Log successes and failures

### Processing Images with a Workflow

After uploading images, you can process them with a workflow:

```bash
python execute_batch.py
```

This will:
1. Get all images for the project and prospect
2. Process each image with the specified workflow
3. Log the results and generate CSV files with successful and failed operations

### Getting Image Row Data

To retrieve row-specific data for images:

```bash
python get_image_row.py
```

This will:
1. Retrieve row data for all images in the project
2. Save the data as CSV files in the logs directory
3. Include OCR text and core outline information

### Getting Upload Lists

To get lists of uploaded files and drill holes:

```bash
python get_upload_list.py
```

This will:
1. Retrieve all uploaded images
2. Check for duplicates
3. Save lists of uploaded files and drill holes as CSV files

## Example Workflow

1. Prepare your `file_summary.csv` file with image information
2. Create a `.env` file with your API credentials
3. Run `upload_image.py` to upload images
4. Run `execute_batch.py` to process the uploaded images
5. Run `get_image_row.py` to retrieve OCR and core outline data
6. Run `get_upload_list.py` to get lists of uploaded files and drill holes

## Sample .env File

```
PROJECT_ID=123
PROSPECT_ID=456
WORKFLOW_ID=789
API_KEY=your_api_key_here
USERNAME=your_username_here
PASSWORD=your_password_here
API_ENDPOINT=https://api-portal1.fastgeo.com.au/api
```

You can use either API_KEY or USERNAME/PASSWORD for authentication.

## Sample file_summary.csv

```csv
Folder,Start Number,End Number,Condition,Original Filename,Full Path
KA-022,168.35,171.15,Dry,KA-022_168.35_171.15_Dry_full.jpg,Platypus Valley/Little River/KA-022/Standard/Original_Dry/KA-022_168.35_171.15_Dry_full.jpg
KA-022,171.15,173.81,Dry,KA-022_171.15_173.81_Dry_full.jpg,Platypus Valley/Little River/KA-022/Standard/Original_Dry/KA-022_171.15_173.81_Dry_full.jpg
```

## Troubleshooting

### Authentication Issues

- Make sure your `.env` file is in the correct location (same directory as the scripts)
- Check that your API credentials are correct
- Verify that you have access to the project and prospect

### Upload Failures

- Check the logs in `logs/upload_image/fail/` for details on failed uploads
- Verify that the image files exist at the paths specified in `file_summary.csv`
- Ensure the image files are in a supported format (JPG, PNG)

### API Connection Issues

- Check your internet connection
- Verify that the API endpoint is correct
- Make sure your API credentials have not expired

## Logs and Output

All scripts create detailed logs in the `logs/` directory:

- Upload logs: `logs/upload_image/logs/`
- Batch processing logs: `logs/execute_batch/logs/`
- Image row data logs: `logs/get_image_row/logs/`

Success and failure details are saved in corresponding subdirectories.