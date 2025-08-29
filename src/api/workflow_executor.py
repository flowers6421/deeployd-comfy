"""Workflow executor service for ComfyUI API integration."""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import websockets

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes ComfyUI workflows with parameter injection."""
    
    def __init__(
        self,
        comfyui_host: str = "localhost",
        comfyui_port: int = 8188,
        workflow_path: str = "workflow.json",
        output_dir: str = "/tmp/outputs"
    ):
        """Initialize workflow executor.
        
        Args:
            comfyui_host: ComfyUI server hostname
            comfyui_port: ComfyUI server port
            workflow_path: Path to workflow JSON template
            output_dir: Directory for output images
        """
        self.comfyui_url = f"http://{comfyui_host}:{comfyui_port}"
        self.ws_url = f"ws://{comfyui_host}:{comfyui_port}/ws"
        self.workflow_path = Path(workflow_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load workflow template
        with open(self.workflow_path) as f:
            self.workflow_template = json.load(f)
    
    def inject_parameters(
        self,
        workflow: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inject user parameters into workflow.
        
        Args:
            workflow: Workflow template
            parameters: User-provided parameters
            
        Returns:
            Modified workflow with injected parameters
        """
        # Deep copy to avoid modifying template
        import copy
        workflow = copy.deepcopy(workflow)
        
        # Parameter mapping - customize based on your workflow
        param_map = {
            # Text prompts
            "positive_prompt": ("84", "inputs", "text"),
            "negative_prompt": ("74", "inputs", "text"),
            
            # Generation settings
            "seed": ("87", "inputs", "seed"),
            "width": ("89", "inputs", "width"),
            "height": ("89", "inputs", "height"),
            "batch_size": ("89", "inputs", "batch_size"),
            
            # Sampler settings
            "steps": ("88", "inputs", "steps"),
            "cfg": ("88", "inputs", "cfg"),
            "sampler_name": ("88", "inputs", "sampler_name"),
            "scheduler": ("88", "inputs", "scheduler"),
            
            # Model settings
            "shift": ("76", "inputs", "shift"),
            "lora_strength": ("85", "inputs", "strength_model"),
        }
        
        # Inject parameters
        for param_name, param_value in parameters.items():
            if param_name in param_map:
                node_id, *path = param_map[param_name]
                if node_id in workflow:
                    # Navigate to the parameter location
                    target = workflow[node_id]
                    for key in path[:-1]:
                        target = target[key]
                    # Set the value
                    target[path[-1]] = param_value
                    logger.info(f"Injected {param_name}={param_value} into node {node_id}")
        
        return workflow
    
    async def submit_workflow(
        self,
        workflow: Dict[str, Any],
        client_id: Optional[str] = None
    ) -> str:
        """Submit workflow to ComfyUI.
        
        Args:
            workflow: Workflow to execute
            client_id: Optional client ID for WebSocket updates
            
        Returns:
            Prompt ID for tracking execution
        """
        if not client_id:
            client_id = str(uuid.uuid4())
        
        prompt_data = {
            "prompt": workflow,
            "client_id": client_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.comfyui_url}/prompt",
                json=prompt_data
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"ComfyUI error: {error}"
                    )
                
                result = await response.json()
                prompt_id = result.get("prompt_id")
                
                if not prompt_id:
                    raise HTTPException(
                        status_code=500,
                        detail="No prompt_id returned from ComfyUI"
                    )
                
                logger.info(f"Submitted workflow with prompt_id: {prompt_id}")
                return prompt_id
    
    async def get_status(self, prompt_id: str) -> Dict[str, Any]:
        """Get workflow execution status.
        
        Args:
            prompt_id: Prompt ID to check
            
        Returns:
            Status information
        """
        async with aiohttp.ClientSession() as session:
            # Check queue
            async with session.get(f"{self.comfyui_url}/queue") as response:
                queue = await response.json()
                
                # Check if running
                for item in queue.get("queue_running", []):
                    if item[1] == prompt_id:
                        return {
                            "status": "running",
                            "prompt_id": prompt_id,
                            "position": 0
                        }
                
                # Check if pending
                for i, item in enumerate(queue.get("queue_pending", [])):
                    if item[1] == prompt_id:
                        return {
                            "status": "pending",
                            "prompt_id": prompt_id,
                            "position": i + 1
                        }
            
            # Check history for completion
            async with session.get(
                f"{self.comfyui_url}/history/{prompt_id}"
            ) as response:
                history = await response.json()
                
                if prompt_id in history:
                    execution = history[prompt_id]
                    status = execution.get("status", {})
                    
                    if status.get("completed"):
                        return {
                            "status": "completed",
                            "prompt_id": prompt_id,
                            "outputs": execution.get("outputs", {})
                        }
                    else:
                        return {
                            "status": "failed",
                            "prompt_id": prompt_id,
                            "error": status.get("messages", [])
                        }
        
        return {
            "status": "unknown",
            "prompt_id": prompt_id
        }
    
    async def get_images(self, prompt_id: str) -> List[str]:
        """Get generated images from completed workflow.
        
        Args:
            prompt_id: Prompt ID of completed workflow
            
        Returns:
            List of image URLs/paths
        """
        status = await self.get_status(prompt_id)
        
        if status["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Workflow not completed: {status['status']}"
            )
        
        images = []
        outputs = status.get("outputs", {})
        
        # Extract image outputs
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for image in node_output["images"]:
                    filename = image.get("filename")
                    if filename:
                        # Download from ComfyUI
                        image_url = f"{self.comfyui_url}/view"
                        params = {
                            "filename": filename,
                            "type": image.get("type", "output"),
                            "subfolder": image.get("subfolder", "")
                        }
                        
                        # Save locally
                        local_path = self.output_dir / f"{prompt_id}_{filename}"
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                image_url,
                                params=params
                            ) as response:
                                if response.status == 200:
                                    content = await response.read()
                                    with open(local_path, "wb") as f:
                                        f.write(content)
                                    images.append(str(local_path))
        
        return images
    
    async def execute_workflow(
        self,
        parameters: Dict[str, Any],
        wait_for_completion: bool = True,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """Execute workflow with parameters.
        
        Args:
            parameters: User parameters to inject
            wait_for_completion: Whether to wait for completion
            timeout: Maximum time to wait (seconds)
            
        Returns:
            Execution result with status and outputs
        """
        # Inject parameters into workflow
        workflow = self.inject_parameters(self.workflow_template, parameters)
        
        # Submit workflow
        prompt_id = await self.submit_workflow(workflow)
        
        if not wait_for_completion:
            return {
                "prompt_id": prompt_id,
                "status": "submitted"
            }
        
        # Wait for completion
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            status = await self.get_status(prompt_id)
            
            if status["status"] in ["completed", "failed"]:
                if status["status"] == "completed":
                    # Get images
                    images = await self.get_images(prompt_id)
                    status["images"] = images
                
                return status
            
            await asyncio.sleep(1.0)
        
        raise HTTPException(
            status_code=408,
            detail=f"Workflow execution timeout after {timeout} seconds"
        )
    
    async def stream_progress(
        self,
        prompt_id: str,
        websocket: WebSocket
    ):
        """Stream workflow progress via WebSocket.
        
        Args:
            prompt_id: Prompt ID to monitor
            websocket: WebSocket connection for updates
        """
        try:
            # Connect to ComfyUI WebSocket
            async with websockets.connect(self.ws_url) as comfyui_ws:
                # Monitor for updates
                while True:
                    message = await comfyui_ws.recv()
                    data = json.loads(message)
                    
                    # Filter for our prompt_id
                    if data.get("prompt_id") == prompt_id:
                        await websocket.send_json(data)
                        
                        # Check if completed
                        if data.get("type") == "execution_complete":
                            break
        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })


class WorkflowRequest(BaseModel):
    """Request model for workflow execution."""
    
    positive_prompt: str = Field(
        ...,
        description="Positive prompt for image generation"
    )
    negative_prompt: Optional[str] = Field(
        None,
        description="Negative prompt for image generation"
    )
    seed: Optional[int] = Field(
        -1,
        description="Random seed (-1 for random)"
    )
    width: Optional[int] = Field(
        1024,
        ge=64,
        le=2048,
        description="Image width"
    )
    height: Optional[int] = Field(
        1024,
        ge=64,
        le=2048,
        description="Image height"
    )
    steps: Optional[int] = Field(
        20,
        ge=1,
        le=100,
        description="Number of sampling steps"
    )
    cfg: Optional[float] = Field(
        7.0,
        ge=1.0,
        le=30.0,
        description="CFG scale"
    )
    sampler_name: Optional[str] = Field(
        "euler",
        description="Sampler name"
    )
    batch_size: Optional[int] = Field(
        1,
        ge=1,
        le=4,
        description="Batch size"
    )


class WorkflowResponse(BaseModel):
    """Response model for workflow execution."""
    
    prompt_id: str
    status: str
    images: Optional[List[str]] = None
    error: Optional[str] = None