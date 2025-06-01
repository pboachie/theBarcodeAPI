import uuid
import json
import io
import pandas as pd
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from fastnanoid import generate as generate_nanoid

from app.dependencies import get_current_user, get_redis_manager
from app.redis_manager import RedisManager


from app.schemas import (
    BarcodeRequest,
    BulkFileMetadata,
    BulkUploadResponse,
    JobStatusEnum,
    JobStatusResponse,
    BarcodeResult,
    UserData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bulk", tags=["Bulk Operations"])

ALLOWED_CONTENT_TYPES = [
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
MAX_FILES = 5


@router.post("/generate_upload", response_model=BulkUploadResponse)
async def bulk_generate_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: UserData = Depends(get_current_user),
    redis_manager: RedisManager = Depends(get_redis_manager),
) -> BulkUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files. Maximum {MAX_FILES} files allowed.",
        )

    job_id = generate_nanoid()
    files_metadata_list: List[BulkFileMetadata] = []
    total_items_to_process = 0

    batch_processor = request.app.state.batch_processor

    for file_idx, file in enumerate(files):
        current_file_item_count = 0
        file_status = "Uploaded"
        file_message = "File uploaded successfully. Processing will start soon."

        metadata = BulkFileMetadata(
            filename=file.filename,
            content_type=file.content_type or "unknown",
            item_count=0,
            status="Pending",
            message=""
        )

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            metadata.status = "Failed"
            metadata.message = f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
            files_metadata_list.append(metadata)
            continue

        try:
            file_content = await file.read()
            await file.seek(0)

            if file.content_type == 'text/plain':
                lines = file_content.decode('utf-8').splitlines()
                for line_num, line_data in enumerate(lines):
                    line_data = line_data.strip()
                    if line_data:
                        current_file_item_count += 1
                        task_id = generate_nanoid()
                        task_key = f"job:{job_id}:task:{task_id}"
                        task_id = generate_nanoid()
                        task_key = f"job:{job_id}:task:{task_id}"

                        barcode_options = {"format": "code128", "image_format": "PNG"}

                        task_payload = {
                            "data": line_data,
                            "options": barcode_options,
                            "task_id": task_id,
                            "job_id": job_id,
                            "original_filename": file.filename,
                            "output_filename": f"{task_id}.png",
                            "status": "PENDING",
                        }
                        await redis_manager.redis.set(task_key, json.dumps(task_payload))
                        await batch_processor.add_to_batch(
                            'generate_barcode',
                            task_payload,
                            priority="MEDIUM"
                        )
                        logger.info(f"Task {task_id} for job {job_id} (file: {file.filename}, line: {line_num}) added to batch for data: {line_data}")

            elif file.content_type == 'text/csv' or \
                 file.content_type == 'application/vnd.ms-excel' or \
                 file.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':

                try:
                    df = pd.read_csv(io.BytesIO(file_content)) if file.content_type == 'text/csv' else pd.read_excel(io.BytesIO(file_content))

                    if 'data' not in df.columns:
                        metadata.status = "Failed"
                        metadata.message = "Missing 'data' column in the file."
                        files_metadata_list.append(metadata)
                        continue

                    for index, row in df.iterrows():
                        barcode_data = row['data']
                        if pd.isna(barcode_data) or str(barcode_data).strip() == "":
                            continue

                        barcode_data = str(barcode_data).strip()
                        current_file_item_count += 1
                        task_id = generate_nanoid()
                        task_key = f"job:{job_id}:task:{task_id}"

                        barcode_options_from_file = {}
                        if 'format' in row and not pd.isna(row['format']): barcode_options_from_file['format'] = str(row['format']).lower()
                        if 'width' in row and not pd.isna(row['width']): barcode_options_from_file['width'] = int(row['width'])
                        if 'height' in row and not pd.isna(row['height']): barcode_options_from_file['height'] = int(row['height'])
                        if 'image_format' in row and not pd.isna(row['image_format']): barcode_options_from_file['image_format'] = str(row['image_format']).upper()
                        if 'show_text' in row and not pd.isna(row['show_text']): barcode_options_from_file['show_text'] = bool(row['show_text'])
                        if 'text_content' in row and not pd.isna(row['text_content']): barcode_options_from_file['text_content'] = str(row['text_content'])
                        if 'module_width' in row and not pd.isna(row['module_width']): barcode_options_from_file['module_width'] = float(row['module_width'])
                        if 'module_height' in row and not pd.isna(row['module_height']): barcode_options_from_file['module_height'] = float(row['module_height'])
                        if 'quiet_zone' in row and not pd.isna(row['quiet_zone']): barcode_options_from_file['quiet_zone'] = float(row['quiet_zone'])
                        if 'font_size' in row and not pd.isna(row['font_size']): barcode_options_from_file['font_size'] = int(row['font_size'])
                        if 'text_distance' in row and not pd.isna(row['text_distance']): barcode_options_from_file['text_distance'] = float(row['text_distance'])
                        if 'background' in row and not pd.isna(row['background']): barcode_options_from_file['background'] = str(row['background'])
                        if 'foreground' in row and not pd.isna(row['foreground']): barcode_options_from_file['foreground'] = str(row['foreground'])
                        if 'center_text' in row and not pd.isna(row['center_text']): barcode_options_from_file['center_text'] = bool(row['center_text'])
                        if 'dpi' in row and not pd.isna(row['dpi']): barcode_options_from_file['dpi'] = int(row['dpi'])
                        if 'add_checksum' in row and not pd.isna(row['add_checksum']): barcode_options_from_file['add_checksum'] = bool(row['add_checksum'])
                        if 'no_checksum' in row and not pd.isna(row['no_checksum']): barcode_options_from_file['no_checksum'] = bool(row['no_checksum'])
                        if 'guardbar' in row and not pd.isna(row['guardbar']): barcode_options_from_file['guardbar'] = bool(row['guardbar'])

                        complete_barcode_options = {
                            "format": "code128",
                            "image_format": "PNG",
                            "width": 200,
                            "height": 100,
                            **barcode_options_from_file
                        }

                        output_filename_suggestion = str(row.get('filename', '')).strip()
                        img_fmt_lower = complete_barcode_options.get("image_format", "png").lower()
                        if output_filename_suggestion:
                            if not output_filename_suggestion.lower().endswith(f".{img_fmt_lower}"):
                                output_filename_suggestion = f"{output_filename_suggestion}.{img_fmt_lower}"
                        else:
                            output_filename_suggestion = f"{task_id}.{img_fmt_lower}"


                        task_payload = {
                            "data": barcode_data,
                            "options": complete_barcode_options,
                            "task_id": task_id,
                            "job_id": job_id,
                            "original_filename": file.filename,
                            "output_filename": output_filename_suggestion,
                            "status": "PENDING",
                        }
                        await redis_manager.redis.set(task_key, json.dumps(task_payload))
                        await batch_processor.add_to_batch(
                            'generate_barcode',
                            task_payload,
                            priority="MEDIUM"
                        )
                        logger.info(f"Task {task_id} for job {job_id} (file: {file.filename}, row: {index}) added to batch for data: {barcode_data}")

                except pd.errors.EmptyDataError:
                    metadata.status = "Failed"
                    metadata.message = "The uploaded file is empty or unparseable."
                except Exception as e:
                    logger.error(f"Error parsing file {file.filename} for job {job_id}: {e}", exc_info=True)
                    metadata.status = "Failed"
                    metadata.message = f"Error processing file: {str(e)}"

            if metadata.status != "Failed":
                metadata.status = "Uploaded"
                metadata.message = "File processed for task creation."

        except Exception as e:
            logger.error(f"Error reading or processing file {file.filename} for job {job_id}: {e}", exc_info=True)
            metadata.status = "Failed"
            metadata.message = f"Error reading file: {str(e)}"

        metadata.item_count = current_file_item_count
        files_metadata_list.append(metadata)
        if metadata.status != "Failed":
            total_items_to_process += current_file_item_count

    # Update overall job state in Redis
    job_data = {
        "status": JobStatusEnum.PENDING.value,
        "files": [meta.model_dump() for meta in files_metadata_list],
        "progress_percentage": 0.0,
        "user_id": current_user.id,
        "results": [],
        "total_items": total_items_to_process,
        "processed_items": 0,
        "initial_setup_complete": True
    }
    await redis_manager.redis.set(f"job:{job_id}", json.dumps(job_data))

    estimated_completion_time = f"{total_items_to_process * 0.5} seconds"
    if total_items_to_process * 0.5 > 1800:
        estimated_completion_time = "Approximately 30 minutes or more."


    return BulkUploadResponse(
        job_id=job_id,
        estimated_completion_time=estimated_completion_time,
        files_processed=files_metadata_list,
    )

@router.get("/job_status/{job_id}", response_model=JobStatusResponse)
async def get_bulk_job_status(
    job_id: str,
    current_user: UserData = Depends(get_current_user),
    redis_manager: RedisManager = Depends(get_redis_manager),
) -> JobStatusResponse:
    job_data_raw = await redis_manager.redis.get(f"job:{job_id}")
    if not job_data_raw:
        raise HTTPException(status_code=404, detail="Job not found.")

    try:
        job_data = json.loads(job_data_raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode job data for job_id: {job_id}")
        raise HTTPException(status_code=500, detail="Error retrieving job status.")

    if job_data.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job.")

    total_items = int(job_data.get("total_items", 0))
    processed_items = int(job_data.get("processed_items", 0))

    progress_percentage = 0.0
    if total_items > 0:
        progress_percentage = round((processed_items / total_items) * 100, 2)

    current_job_status_val = job_data.get("status", JobStatusEnum.PENDING.value)

    results_json_list = await redis_manager.redis.lrange(f"job:{job_id}:results", 0, -1)
    actual_results = [BarcodeResult(**json.loads(r)) for r in results_json_list]

    if job_data.get("initial_setup_complete") and processed_items >= total_items and total_items > 0:
        if current_job_status_val not in [JobStatusEnum.COMPLETED.value, JobStatusEnum.PARTIAL_SUCCESS.value, JobStatusEnum.FAILED.value]:
            has_failures = any(res.status == "Failed" for res in actual_results)
            if has_failures:
                if processed_items == len(actual_results):
                    all_failed = all(res.status == "Failed" for res in actual_results)
                    if all_failed and total_items > 0 :
                        current_job_status_val = JobStatusEnum.FAILED.value
                    else:
                        current_job_status_val = JobStatusEnum.PARTIAL_SUCCESS.value
                else:
                    current_job_status_val = JobStatusEnum.PROCESSING.value
            else:
                current_job_status_val = JobStatusEnum.COMPLETED.value

            if current_job_status_val != job_data.get("status"):
                await redis_manager.redis.hset(f"job:{job_id}", "status", current_job_status_val)
                job_data["status"] = current_job_status_val

    if current_job_status_val in [JobStatusEnum.COMPLETED.value, JobStatusEnum.PARTIAL_SUCCESS.value, JobStatusEnum.FAILED.value] and processed_items == total_items and total_items > 0:
        progress_percentage = 100.0


    return JobStatusResponse(
        job_id=job_id,
        status=JobStatusEnum(current_job_status_val),
        progress_percentage=progress_percentage,
        results=actual_results,
        error_message=job_data.get("error_message"),
        files=[BulkFileMetadata(**fmeta) for fmeta in job_data.get("files", [])],
    )
