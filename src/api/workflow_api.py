"""FastAPI application for workflow execution."""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.api.workflow_executor import WorkflowExecutor, WorkflowRequest, WorkflowResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Track running jobs
jobs_status = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Workflow API Server")
    app.state.executor = WorkflowExecutor(
        comfyui_host=os.getenv("COMFYUI_HOST", "localhost"),
        comfyui_port=int(os.getenv("COMFYUI_PORT", "8188")),
        workflow_path=os.getenv("WORKFLOW_PATH", "/app/workflow.json"),
        output_dir=os.getenv("OUTPUT_DIR", "/app/outputs")
    )
    yield
    # Shutdown
    logger.info("Shutting down Workflow API Server")


# Create FastAPI app
app = FastAPI(
    title="ComfyUI Workflow API",
    description="REST API for executing ComfyUI workflows with parameter injection",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "ComfyUI Workflow API",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/generate",
            "status": "/api/status/{prompt_id}",
            "image": "/api/images/{filename}",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "workflow-api"}


@app.post("/api/generate", response_model=WorkflowResponse)
async def generate_image(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    wait: bool = True
):
    """Generate image from workflow with parameters.
    
    Args:
        request: Workflow parameters
        wait: Whether to wait for completion (default: True)
        
    Returns:
        WorkflowResponse with status and images
    """
    executor = app.state.executor
    
    # Convert request to dict
    parameters = request.dict(exclude_unset=True)
    
    # Handle random seed
    if parameters.get("seed", -1) == -1:
        import random
        parameters["seed"] = random.randint(0, 2**32 - 1)
    
    try:
        if wait:
            # Synchronous execution - wait for completion
            result = await executor.execute_workflow(
                parameters,
                wait_for_completion=True,
                timeout=300.0
            )
            
            return WorkflowResponse(
                prompt_id=result.get("prompt_id", ""),
                status=result.get("status", "unknown"),
                images=result.get("images", [])
            )
        else:
            # Asynchronous execution - return immediately
            workflow = executor.inject_parameters(
                executor.workflow_template,
                parameters
            )
            prompt_id = await executor.submit_workflow(workflow)
            
            # Track job
            jobs_status[prompt_id] = "submitted"
            
            # Start background task to monitor
            background_tasks.add_task(
                monitor_job,
                prompt_id,
                executor
            )
            
            return WorkflowResponse(
                prompt_id=prompt_id,
                status="submitted"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{prompt_id}")
async def get_status(prompt_id: str):
    """Get workflow execution status.
    
    Args:
        prompt_id: Prompt ID to check
        
    Returns:
        Status information
    """
    executor = app.state.executor
    
    try:
        status = await executor.get_status(prompt_id)
        
        # Add images if completed
        if status.get("status") == "completed":
            try:
                images = await executor.get_images(prompt_id)
                status["images"] = images
            except Exception as e:
                logger.error(f"Error getting images: {e}")
        
        return status
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/images/{filename}")
async def get_image(filename: str):
    """Serve generated images.
    
    Args:
        filename: Image filename
        
    Returns:
        Image file
    """
    output_dir = Path(os.getenv("OUTPUT_DIR", "/app/outputs"))
    image_path = output_dir / filename
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=filename
    )


@app.websocket("/ws/{prompt_id}")
async def websocket_progress(websocket: WebSocket, prompt_id: str):
    """WebSocket endpoint for real-time progress updates.
    
    Args:
        websocket: WebSocket connection
        prompt_id: Prompt ID to monitor
    """
    await websocket.accept()
    executor = app.state.executor
    
    try:
        # Send initial status
        status = await executor.get_status(prompt_id)
        await websocket.send_json(status)
        
        # Monitor progress
        while status.get("status") not in ["completed", "failed"]:
            await asyncio.sleep(1.0)
            status = await executor.get_status(prompt_id)
            await websocket.send_json(status)
            
            # Add images if completed
            if status.get("status") == "completed":
                try:
                    images = await executor.get_images(prompt_id)
                    status["images"] = images
                    await websocket.send_json(status)
                except Exception as e:
                    logger.error(f"Error getting images: {e}")
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {prompt_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


@app.post("/api/cancel/{prompt_id}")
async def cancel_generation(prompt_id: str):
    """Cancel a running workflow.
    
    Args:
        prompt_id: Prompt ID to cancel
        
    Returns:
        Cancellation status
    """
    # This would need ComfyUI API support for cancellation
    # For now, just mark as cancelled in our tracking
    if prompt_id in jobs_status:
        jobs_status[prompt_id] = "cancelled"
        return {"status": "cancelled", "prompt_id": prompt_id}
    
    raise HTTPException(status_code=404, detail="Job not found")


async def monitor_job(prompt_id: str, executor: WorkflowExecutor):
    """Background task to monitor job completion.
    
    Args:
        prompt_id: Prompt ID to monitor
        executor: Workflow executor instance
    """
    try:
        timeout = 300.0  # 5 minutes
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            status = await executor.get_status(prompt_id)
            jobs_status[prompt_id] = status.get("status", "unknown")
            
            if status.get("status") in ["completed", "failed"]:
                break
            
            await asyncio.sleep(2.0)
        
        # Timeout
        if prompt_id in jobs_status and jobs_status[prompt_id] not in ["completed", "failed"]:
            jobs_status[prompt_id] = "timeout"
    
    except Exception as e:
        logger.error(f"Error monitoring job {prompt_id}: {e}")
        jobs_status[prompt_id] = "error"


if __name__ == "__main__":
    uvicorn.run(
        "workflow_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )