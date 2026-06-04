# Drill Core Image Management

This project is a set of Python scripts for managing, uploading, and processing drill core images in the FastGeo system. The scripts help with operations like uploading images, processing batches, retrieving image data, and managing drill hole information.

## Project Overview

The project includes several scripts for different operations:

- `upload_image.py`: Uploads drill core images to the FastGeo API
- `execute_batch.py`: Processes uploaded images one-by-one through a workflow (`Image/ProcessImage`)
- `batch_process.py`: Runs the full drill-hole batch workflow end-to-end (create → start → poll → fetch OCR / row detail) via the `WorkflowJob` API
- `get_image_row.py`: Retrieves row-specific data for images, including OCR text, core outlines, polygon, v.v
- `get_upload_list.py`: Gets lists of uploaded files and drill holes

### `execute_batch.py` vs `batch_process.py`

| | `execute_batch.py` | `batch_process.py` |
|---|---|---|
| Granularity | One image at a time (`Image/ProcessImage`) | Whole drill hole as a single batch (`WorkflowJob`) |
| Workflow | Fetch images, loop, process each | Create batch → start → poll until done → fetch results |
| Input | `sendtobatch.csv` (hole IDs) | `DRILLHOLE_ID` in `.env` |
| Output | Success/failure CSVs in `logs/` | `detail_by_row.json` (OCR / row detail) |
| Drill-hole context | Per image | Full drill-hole context (recommended for Block OCR) |

Both scripts share the same `.env` and `authentication.py` (API key or username/password). Use `batch_process.py` when OCR or AI workflows need full drill-hole context (recommended for Block OCR); use `execute_batch.py` for selective, per-image processing.

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

# Additional variables used by batch_process.py
DRILLHOLE_ID=<your_drillhole_id>
IMAGE_TYPE_ID=<your_image_type_id>
```

Replace the values with your actual credentials. You can use either API_KEY or USERNAME/PASSWORD for authentication.

`DRILLHOLE_ID` and `IMAGE_TYPE_ID` are only required for `batch_process.py`; the other scripts ignore them. See [Running a Full Drill-Hole Batch](#running-a-full-drill-hole-batch) for the optional variables that script also supports.

## Usage Instructions

### Preparing Data for Upload

Before uploading images, you need to create a CSV file named `filestoupload.csv` with the following columns:

- `HoleID`: Drill hole name
- `BoxFrom`: Depth from
- `BoxTo`: Depth to
- `ImageType`: Image condition (e.g., "Dry" or "Wet")
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

### Running a Full Drill-Hole Batch

To run an entire drill hole through a workflow as a single batch job (create → start → poll → fetch results), use `batch_process.py`. Like the other scripts, it reads its configuration from the `.env` file and authenticates with either `API_KEY` or `USERNAME`/`PASSWORD`.

Add `DRILLHOLE_ID` and `IMAGE_TYPE_ID` to your `.env` (in addition to `PROJECT_ID`, `PROSPECT_ID`, `WORKFLOW_ID`, and your credentials), then run:

```bash
python batch_process_by_drillhole.py
```

This will:
1. Resolve the drill hole name via `DrillHole/Get`
2. Create a batch with `WorkflowJob/Create` (status NotStart)
3. Start processing with `WorkflowJob/RerunJob`
4. Poll `WorkflowJob/Get` every few seconds until a terminal status (Completed, Failed, or Canceled)
5. On success, call `Image/GetDetailByRow` and save the response to `detail_by_row.json`

**Required API key roles:** ProcessBatch, GetDrillhole, GetImageRowData

#### Required `.env` variables

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | Project ID. |
| `PROSPECT_ID` | Prospect ID. |
| `WORKFLOW_ID` | Workflow ID (e.g. Block OCR workflow). |
| `DRILLHOLE_ID` | Drill hole ID to process. |
| `IMAGE_TYPE_ID` | Image type ID to include in the batch. |
| `API_KEY` *or* `USERNAME`/`PASSWORD` | Authentication (same as the other scripts). |
| `API_ENDPOINT` | API root URL (defaults to production). |

#### Optional `.env` variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_SUBTYPE_ID` | — | Filter batch to a specific image subtype. |
| `IMAGE_CATEGORY` | — | Image category filter. |
| `IS_ONLY_NEW_IMAGES` | `false` | When `true`/`1`/`yes`, process only new images. |
| `POLL_INTERVAL_SEC` | `5` | Seconds between status polls. |
| `OUTPUT_FILE` | `detail_by_row.json` | Path for the GetDetailByRow JSON output. |
| `BATCH_NAME` | auto | Override batch name (skips drill hole lookup). |
| `DRILLHOLE_NAME` | auto | Use `Process drillhole {name}` without calling DrillHole/Get. |

#### Job status codes

| Status | Value | Meaning |
|--------|-------|---------|
| NotStart | 1 | Batch created, not yet running. |
| Running | 2 | Processing in progress. |
| Completed | 3 | Success — script fetches GetDetailByRow. |
| Failed | 4 | Batch failed — check `failedImageIds` in the job response. |
| Canceled | 5 | Batch was canceled. |

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
1. Prepare your `filestoupload.csv` file with image information
1. Prepare your `file_summary.csv` file with image information
2. Create a `.env` file with your API credentials
3. Run `upload_image.py` to upload images
4. Process the uploaded images, either:
   - Run `execute_batch.py` for per-image processing, or
   - Run `batch_process.py` to run a full drill hole as a single batch job
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

# Used by batch_process.py
DRILLHOLE_ID=626
IMAGE_TYPE_ID=91
```

You can use either API_KEY or USERNAME/PASSWORD for authentication.

## Sample filestoupload.csv

```csv
HoleID,BoxFrom,BoxTo,ImageType,Original Filename,Full Path
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
- Verify that the image files exist at the paths specified in `filestoupload.csv`
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

`batch_process.py` does not write to `logs/`; it prints progress to the console and saves the final OCR / row detail to `detail_by_row.json` (or the path set in `OUTPUT_FILE`). This output may contain project / drill hole data, so keep it out of version control.