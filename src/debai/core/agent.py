"""
Agent management module for Debai.

This module provides classes and utilities for creating, managing, and
interacting with AI agents using the cagent framework.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    WAITING = "waiting"


class AgentType(str, Enum):
    """Types of agents available."""
    SYSTEM = "system"           # System maintenance tasks
    PACKAGE = "package"         # Package management
    CONFIG = "config"           # Configuration management
    RESOURCE = "resource"       # Resource monitoring
    SECURITY = "security"       # Security tasks
    BACKUP = "backup"           # Backup management
    NETWORK = "network"         # Network configuration
    CUSTOM = "custom"           # User-defined agents


class AgentCapability(str, Enum):
    """Agent capabilities."""
    READ_SYSTEM = "read_system"
    WRITE_SYSTEM = "write_system"
    EXECUTE_COMMANDS = "execute_commands"
    NETWORK_ACCESS = "network_access"
    FILE_ACCESS = "file_access"
    PACKAGE_INSTALL = "package_install"
    SERVICE_CONTROL = "service_control"
    USER_INTERACTION = "user_interaction"


class AgentConfig(BaseModel):
    """Configuration for an AI agent."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="")
    agent_type: AgentType = Field(default=AgentType.CUSTOM)
    model_id: str = Field(..., description="ID of the model to use")
    capabilities: list[AgentCapability] = Field(default_factory=list)
    
    # Execution settings
    auto_start: bool = Field(default=False)
    interactive: bool = Field(default=True)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    
    # Resource limits
    max_memory_mb: int = Field(default=512, ge=64, le=8192)
    max_cpu_percent: float = Field(default=50.0, ge=1.0, le=100.0)
    
    # Scheduling
    schedule_cron: Optional[str] = Field(default=None)
    run_on_boot: bool = Field(default=False)
    
    # Environment
    environment: dict[str, str] = Field(default_factory=dict)
    working_directory: str = Field(default="/tmp/debai")
    
    # Instructions
    system_prompt: str = Field(
        default="You are a helpful AI assistant managing a GNU/Linux system."
    )
    allowed_commands: list[str] = Field(default_factory=list)
    denied_commands: list[str] = Field(
        default_factory=lambda: ["rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:"]
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class AgentMessage(BaseModel):
    """Message exchanged with an agent."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Agent:
    """
    AI Agent that can perform system tasks autonomously.
    
    This class wraps the cagent framework to provide a high-level interface
    for creating and managing AI agents.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.STOPPED
        self.process: Optional[subprocess.Popen] = None
        self.message_history: list[AgentMessage] = []
        self._callbacks: dict[str, list[Callable]] = {
            "on_start": [],
            "on_stop": [],
            "on_message": [],
            "on_error": [],
            "on_task_complete": [],
        }
        self._lock = asyncio.Lock()
        
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    def is_alive(self) -> bool:
        """Check if the agent process is still running."""
        # First check if we have a subprocess object
        if self.process is not None:
            return self.process.poll() is None
        
        # If no process object, search for cagent process with our config file
        try:
            import psutil
            work_dir = Path(self.config.working_directory)
            agent_config_path = work_dir / f"agent_{self.id}.yaml"
            
            # Search for cagent processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'cagent' and proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if str(agent_config_path) in cmdline:
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            # psutil not available, fall back to checking self.process only
            pass
        
        return False
    
    def update_status(self) -> None:
        """Update the agent status based on process state."""
        if self.is_alive():
            # Process is running, update status to RUNNING
            if self.status in (AgentStatus.STOPPED, AgentStatus.ERROR, AgentStatus.STARTING):
                self.status = AgentStatus.RUNNING
        else:
            # Process is not running, update status to STOPPED
            if self.status == AgentStatus.RUNNING:
                self.status = AgentStatus.STOPPED
    
    def on(self, event: str, callback: Callable) -> None:
        """Register an event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in callback for {event}: {e}")
    
    async def start(self) -> bool:
        """Start the agent."""
        async with self._lock:
            if self.status == AgentStatus.RUNNING:
                logger.warning(f"Agent {self.name} is already running")
                return True
            
            try:
                self.status = AgentStatus.STARTING
                logger.info(f"Starting agent {self.name}...")
                
                # Create working directory
                work_dir = Path(self.config.working_directory)
                work_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate agent configuration for cagent
                agent_config_path = work_dir / f"agent_{self.id}.yaml"
                self._write_cagent_config(agent_config_path)
                
                # Check if model is available, download if needed
                # Get the model ID from the config we just wrote
                with open(agent_config_path) as f:
                    config_data = yaml.safe_load(f)
                    model_id = config_data["agents"]["root"]["model"]
                
                if not self._check_model_available(model_id):
                    logger.info(f"Model {model_id} not found locally, downloading...")
                    if not self._pull_model(model_id):
                        raise Exception(f"Failed to download model {model_id}")
                
                # Start cagent API server
                # Use 'cagent api' to run agent as HTTP API service
                # Each agent gets a unique port based on hash of agent ID
                port = 8000 + (hash(self.id) % 1000)
                
                cmd = [
                    "cagent",
                    "api",
                    str(agent_config_path),
                    "--listen", f":{port}",
                ]
                
                # Log the command for debugging
                logger.debug(f"Starting agent with command: {' '.join(cmd)}")
                logger.info(f"Agent API will listen on port {port}")
                
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(work_dir),
                    env={**os.environ, **self.config.environment},
                )
                
                # Give it a moment to start
                await asyncio.sleep(0.5)
                
                # Check if process is still running
                if self.process.poll() is not None:
                    # Process died immediately
                    stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                    raise Exception(f"Agent process exited immediately: {stderr}")
                
                self.status = AgentStatus.RUNNING
                self._emit("on_start", self)
                logger.info(f"Agent {self.name} started successfully")
                return True
                
            except Exception as e:
                self.status = AgentStatus.ERROR
                self._emit("on_error", self, e)
                logger.error(f"Failed to start agent {self.name}: {e}")
                return False
    
    async def stop(self) -> bool:
        """Stop the agent."""
        async with self._lock:
            # Update status first to check actual process state
            self.update_status()
            
            if self.status == AgentStatus.STOPPED and not self.is_alive():
                return True
            
            try:
                # Try to stop via subprocess object first
                if self.process:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                else:
                    # No subprocess object, find and kill the process using psutil
                    try:
                        import psutil
                        work_dir = Path(self.config.working_directory)
                        agent_config_path = work_dir / f"agent_{self.id}.yaml"
                        
                        # Search for cagent processes
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                            try:
                                if proc.info['name'] == 'cagent' and proc.info['cmdline']:
                                    cmdline = ' '.join(proc.info['cmdline'])
                                    if str(agent_config_path) in cmdline:
                                        logger.info(f"Terminating cagent process PID {proc.info['pid']}")
                                        proc.terminate()
                                        try:
                                            proc.wait(timeout=10)
                                        except psutil.TimeoutExpired:
                                            logger.warning(f"Process {proc.info['pid']} didn't terminate, killing")
                                            proc.kill()
                                            proc.wait()
                                        break
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    except ImportError:
                        logger.warning("psutil not available, cannot stop agent without process object")
                
                self.status = AgentStatus.STOPPED
                self._emit("on_stop", self)
                logger.info(f"Agent {self.name} stopped")
                return True
                
            except Exception as e:
                self._emit("on_error", self, e)
                logger.error(f"Failed to stop agent {self.name}: {e}")
                return False
    
    async def send_message(self, content: str) -> Optional[AgentMessage]:
        """Send a message to the agent and wait for response."""
        if self.status != AgentStatus.RUNNING:
            logger.error(f"Agent {self.name} is not running")
            return None
        
        try:
            import subprocess
            import tempfile
            
            # Record user message
            user_msg = AgentMessage(role="user", content=content)
            self.message_history.append(user_msg)
            
            # Get the temporary agent config path
            agent_config_path = Path(tempfile.gettempdir()) / "debai" / f"agent_{self.id}.yaml"
            
            if not agent_config_path.exists():
                logger.error(f"Agent config file not found: {agent_config_path}")
                return None
            
            # Run cagent with the message
            cmd = [
                "cagent", "run", str(agent_config_path), content, 
                "--tui=false"
            ]
            
            # Execute cagent run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(agent_config_path.parent)
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)
            
            if process.returncode == 0:
                response_content = stdout.decode('utf-8').strip()
                # Remove the "--- Agent: root ---" header if present
                if response_content.startswith("--- Agent:"):
                    lines = response_content.split('\n')
                    if len(lines) > 1:
                        response_content = '\n'.join(lines[1:]).strip()
                
                if response_content:
                    assistant_msg = AgentMessage(role="assistant", content=response_content)
                    self.message_history.append(assistant_msg)
                    self._emit("on_message", self, assistant_msg)
                    return assistant_msg
                else:
                    logger.error(f"Empty response from agent {self.name}")
                    return None
            else:
                error_text = stderr.decode('utf-8')
                logger.error(f"Agent {self.name} error: {error_text}")
                return None
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response from agent {self.name}")
            return None
        except Exception as e:
            logger.error(f"Error sending message to agent {self.name}: {e}")
            return None
    
    async def execute_task(self, task_description: str) -> dict[str, Any]:
        """Execute a task and return the result."""
        result = {
            "success": False,
            "output": "",
            "error": None,
            "duration_seconds": 0,
        }
        
        start_time = datetime.now()
        
        try:
            response = await self.send_message(
                f"Execute the following task: {task_description}"
            )
            
            if response:
                result["success"] = True
                result["output"] = response.content
                self._emit("on_task_complete", self, result)
            
        except Exception as e:
            result["error"] = str(e)
            self._emit("on_error", self, e)
        
        result["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        return result
    
    def _check_model_available(self, model_name: str) -> bool:
        """Check if a model is available locally in docker-model."""
        try:
            result = subprocess.run(
                ["docker-model", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse output and check if model exists
                # Model name might be in format "dmr/model" or just "model"
                check_name = model_name.replace("dmr/", "")
                return check_name in result.stdout
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Could not check model availability (docker-model not found)")
            return True  # Assume available if we can't check
    
    def _pull_model(self, model_name: str) -> bool:
        """Pull a model using docker-model."""
        try:
            # Remove dmr/ prefix if present
            pull_name = model_name.replace("dmr/", "")
            logger.info(f"Downloading model {pull_name}...")
            
            result = subprocess.run(
                ["docker-model", "pull", pull_name],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout for download
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully downloaded model {pull_name}")
                return True
            else:
                logger.error(f"Failed to download model {pull_name}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while downloading model {model_name}")
            return False
        except FileNotFoundError:
            logger.error("docker-model command not found")
            return False
    
    def _write_cagent_config(self, path: Path) -> None:
        """Write cagent configuration file."""
        # cagent v2 format
        # Use the exact model requested by the user
        model_id = self.config.model_id
        
        # Add dmr/ prefix if not already present and no other provider is specified
        if "/" not in model_id:
            model_id = f"dmr/{model_id}"
        
        config = {
            "version": "2",
            "agents": {
                "root": {
                    "description": self.config.description or self.config.name,
                    "instruction": self.config.system_prompt,
                    "model": model_id,
                }
            }
        }
        
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config.model_dump(),
            "message_count": len(self.message_history),
        }
    
    def __repr__(self) -> str:
        return f"Agent(id={self.id}, name={self.name}, status={self.status.value})"


class AgentManager:
    """
    Manager for multiple AI agents.
    
    Provides functionality to create, start, stop, and manage multiple agents.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".config" / "debai" / "agents"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.agents: dict[str, Agent] = {}
        self._lock = asyncio.Lock()
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create a new agent."""
        async with self._lock:
            if config.id in self.agents:
                raise ValueError(f"Agent with id {config.id} already exists")
            
            agent = Agent(config)
            self.agents[config.id] = agent
            
            # Save configuration
            self._save_agent_config(agent)
            
            logger.info(f"Created agent: {agent.name}")
            return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)
    
    def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        agent_type: Optional[AgentType] = None,
    ) -> list[Agent]:
        """List agents with optional filtering."""
        # Update all agent statuses first
        for agent in self.agents.values():
            agent.update_status()
        
        agents = list(self.agents.values())
        
        if status:
            agents = [a for a in agents if a.status == status]
        
        if agent_type:
            agents = [a for a in agents if a.config.agent_type == agent_type]
        
        return agents
    
    async def start_agent(self, agent_id: str) -> bool:
        """Start an agent by ID."""
        agent = self.get_agent(agent_id)
        if agent:
            return await agent.start()
        return False
    
    async def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent by ID."""
        agent = self.get_agent(agent_id)
        if agent:
            return await agent.stop()
        return False
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        async with self._lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return False
            
            # Stop if running
            await agent.stop()
            
            # Remove configuration
            config_path = self.config_dir / f"{agent_id}.yaml"
            if config_path.exists():
                config_path.unlink()
            
            del self.agents[agent_id]
            logger.info(f"Deleted agent: {agent_id}")
            return True
    
    async def start_all(self, auto_start_only: bool = True) -> dict[str, bool]:
        """Start all agents (optionally only auto-start ones)."""
        results = {}
        for agent_id, agent in self.agents.items():
            if not auto_start_only or agent.config.auto_start:
                results[agent_id] = await agent.start()
        return results
    
    async def stop_all(self) -> dict[str, bool]:
        """Stop all running agents."""
        results = {}
        for agent_id, agent in self.agents.items():
            if agent.status == AgentStatus.RUNNING:
                results[agent_id] = await agent.stop()
        return results
    
    def load_agents(self) -> int:
        """Load agents from configuration directory."""
        count = 0
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f)
                
                config = AgentConfig(**data)
                agent = Agent(config)
                self.agents[config.id] = agent
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to load agent from {config_file}: {e}")
        
        logger.info(f"Loaded {count} agents from {self.config_dir}")
        return count
    
    def save_agents(self) -> int:
        """Save all agent configurations."""
        count = 0
        for agent in self.agents.values():
            try:
                self._save_agent_config(agent)
                count += 1
            except Exception as e:
                logger.error(f"Failed to save agent {agent.id}: {e}")
        return count
    
    def _save_agent_config(self, agent: Agent) -> None:
        """Save agent configuration to file."""
        config_path = self.config_dir / f"{agent.id}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(agent.config.model_dump(), f, default_flow_style=False)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get agent statistics."""
        total = len(self.agents)
        by_status = {}
        by_type = {}
        
        for agent in self.agents.values():
            status = agent.status.value
            agent_type = agent.config.agent_type
            
            by_status[status] = by_status.get(status, 0) + 1
            by_type[agent_type] = by_type.get(agent_type, 0) + 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
        }


# Predefined agent templates
AGENT_TEMPLATES = {
    "package_updater": AgentConfig(
        name="Package Updater",
        description="Automatically updates system packages",
        agent_type=AgentType.PACKAGE,
        model_id="llama3.2:3b",
        capabilities=[
            AgentCapability.READ_SYSTEM,
            AgentCapability.EXECUTE_COMMANDS,
            AgentCapability.PACKAGE_INSTALL,
        ],
        system_prompt="""You are a package management agent for a GNU/Linux system.
Your role is to:
1. Check for available package updates
2. Review update changelogs for security implications
3. Apply updates safely during low-usage periods
4. Report any issues or conflicts

Always prioritize security updates and be cautious with major version upgrades.""",
        allowed_commands=["apt", "apt-get", "dpkg", "snap", "flatpak"],
        schedule_cron="0 3 * * *",  # 3 AM daily
    ),
    "config_manager": AgentConfig(
        name="Configuration Manager",
        description="Manages application configurations",
        agent_type=AgentType.CONFIG,
        model_id="llama3.2:3b",
        capabilities=[
            AgentCapability.READ_SYSTEM,
            AgentCapability.FILE_ACCESS,
            AgentCapability.USER_INTERACTION,
        ],
        system_prompt="""You are a configuration management agent.
Your role is to:
1. Monitor configuration files for changes
2. Validate configurations against best practices
3. Suggest optimizations
4. Backup configurations before changes
5. Help users with configuration questions

Always create backups before modifying any configuration.""",
    ),
    "resource_monitor": AgentConfig(
        name="Resource Monitor",
        description="Monitors and optimizes system resources",
        agent_type=AgentType.RESOURCE,
        model_id="llama3.2:3b",
        capabilities=[
            AgentCapability.READ_SYSTEM,
            AgentCapability.EXECUTE_COMMANDS,
            AgentCapability.SERVICE_CONTROL,
        ],
        system_prompt="""You are a resource monitoring agent.
Your role is to:
1. Monitor CPU, memory, disk, and network usage
2. Identify resource-hungry processes
3. Suggest optimizations
4. Alert on critical thresholds
5. Perform automatic cleanup of temporary files

Never terminate critical system processes without explicit permission.""",
        schedule_cron="*/15 * * * *",  # Every 15 minutes
    ),
    "security_guard": AgentConfig(
        name="Security Guard",
        description="Monitors system security",
        agent_type=AgentType.SECURITY,
        model_id="llama3.2:3b",
        capabilities=[
            AgentCapability.READ_SYSTEM,
            AgentCapability.EXECUTE_COMMANDS,
            AgentCapability.NETWORK_ACCESS,
        ],
        system_prompt="""You are a security monitoring agent.
Your role is to:
1. Monitor system logs for suspicious activity
2. Check for unauthorized access attempts
3. Verify file integrity
4. Monitor open ports and network connections
5. Alert on security issues

Never expose sensitive information in logs or reports.""",
        interactive=True,
    ),
    "backup_agent": AgentConfig(
        name="Backup Manager",
        description="Manages system backups",
        agent_type=AgentType.BACKUP,
        model_id="llama3.2:3b",
        capabilities=[
            AgentCapability.READ_SYSTEM,
            AgentCapability.FILE_ACCESS,
            AgentCapability.EXECUTE_COMMANDS,
        ],
        system_prompt="""You are a backup management agent.
Your role is to:
1. Create regular backups of important data
2. Verify backup integrity
3. Manage backup retention policies
4. Perform restore operations when needed
5. Monitor backup storage usage

Always verify backups after creation.""",
        schedule_cron="0 2 * * *",  # 2 AM daily
    ),
}


def get_agent_template(template_name: str) -> Optional[AgentConfig]:
    """Get a predefined agent template."""
    return AGENT_TEMPLATES.get(template_name)


def list_agent_templates() -> list[str]:
    """List available agent templates."""
    return list(AGENT_TEMPLATES.keys())
