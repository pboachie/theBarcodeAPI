import pytest
import asyncio
import json
from io import BytesIO
from typing import List, Optional, Dict, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, Request, Depends
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Application components to test or mock
from app.api.bulk import router as bulk_router
from app.schemas import (
    UserData,
    BulkUploadResponse,
    BulkFileMetadata,
    JobStatusResponse,
    JobStatusEnum,
    BarcodeResult,
)
from app.dependencies import get_current_user, get_redis_manager
from app.redis_manager import RedisManager
from app.batch_processor import MultiLevelBatchProcessor # Assuming this is the correct import path


# --- Test App Setup ---
app = FastAPI()
app.include_router(bulk_router, prefix="/api/bulk")

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_user_data() -> UserData:
    return UserData(
        id="test_user_123",
        username="testuser",
        tier="premium",
        requests_today=0,
        remaining_requests=1000,
        # last_request and last_reset can be None or datetime objects
    )

@pytest.fixture
def mock_redis_manager_fixture():
    mock_redis = AsyncMock(spec=RedisManager) # Use AsyncMock if RedisManager methods are async
    mock_redis.redis = AsyncMock() # Mock the actual redis client attribute within RedisManager

    # Mock specific redis client methods if needed by the endpoint directly or via RedisManager methods
    mock_redis.redis.set = AsyncMock(return_value=True)
    mock_redis.redis.get = AsyncMock(return_value=None)
    mock_redis.redis.hset = AsyncMock(return_value=1)
    mock_redis.redis.hgetall = AsyncMock(return_value={})
    mock_redis.redis.lrange = AsyncMock(return_value=[])
    mock_redis.redis.hincrby = AsyncMock(return_value=1)
    mock_redis.redis.rpush = AsyncMock(return_value=1)
    # Add other methods as needed

    return mock_redis

@pytest.fixture
def mock_batch_processor_fixture():
    mock_processor = AsyncMock(spec=MultiLevelBatchProcessor)
    mock_processor.add_to_batch = AsyncMock(return_value=None) # Example, adjust as needed
    return mock_processor


@pytest.fixture
def client(mock_user_data, mock_redis_manager_fixture, mock_batch_processor_fixture):

    # This is where we override dependencies for the test app
    app.dependency_overrides[get_current_user] = lambda: mock_user_data
    app.dependency_overrides[get_redis_manager] = lambda: mock_redis_manager_fixture

    # How to mock request.app.state.batch_processor?
    # We can patch it during the test or ensure our app instance used by TestClient has it.
    # For TestClient, it's tricky to set app.state directly for dependencies.
    # A common way is to have a dependency that provides it, or patch where it's accessed.
    # Let's assume for now that the router will try to access it via request.app.state.
    # We'll handle this by patching `request.app.state` or ensuring the app has this state.

    # Create a new app instance for each test to ensure clean state
    test_app = FastAPI()
    test_app.include_router(bulk_router, prefix="/api/bulk") # Assuming /api/bulk is the prefix in main app

    test_app.dependency_overrides[get_current_user] = lambda: mock_user_data
    test_app.dependency_overrides[get_redis_manager] = lambda: mock_redis_manager_fixture

    # Set the batch_processor on the app state for this test_app instance
    # This is crucial for the `request.app.state.batch_processor` access pattern
    test_app.state.batch_processor = mock_batch_processor_fixture

    with TestClient(test_app) as c:
        yield c

    app.dependency_overrides = {} # Clean up overrides


# --- Helper Functions ---
def create_mock_upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content), content_type=content_type)

# --- Basic Upload Tests ---

def test_upload_no_files(client: TestClient):
    response = client.post("/api/bulk/generate_upload", files=[]) # Sending an empty list for 'files'
    assert response.status_code == 400 # Should be 422 if no files means empty body, or 400 if files=[]
    # The exact error code might depend on FastAPI's handling of empty File(...) lists.
    # If File(...) means at least one file, it will be 422 Unprocessable Entity.
    # If the endpoint logic checks `if not files:`, it's a 400.
    # Based on current implementation, it's a 400.
    assert "No files uploaded" in response.json()["detail"]

def test_upload_too_many_files(client: TestClient):
    mock_files = []
    for i in range(6):
        mock_files.append(
            ("files", (f"test{i}.txt", BytesIO(b"test data"), "text/plain"))
        )
    response = client.post("/api/bulk/generate_upload", files=mock_files)
    assert response.status_code == 413
    assert "Too many files" in response.json()["detail"]

def test_upload_invalid_file_type(client: TestClient, mock_redis_manager_fixture: MagicMock):
    # Even though it's an invalid type, the job itself should be created,
    # but the file within files_processed should have a "Failed" status.

    files_data = [
        ("files", ("image.jpg", BytesIO(b"fakeimagedata"), "image/jpeg"))
    ]
    response = client.post("/api/bulk/generate_upload", files=files_data)

    assert response.status_code == 200 # The overall request is accepted
    json_response = response.json()

    assert "job_id" in json_response
    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "image.jpg"
    assert file_meta["status"] == "Failed"
    assert "Invalid file type" in file_meta["message"]

    # Verify that Redis was called to set the job data, including the failed file
    # The structure of what's stored in Redis for the job:
    # job_id -> {"status": PENDING, "files": [file_meta_dict], ...}

    # Get the last call to redis.set (assuming it's the one for the job_id)
    # This is a bit fragile if other set calls happen. A more robust way is to inspect args.
    # For this simple case, let's assume the last call to set is the one we want.

    # We need to check the arguments of the `set` call on the *mocked* redis client
    # which is mock_redis_manager_fixture.redis.set

    # Assert that set was called (at least once for the job)
    mock_redis_manager_fixture.redis.set.assert_called()

    # Get all calls to the mock
    # calls = mock_redis_manager_fixture.redis.set.call_args_list
    # Check the last call
    # last_call_args = calls[-1][0] # Arguments of the last call
    # job_key_in_redis = last_call_args[0]
    # job_data_in_redis_json = last_call_args[1]
    # job_data_in_redis = json.loads(job_data_in_redis_json)

    # assert job_key_in_redis == f"job:{json_response['job_id']}"
    # assert len(job_data_in_redis["files"]) == 1
    # assert job_data_in_redis["files"][0]["filename"] == "image.jpg"
    # assert job_data_in_redis["files"][0]["status"] == "Failed"

# More tests will be added here...
# Test successful TXT upload
# Test successful CSV upload
# Test successful XLSX upload
# Test CSV/XLSX missing 'data' column

# --- Job Status Tests ---
# Test job not found
# Test unauthorized access
# Test pending status
# Test processing status
# Test completed status
# Test failed status

# To run these tests:
# Ensure pytest and pytest-asyncio are installed.
# Run `pytest` in the terminal from the root of your project or the `tests` directory.
# You might need to adjust PYTHONPATH if app modules are not found.
# Example: PYTHONPATH=. pytest app/tests/test_bulk_api.py

# Note on openpyxl for .xlsx:
# If testing .xlsx, ensure openpyxl is installed in your test environment.
# (It's in barcodeApi/requirements.txt, so should be fine if env is set up from that)

# Note on mocking request.app.state.batch_processor:
# The client fixture now sets app.state.batch_processor directly on the test_app instance.
# This makes it available via request.app.state.batch_processor in the route handlers.
# This is a common pattern for testing stateful parts of an application with TestClient.
# The key is that the TestClient uses the `test_app` instance we configured.
# The original `app` is only used for initial router inclusion and then discarded for client use.
# This ensures that each test run gets a fresh app state if needed, or specific state.
# We also clear app.dependency_overrides after each test using the client fixture.
python
import pytest
import asyncio
import json
from io import BytesIO
from typing import List, Optional, Dict, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, Request, Depends
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Application components to test or mock
from app.api.bulk import router as bulk_router
from app.schemas import (
    UserData,
    BulkUploadResponse,
    BulkFileMetadata,
    JobStatusResponse,
    JobStatusEnum,
    BarcodeResult,
)
from app.dependencies import get_current_user, get_redis_manager
from app.redis_manager import RedisManager
from app.batch_processor import MultiLevelBatchProcessor # Assuming this is the correct import path


# --- Test App Setup ---
# This app instance is primarily for TestClient to discover routes.
# We create a new app instance within the client fixture for cleaner state management per test.
main_app_for_routes = FastAPI()
main_app_for_routes.include_router(bulk_router, prefix="/api/bulk")


# --- Mocks and Fixtures ---

@pytest.fixture
def mock_user_data() -> UserData:
    return UserData(
        id="test_user_123",
        username="testuser",
        tier="premium",
        requests_today=0,
        remaining_requests=1000,
        # last_request and last_reset can be None or datetime objects
    )

@pytest.fixture
def mock_redis_manager_fixture():
    # Using MagicMock for synchronous methods if RedisManager is not fully async
    # If it is fully async, AsyncMock is appropriate.
    # For this example, assuming RedisManager might have sync parts or direct redis calls.
    mock_redis_mgr = MagicMock(spec=RedisManager)
    mock_redis_mgr.redis = AsyncMock() # The 'redis' attribute (actual client) should be AsyncMock

    mock_redis_mgr.redis.set = AsyncMock(return_value=True)
    mock_redis_mgr.redis.get = AsyncMock(return_value=None) # Default to job not found
    mock_redis_mgr.redis.hset = AsyncMock(return_value=1)
    mock_redis_mgr.redis.hgetall = AsyncMock(return_value={}) # Default to empty hash
    mock_redis_mgr.redis.lrange = AsyncMock(return_value=[]) # Default to empty list for results
    mock_redis_mgr.redis.hincrby = AsyncMock(return_value=1)
    mock_redis_mgr.redis.rpush = AsyncMock(return_value=1) # For adding to results list
    mock_redis_mgr.redis.exists = AsyncMock(return_value=0) # Default to key not existing
    # Add other specific redis client methods as needed by your RedisManager's implementation

    return mock_redis_mgr

@pytest.fixture
def mock_batch_processor_fixture():
    mock_processor = AsyncMock(spec=MultiLevelBatchProcessor)
    mock_processor.add_to_batch = AsyncMock(return_value=None)
    return mock_processor


@pytest.fixture
def client(mock_user_data, mock_redis_manager_fixture, mock_batch_processor_fixture):
    # Create a new app instance for each test to ensure clean state and proper dependency overrides
    test_app = FastAPI()
    test_app.include_router(main_app_for_routes.router, prefix="/api/bulk") # Use router from pre-configured app

    # Override dependencies for this specific test_app instance
    test_app.dependency_overrides[get_current_user] = lambda: mock_user_data
    test_app.dependency_overrides[get_redis_manager] = lambda: mock_redis_manager_fixture

    # Set the batch_processor on the app state for this test_app instance
    test_app.state.batch_processor = mock_batch_processor_fixture

    with TestClient(test_app) as c:
        yield c

    # Clean up overrides from the test_app instance (though it's local to this fixture)
    test_app.dependency_overrides = {}


# --- Helper Functions ---
def create_mock_upload_file_tuple(filename: str, content: bytes, content_type: str) -> tuple:
    # TestClient expects files as a list of tuples: (name, file_tuple)
    # file_tuple: (filename, file_object, content_type)
    return ("files", (filename, BytesIO(content), content_type))

# --- Basic Upload Tests ---

def test_upload_no_files(client: TestClient):
    # For `files: List[UploadFile] = File(...)`, if you send an empty list or no 'files' field,
    # FastAPI should return a 422 if the field is mandatory.
    # However, the endpoint has `if not files:` which would be a 400 if an empty list is passed.
    # If the "files" key is missing from the multipart form, it's a 422.
    # Sending `files=[]` in `client.post` is not how TestClient handles empty file lists for `File(...)`.
    # It's better to send no `files` parameter or an empty dictionary for `files`.
    response = client.post("/api/bulk/generate_upload") # No files data sent
    assert response.status_code == 422 # FastAPI's validation for missing File(...)
    # If you want to test the `if not files:` logic, you'd need to construct the request carefully
    # or adjust the endpoint to allow an optional list. For now, 422 is expected for missing field.

def test_upload_too_many_files(client: TestClient):
    mock_files_payload = []
    for i in range(6):
        mock_files_payload.append(
            create_mock_upload_file_tuple(f"test{i}.txt", b"test data", "text/plain")
        )
    response = client.post("/api/bulk/generate_upload", files=mock_files_payload)
    assert response.status_code == 413
    assert "Too many files" in response.json()["detail"]

def test_upload_invalid_file_type(client: TestClient, mock_redis_manager_fixture: MagicMock):
    files_payload = [
        create_mock_upload_file_tuple("image.jpg", b"fakeimagedata", "image/jpeg")
    ]
    response = client.post("/api/bulk/generate_upload", files=files_payload)

    assert response.status_code == 200
    json_response = response.json()

    assert "job_id" in json_response
    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "image.jpg"
    assert file_meta["status"] == "Failed"
    assert "Invalid file type" in file_meta["message"]

    # Verify Redis was called to store the initial job data
    # The key should be job_id, value should be a JSON string of the job data
    # We check the call to `set` on the mocked redis instance.
    mock_redis_manager_fixture.redis.set.assert_called_once()
    args, _ = mock_redis_manager_fixture.redis.set.call_args
    assert args[0] == f"job:{json_response['job_id']}" # Check key
    stored_job_data = json.loads(args[1]) # Check value
    assert stored_job_data["status"] == JobStatusEnum.PENDING.value
    assert len(stored_job_data["files"]) == 1
    assert stored_job_data["files"][0]["filename"] == "image.jpg"
    assert stored_job_data["files"][0]["status"] == "Failed"

def test_upload_successful_txt(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_batch_processor_fixture: AsyncMock, mock_user_data: UserData):
    txt_content = b"data1\ndata2\n\ndata3" # Includes an empty line
    files_payload = [
        create_mock_upload_file_tuple("test.txt", txt_content, "text/plain")
    ]

    response = client.post("/api/bulk/generate_upload", files=files_payload)

    assert response.status_code == 200
    json_response = response.json()
    job_id = json_response["job_id"]
    assert job_id is not None

    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "test.txt"
    assert file_meta["status"] == "Uploaded" # Initial status after parsing before batch processing fully confirms
    assert file_meta["item_count"] == 3 # data1, data2, data3
    assert "File processed for task creation" in file_meta["message"]

    # Verify Redis calls
    # 1. Job data set
    # Call args for job set: (key, job_data_json_string)
    job_set_call = next(c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}"))
    assert job_set_call[0][0] == f"job:{job_id}"
    stored_job_data = json.loads(job_set_call[0][1])
    assert stored_job_data["status"] == JobStatusEnum.PENDING.value
    assert stored_job_data["total_items"] == 3
    assert stored_job_data["user_id"] == mock_user_data.id
    assert len(stored_job_data["files"]) == 1
    assert stored_job_data["files"][0]["filename"] == "test.txt"

    # 2. Task data set (3 tasks from the TXT file)
    # We expect 3 calls to set for the tasks, plus one for the job itself.
    task_set_calls = [c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}:task:")]
    assert len(task_set_calls) == 3

    expected_task_data = ["data1", "data2", "data3"]
    for i, call_args in enumerate(task_set_calls):
        task_key = call_args[0][0]
        task_data_json = call_args[0][1]
        task_data = json.loads(task_data_json)
        assert task_data["data"] == expected_task_data[i]
        assert task_data["status"] == "PENDING"
        assert task_data["original_filename"] == "test.txt"
        assert task_data["job_id"] == job_id
        assert "task_id" in task_data
        # Check default options for TXT
        assert task_data["options"]["format"] == "code128"


    # Verify batch processor calls
    assert mock_batch_processor_fixture.add_to_batch.call_count == 3
    batch_calls = mock_batch_processor_fixture.add_to_batch.call_args_list

    for i, call in enumerate(batch_calls):
        args, kwargs = call
        operation_name = args[0]
        task_payload = args[1]
        priority = kwargs.get("priority")

        assert operation_name == "generate_barcode"
        assert task_payload["data"] == expected_task_data[i]
        assert task_payload["job_id"] == job_id
        assert task_payload["original_filename"] == "test.txt"
        assert priority == "MEDIUM"

def test_upload_successful_csv(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_batch_processor_fixture: AsyncMock, mock_user_data: UserData):
    # CSV content: data,filename,format,width
    csv_content = (
        b"data,filename,format,width\n"
        b"csv_data1,barcode1.png,qr,300\n"
        b"csv_data2,,code128,\n"  # Missing filename, missing width, format specified
        b",,\n" # Empty line
        b"csv_data3,barcode3.jpg,ean13,250"
    ).decode('utf-8') # Simulate text file from frontend for pandas

    files_payload = [
        create_mock_upload_file_tuple("test.csv", csv_content.encode('utf-8'), "text/csv")
    ]

    response = client.post("/api/bulk/generate_upload", files=files_payload)

    assert response.status_code == 200
    json_response = response.json()
    job_id = json_response["job_id"]
    assert job_id is not None

    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "test.csv"
    assert file_meta["status"] == "Uploaded"
    assert file_meta["item_count"] == 3 # csv_data1, csv_data2, csv_data3

    # Verify Redis calls
    job_set_call = next(c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}"))
    assert job_set_call[0][0] == f"job:{job_id}"
    stored_job_data = json.loads(job_set_call[0][1])
    assert stored_job_data["total_items"] == 3

    task_set_calls = [c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}:task:")]
    assert len(task_set_calls) == 3

    expected_tasks_details = [
        {"data": "csv_data1", "output_filename": "barcode1.png", "options": {"format": "qr", "width": 300, "image_format": "PNG", "height": 100}}, # Assuming PNG default if not specified, height default
        {"data": "csv_data2", "output_filename": None, "options": {"format": "code128", "image_format": "PNG", "width": 200, "height": 100}}, # Defaults for filename, width, height
        {"data": "csv_data3", "output_filename": "barcode3.jpg", "options": {"format": "ean13", "width": 250, "image_format": "JPEG", "height": 100}}, # image_format derived from filename
    ]

    for i, call_args in enumerate(task_set_calls):
        task_data = json.loads(call_args[0][1])
        expected = expected_tasks_details[i]
        assert task_data["data"] == expected["data"]
        # For output_filename, if None, it might be generated as task_id.png or similar.
        # The current test setup in bulk.py uses task_id + inferred extension if filename is None.
        # For simplicity here, we'll check if it contains the core part or if it's None as expected from direct CSV.
        if expected["output_filename"] is None:
            assert task_data["output_filename"].startswith(task_data["task_id"]) # e.g. task_id.png
            assert task_data["output_filename"].endswith(f".{expected['options']['image_format'].lower()}")
        else:
            assert task_data["output_filename"] == expected["output_filename"]

        assert task_data["options"]["format"] == expected["options"]["format"]
        assert task_data["options"]["width"] == expected["options"].get("width", 200) # Check against default if not in expected
        assert task_data["options"]["image_format"] == expected["options"].get("image_format", "PNG")


    # Verify batch processor calls
    assert mock_batch_processor_fixture.add_to_batch.call_count == 3
    batch_calls = mock_batch_processor_fixture.add_to_batch.call_args_list
    for i, call in enumerate(batch_calls):
        task_payload = call[0][1] # Second argument of the call
        expected = expected_tasks_details[i]
        assert task_payload["data"] == expected["data"]
        assert task_payload["job_id"] == job_id
        if expected["output_filename"] is None:
             assert task_payload["output_filename"].startswith(task_payload["task_id"])
        else:
            assert task_payload["output_filename"] == expected["output_filename"]
        assert task_payload["options"]["format"] == expected["options"]["format"]

def test_upload_successful_xlsx(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_batch_processor_fixture: AsyncMock, mock_user_data: UserData):
    # Create an in-memory XLSX file
    df = pd.DataFrame([
        {"data": "xlsx_data1", "filename": "barcode_excel1.png", "format": "datamatrix", "width": 250, "height": 250},
        {"data": "xlsx_data2", "filename": None, "format": "code128", "width": None, "height": 150}, # No filename, no width
        {"data": "xlsx_data3", "filename": "barcode_excel3.gif", "format": None, "width": 400} # No format, GIF output
    ])
    xlsx_io = BytesIO()
    with pd.ExcelWriter(xlsx_io, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    xlsx_io.seek(0)

    files_payload = [
        create_mock_upload_file_tuple("test.xlsx", xlsx_io.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    ]

    response = client.post("/api/bulk/generate_upload", files=files_payload)

    assert response.status_code == 200
    json_response = response.json()
    job_id = json_response["job_id"]
    assert job_id is not None

    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "test.xlsx"
    assert file_meta["status"] == "Uploaded"
    assert file_meta["item_count"] == 3

    # Verify Redis calls (job and tasks)
    job_set_call = next(c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}"))
    stored_job_data = json.loads(job_set_call[0][1])
    assert stored_job_data["total_items"] == 3

    task_set_calls = [c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}:task:")]
    assert len(task_set_calls) == 3

    expected_tasks_details = [
        {"data": "xlsx_data1", "output_filename": "barcode_excel1.png", "options": {"format": "datamatrix", "width": 250, "height": 250, "image_format": "PNG"}},
        {"data": "xlsx_data2", "output_filename": None, "options": {"format": "code128", "width": 200, "height": 150, "image_format": "PNG"}}, # Default width
        {"data": "xlsx_data3", "output_filename": "barcode_excel3.gif", "options": {"format": "code128", "width": 400, "height": 100, "image_format": "GIF"}}, # Default format, default height
    ]

    for i, call_args in enumerate(task_set_calls):
        task_data = json.loads(call_args[0][1])
        expected = expected_tasks_details[i]
        assert task_data["data"] == expected["data"]
        if expected["output_filename"] is None:
            assert task_data["output_filename"].startswith(task_data["task_id"])
            assert task_data["output_filename"].endswith(f".{expected['options']['image_format'].lower()}")
        else:
            assert task_data["output_filename"] == expected["output_filename"]
        assert task_data["options"]["format"] == expected["options"]["format"]
        assert task_data["options"]["width"] == expected["options"]["width"]
        assert task_data["options"]["height"] == expected["options"]["height"]
        assert task_data["options"]["image_format"] == expected["options"]["image_format"]

    # Verify batch processor calls
    assert mock_batch_processor_fixture.add_to_batch.call_count == 3
    batch_calls = mock_batch_processor_fixture.add_to_batch.call_args_list
    for i, call in enumerate(batch_calls):
        task_payload = call[0][1]
        expected = expected_tasks_details[i]
        assert task_payload["data"] == expected["data"]
        assert task_payload["options"]["format"] == expected["options"]["format"]
        assert task_payload["options"]["width"] == expected["options"]["width"]
        assert task_payload["options"]["height"] == expected["options"]["height"]
        assert task_payload["options"]["image_format"] == expected["options"]["image_format"]

def test_upload_csv_missing_data_column(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_batch_processor_fixture: AsyncMock):
    csv_content_missing_data = (
        b"filename,format\n"
        b"barcode1.png,qr"
    ).decode('utf-8')

    files_payload = [
        create_mock_upload_file_tuple("test_missing_data.csv", csv_content_missing_data.encode('utf-8'), "text/csv")
    ]

    response = client.post("/api/bulk/generate_upload", files=files_payload)

    assert response.status_code == 200 # Request is still accepted
    json_response = response.json()
    job_id = json_response["job_id"]
    assert job_id is not None

    assert len(json_response["files_processed"]) == 1
    file_meta = json_response["files_processed"][0]
    assert file_meta["filename"] == "test_missing_data.csv"
    assert file_meta["status"] == "Failed" # File processing should fail
    assert file_meta["item_count"] == 0
    assert "Missing 'data' column" in file_meta["message"]

    # Verify job data in Redis indicates 0 total items from this file
    job_set_call = next(c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}"))
    stored_job_data = json.loads(job_set_call[0][1])
    assert stored_job_data["total_items"] == 0 # No items should be processed from this file

    # Ensure no tasks were created for this job_id
    task_set_calls = [c for c in mock_redis_manager_fixture.redis.set.call_args_list if c[0][0].startswith(f"job:{job_id}:task:")]
    assert len(task_set_calls) == 0

    # Ensure batch processor was not called
    mock_batch_processor_fixture.add_to_batch.assert_not_called()


# TODO: Add more representative tests for other scenarios

# --- Job Status Tests (Basic Examples) ---

def test_get_job_status_not_found(client: TestClient, mock_redis_manager_fixture: MagicMock):
    mock_redis_manager_fixture.redis.get.return_value = None # Simulate job not found
    response = client.get("/api/bulk/bulk_job_status/non_existent_job_id")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]

def test_get_job_status_unauthorized(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "job_for_another_user"
    job_data_for_other_user = {
        "job_id": job_id,
        "user_id": "other_user_456", # Different from mock_user_data.id
        "status": JobStatusEnum.PENDING.value,
        "files": [],
        "progress_percentage": 0,
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(job_data_for_other_user)

    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]

def test_get_job_status_pending(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "pending_job_123"
    mock_file_meta = BulkFileMetadata(
        filename="test.txt", content_type="text/plain", item_count=10, status="Uploaded", message="File processed."
    )
    pending_job_data = {
        "job_id": job_id,
        "user_id": mock_user_data.id,
        "status": JobStatusEnum.PENDING.value,
        "files": [mock_file_meta.model_dump()],
        "progress_percentage": 0.0,
        "total_items": 10,
        "processed_items": 0,
        "initial_setup_complete": True,
        "results": []
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(pending_job_data)
    # For lrange call for results, which should be empty for pending
    mock_redis_manager_fixture.redis.lrange.return_value = []


    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 200
    json_response = response.json()

    assert json_response["job_id"] == job_id
    assert json_response["status"] == JobStatusEnum.PENDING.value
    assert json_response["progress_percentage"] == 0.0
    assert len(json_response["files"]) == 1
    assert json_response["files"][0]["filename"] == "test.txt"
    assert json_response["results"] == []

def test_get_job_status_processing(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "processing_job_456"
    mock_file_meta = BulkFileMetadata(filename="data.csv", content_type="text/csv", item_count=20, status="Processing", message="Ongoing")
    processing_job_data = {
        "job_id": job_id,
        "user_id": mock_user_data.id,
        "status": JobStatusEnum.PROCESSING.value, # Could also be PENDING if initial_setup_complete is true and processed_items > 0 but < total_items
        "files": [mock_file_meta.model_dump()],
        "total_items": 20,
        "processed_items": 5, # Example: 5 items processed
        "initial_setup_complete": True,
        "results": [] # Results might start populating here or fetched by lrange
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(processing_job_data)

    # Simulate some partial results if the logic fetches them via lrange
    # For this test, let's assume results are still empty or not fully populated in the main job hash yet
    mock_redis_manager_fixture.redis.lrange.return_value = []


    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 200
    json_response = response.json()

    assert json_response["job_id"] == job_id
    assert json_response["status"] == JobStatusEnum.PROCESSING.value # Or PENDING, depending on how status is set before completion
    assert json_response["progress_percentage"] == (5 / 20) * 100 # 25.0
    assert len(json_response["files"]) == 1
    assert json_response["files"][0]["filename"] == "data.csv"

def test_get_job_status_completed(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "completed_job_789"
    mock_file_meta = BulkFileMetadata(filename="final.txt", content_type="text/plain", item_count=2, status="Completed", message="All done.")
    completed_job_data = {
        "job_id": job_id,
        "user_id": mock_user_data.id,
        "status": JobStatusEnum.PROCESSING.value, # Status will be updated to COMPLETED by the endpoint logic
        "files": [mock_file_meta.model_dump()],
        "total_items": 2,
        "processed_items": 2,
        "initial_setup_complete": True,
        # "results" key in the main job hash might not be used if lrange is the source of truth for results list
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(completed_job_data)

    mock_results = [
        BarcodeResult(original_data="item1", output_filename="item1.png", status="Generated", barcode_image_url="url1").model_dump_json(),
        BarcodeResult(original_data="item2", output_filename="item2.png", status="Generated", barcode_image_url="url2").model_dump_json(),
    ]
    mock_redis_manager_fixture.redis.lrange.return_value = mock_results
    # Mock hset for when the status is updated to COMPLETED by the endpoint itself
    mock_redis_manager_fixture.redis.hset = AsyncMock(return_value=1)


    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 200
    json_response = response.json()

    assert json_response["job_id"] == job_id
    assert json_response["status"] == JobStatusEnum.COMPLETED.value # Endpoint should update this
    assert json_response["progress_percentage"] == 100.0
    assert len(json_response["results"]) == 2
    assert json_response["results"][0]["original_data"] == "item1"
    assert json_response["results"][0]["status"] == "Generated"

    # Verify that hset was called to update the status to COMPLETED
    mock_redis_manager_fixture.redis.hset.assert_called_with(f"job:{job_id}", "status", JobStatusEnum.COMPLETED.value)


def test_get_job_status_failed(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "failed_job_000"
    failed_job_data = {
        "job_id": job_id,
        "user_id": mock_user_data.id,
        "status": JobStatusEnum.FAILED.value, # Pre-set as FAILED
        "files": [BulkFileMetadata(filename="bad.txt", content_type="text/plain", item_count=1, status="Failed", message="Critical error").model_dump()],
        "total_items": 1,
        "processed_items": 1, # Or 0, depending on when it failed
        "initial_setup_complete": True,
        "error_message": "A global job failure reason."
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(failed_job_data)
    # Assume no results generated or only error result for the one item
    mock_result_item_failed = BarcodeResult(original_data="item_bad", status="Failed", error_message="Failed to process").model_dump_json()
    mock_redis_manager_fixture.redis.lrange.return_value = [mock_result_item_failed]


    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 200
    json_response = response.json()

    assert json_response["job_id"] == job_id
    assert json_response["status"] == JobStatusEnum.FAILED.value
    assert json_response["error_message"] == "A global job failure reason."
    assert json_response["progress_percentage"] == 100.0 # Still 100% as all "processed" (attempted)
    assert len(json_response["results"]) == 1
    assert json_response["results"][0]["status"] == "Failed"


def test_get_job_status_partial_success(client: TestClient, mock_redis_manager_fixture: MagicMock, mock_user_data: UserData):
    job_id = "partial_job_111"
    partial_job_data = {
        "job_id": job_id,
        "user_id": mock_user_data.id,
        "status": JobStatusEnum.PROCESSING.value, # Will be updated by endpoint logic
        "files": [BulkFileMetadata(filename="mixed.txt", content_type="text/plain", item_count=2, status="Completed", message="Processed.").model_dump()],
        "total_items": 2,
        "processed_items": 2,
        "initial_setup_complete": True,
    }
    mock_redis_manager_fixture.redis.get.return_value = json.dumps(partial_job_data)

    mock_results = [
        BarcodeResult(original_data="item_ok", status="Generated", barcode_image_url="url_ok").model_dump_json(),
        BarcodeResult(original_data="item_bad", status="Failed", error_message="Something went wrong").model_dump_json(),
    ]
    mock_redis_manager_fixture.redis.lrange.return_value = mock_results
    mock_redis_manager_fixture.redis.hset = AsyncMock(return_value=1)


    response = client.get(f"/api/bulk/bulk_job_status/{job_id}")
    assert response.status_code == 200
    json_response = response.json()

    assert json_response["job_id"] == job_id
    assert json_response["status"] == JobStatusEnum.PARTIAL_SUCCESS.value # Endpoint should update this
    assert json_response["progress_percentage"] == 100.0
    assert len(json_response["results"]) == 2
    assert json_response["results"][0]["status"] == "Generated"
    assert json_response["results"][1]["status"] == "Failed"

    mock_redis_manager_fixture.redis.hset.assert_called_with(f"job:{job_id}", "status", JobStatusEnum.PARTIAL_SUCCESS.value)
