import os
import logger
import uuid
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict
from models import SeparationResponse
from processor import AudioSeparatorProcessor
from config import settings

router = APIRouter()
processor = AudioSeparatorProcessor()
new_logger = logger.CustomLogger()

class AudioSeparationRequest(BaseModel):
    audio_path: str
    model: str
    task_id: str
    output_path: str

class SeparationResponse(BaseModel):
    status: str
    task_id: str
    message: Optional[str] = None
    separated_audio: Optional[Dict[str, str]] = Field(default_factory=dict)
    file_paths: Optional[Dict[str, str]] = Field(default_factory=dict)
    has_audio_stream: bool = True

def validate_file_path(file_path: str) -> bool:
    """验证文件路径是否存在"""
    return os.path.exists(file_path)

def validate_output_directory(output_path: str) -> bool:
    """验证输出目录是否存在，如不存在则创建"""
    try:
        os.makedirs(output_path, exist_ok=True)
        return True
    except Exception:
        return False

@router.post("/api/v1/audio-separation/process", response_model=SeparationResponse)
async def separate_audio(request: AudioSeparationRequest):
    request_id = uuid.uuid4().hex
    start_time = time.time()
    
    try:
        # 记录请求信息
        new_logger.info(
            f"Request received - request_id: {request_id}, "
            f"task_id: {request.task_id}, "
            f"model: {request.model}, "
            f"audio_path: {request.audio_path}"
        )

        # 输入验证
        if not validate_file_path(request.audio_path):
            error_msg = f"Input audio file not found: {request.audio_path}"
            new_logger.error(f"Request failed - task_id: {request.task_id}, error: {error_msg}")
            return SeparationResponse(
                status="error",
                task_id=request.task_id,
                message=error_msg
            )

        if not validate_output_directory(request.output_path):
            error_msg = f"Cannot create or access output directory: {request.output_path}"
            new_logger.error(f"Request failed - task_id: {request.task_id}, error: {error_msg}")
            return SeparationResponse(
                status="error",
                task_id=request.task_id,
                message=error_msg
            )

        # 处理音频文件
        try:
            output_files = processor.process_audio(
                request.audio_path,
                request.task_id,
                request.output_path
            )
        except Exception as e:
            error_msg = f"Audio processing failed: {str(e)}"
            new_logger.error(f"Processing failed - task_id: {request.task_id}, error: {error_msg}")
            return SeparationResponse(
                status="error",
                task_id=request.task_id,
                message=error_msg
            )

        # 检查是否有音频流
        has_audio_stream = output_files.get("has_audio_stream", True)
        
        # 如果没有音频流，返回特殊响应
        if not has_audio_stream:
            new_logger.info(f"文件不包含音频流 - task_id: {request.task_id}")
            return SeparationResponse(
                status="success",
                message="文件不包含音频流",
                task_id=request.task_id,
                has_audio_stream=False,
                separated_audio={
                    "vocals": "",
                    "accompaniment": ""
                },
                file_paths={
                    "vocals": "",
                    "accompaniment": ""
                }
            )

        # 构建成功响应
        response = SeparationResponse(
            status="success",
            message="success",
            task_id=request.task_id,
            has_audio_stream=True,
            separated_audio={
                "vocals": os.path.basename(output_files["vocals"]),
                "accompaniment": os.path.basename(output_files["accompaniment"]) if output_files.get("accompaniment") else ""
            },
            file_paths={
                "vocals": output_files["vocals"],
                "accompaniment": output_files.get("accompaniment", "")
            }
        )

        # 记录处理时间和成功信息
        processing_time = time.time() - start_time
        new_logger.info(
            f"Request completed - task_id: {request.task_id}, "
            f"processing_time: {processing_time:.2f}s"
        )
        
        return response

    except Exception as e:
        # 捕获所有未预期的异常
        error_msg = f"Unexpected error: {str(e)}"
        new_logger.error(
            f"Unexpected error occurred - request_id: {request_id}, "
            f"task_id: {request.task_id}, error: {error_msg}"
        )
        
        return SeparationResponse(
            status="error",
            task_id=request.task_id,
            message=error_msg
        )