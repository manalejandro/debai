"""
Model management module for Debai.

This module provides classes and utilities for managing AI models
using Docker Model Runner.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model status enumeration."""
    NOT_PULLED = "not_pulled"
    PULLING = "pulling"
    READY = "ready"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


class ModelProvider(str, Enum):
    """Model providers."""
    DOCKER_MODEL = "docker-model"
    OLLAMA = "ollama"
    LOCAL = "local"


class ModelCapability(str, Enum):
    """Model capabilities."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    CHAT = "chat"
    EMBEDDING = "embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"


class ModelConfig(BaseModel):
    """Configuration for an AI model."""
    
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    provider: ModelProvider = Field(default=ModelProvider.DOCKER_MODEL)
    description: str = Field(default="")
    
    # Model specifications
    parameter_count: str = Field(default="")  # e.g., "7B", "13B"
    context_length: int = Field(default=4096, ge=512, le=131072)
    quantization: str = Field(default="")  # e.g., "Q4_K_M", "Q8_0"
    
    # Capabilities
    capabilities: list[ModelCapability] = Field(default_factory=list)
    
    # Runtime settings
    gpu_layers: int = Field(default=0, ge=0)
    threads: int = Field(default=4, ge=1, le=64)
    batch_size: int = Field(default=512, ge=1, le=4096)
    
    # Generation defaults
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=0, le=100)
    repeat_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    
    # Metadata
    size_bytes: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class Model:
    """
    AI Model wrapper for Docker Model Runner.
    
    Provides a high-level interface for managing and using AI models.
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.status = ModelStatus.NOT_PULLED
        self._lock = asyncio.Lock()
    
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def is_ready(self) -> bool:
        return self.status in (ModelStatus.READY, ModelStatus.LOADED)
    
    async def pull(self, progress_callback: Optional[callable] = None) -> bool:
        """Pull the model from Docker Model Runner."""
        async with self._lock:
            if self.status == ModelStatus.READY:
                return True
            
            try:
                self.status = ModelStatus.PULLING
                logger.info(f"Pulling model {self.id}...")
                
                # Use docker model pull
                process = await asyncio.create_subprocess_exec(
                    "docker", "model", "pull", self.id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    self.status = ModelStatus.READY
                    logger.info(f"Model {self.id} pulled successfully")
                    return True
                else:
                    self.status = ModelStatus.ERROR
                    logger.error(f"Failed to pull model: {stderr.decode()}")
                    return False
                    
            except Exception as e:
                self.status = ModelStatus.ERROR
                logger.error(f"Error pulling model {self.id}: {e}")
                return False
    
    async def load(self) -> bool:
        """Load the model into memory."""
        if self.status not in (ModelStatus.READY, ModelStatus.LOADED):
            logger.error(f"Model {self.id} is not ready")
            return False
        
        try:
            self.status = ModelStatus.LOADING
            
            # Start docker model serve
            process = await asyncio.create_subprocess_exec(
                "docker", "model", "serve", self.id,
                "--threads", str(self.config.threads),
                "--ctx-size", str(self.config.context_length),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            self.status = ModelStatus.LOADED
            logger.info(f"Model {self.id} loaded")
            return True
            
        except Exception as e:
            self.status = ModelStatus.ERROR
            logger.error(f"Error loading model {self.id}: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: Optional[float] = None,
        stop_sequences: Optional[list[str]] = None,
    ) -> str:
        """Generate text using the model."""
        if not self.is_ready:
            raise RuntimeError(f"Model {self.id} is not ready")
        
        try:
            # Build generation request
            cmd = [
                "docker", "model", "run", self.id,
                "--prompt", prompt,
                "--max-tokens", str(max_tokens),
                "--temperature", str(temperature or self.config.temperature),
            ]
            
            if stop_sequences:
                for seq in stop_sequences:
                    cmd.extend(["--stop", seq])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                raise RuntimeError(f"Generation failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat with the model."""
        if not self.is_ready:
            raise RuntimeError(f"Model {self.id} is not ready")
        
        # Format messages for chat
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        
        prompt = "\n".join(formatted) + "\nassistant:"
        return await self.generate(prompt, max_tokens, temperature)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config.model_dump(),
        }
    
    def __repr__(self) -> str:
        return f"Model(id={self.id}, status={self.status.value})"


class ModelManager:
    """
    Manager for AI models.
    
    Handles model discovery, pulling, loading, and lifecycle management.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".config" / "debai" / "models"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.models: dict[str, Model] = {}
        self._lock = asyncio.Lock()
    
    async def discover_models(self) -> list[ModelConfig]:
        """Discover available models from Docker Model Runner."""
        models = []
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "model", "list", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                for item in data:
                    config = ModelConfig(
                        id=item.get("name", item.get("id", "")),
                        name=item.get("name", ""),
                        size_bytes=item.get("size", 0),
                    )
                    models.append(config)
            
        except Exception as e:
            logger.error(f"Error discovering models: {e}")
        
        return models
    
    async def add_model(self, config: ModelConfig) -> Model:
        """Add a model to the manager."""
        async with self._lock:
            if config.id in self.models:
                return self.models[config.id]
            
            model = Model(config)
            self.models[config.id] = model
            
            # Save configuration
            self._save_model_config(model)
            
            logger.info(f"Added model: {model.name}")
            return model
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """Get a model by ID."""
        return self.models.get(model_id)
    
    def list_models(
        self,
        status: Optional[ModelStatus] = None,
        capability: Optional[ModelCapability] = None,
    ) -> list[Model]:
        """List models with optional filtering."""
        models = list(self.models.values())
        
        if status:
            models = [m for m in models if m.status == status]
        
        if capability:
            models = [
                m for m in models 
                if capability in m.config.capabilities
            ]
        
        return models
    
    async def pull_model(
        self,
        model_id: str,
        progress_callback: Optional[callable] = None,
    ) -> bool:
        """Pull a model by ID."""
        model = self.get_model(model_id)
        if model:
            return await model.pull(progress_callback)
        return False
    
    async def remove_model(self, model_id: str) -> bool:
        """Remove a model."""
        async with self._lock:
            model = self.models.get(model_id)
            if not model:
                return False
            
            try:
                # Remove from Docker Model Runner
                process = await asyncio.create_subprocess_exec(
                    "docker", "model", "rm", model_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                
            except Exception as e:
                logger.warning(f"Error removing model from runner: {e}")
            
            # Remove configuration
            config_path = self.config_dir / f"{model_id.replace(':', '_')}.yaml"
            if config_path.exists():
                config_path.unlink()
            
            del self.models[model_id]
            logger.info(f"Removed model: {model_id}")
            return True
    
    def load_models(self) -> int:
        """Load models from configuration directory."""
        count = 0
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f)
                
                config = ModelConfig(**data)
                model = Model(config)
                model.status = ModelStatus.READY  # Assume ready if configured
                self.models[config.id] = model
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to load model from {config_file}: {e}")
        
        logger.info(f"Loaded {count} models from {self.config_dir}")
        return count
    
    def save_models(self) -> int:
        """Save all model configurations."""
        count = 0
        for model in self.models.values():
            try:
                self._save_model_config(model)
                count += 1
            except Exception as e:
                logger.error(f"Failed to save model {model.id}: {e}")
        return count
    
    def _save_model_config(self, model: Model) -> None:
        """Save model configuration to file."""
        config_path = self.config_dir / f"{model.id.replace(':', '_')}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(model.config.model_dump(), f, default_flow_style=False)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get model statistics."""
        total = len(self.models)
        by_status = {}
        total_size = 0
        
        for model in self.models.values():
            status = model.status.value
            by_status[status] = by_status.get(status, 0) + 1
            total_size += model.config.size_bytes
        
        return {
            "total": total,
            "by_status": by_status,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
        }


# Recommended models for different use cases
RECOMMENDED_MODELS = {
    "general": ModelConfig(
        id="llama3.2:3b",
        name="Llama 3.2 3B",
        description="Balanced model for general tasks",
        parameter_count="3B",
        context_length=8192,
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CHAT,
            ModelCapability.CODE_GENERATION,
        ],
    ),
    "code": ModelConfig(
        id="codellama:7b",
        name="Code Llama 7B",
        description="Specialized for code generation and analysis",
        parameter_count="7B",
        context_length=16384,
        capabilities=[
            ModelCapability.CODE_GENERATION,
            ModelCapability.TEXT_GENERATION,
        ],
    ),
    "small": ModelConfig(
        id="llama3.2:1b",
        name="Llama 3.2 1B",
        description="Lightweight model for simple tasks",
        parameter_count="1B",
        context_length=4096,
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CHAT,
        ],
    ),
    "large": ModelConfig(
        id="llama3.1:8b",
        name="Llama 3.1 8B",
        description="Larger model for complex tasks",
        parameter_count="8B",
        context_length=16384,
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CHAT,
            ModelCapability.CODE_GENERATION,
            ModelCapability.FUNCTION_CALLING,
        ],
    ),
}


def get_recommended_model(use_case: str) -> Optional[ModelConfig]:
    """Get a recommended model for a specific use case."""
    return RECOMMENDED_MODELS.get(use_case)


def list_recommended_models() -> list[str]:
    """List available recommended model configurations."""
    return list(RECOMMENDED_MODELS.keys())
