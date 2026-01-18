"""
Task management module for Debai.

This module provides classes and utilities for creating and managing
automated tasks that agents can execute.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Types of tasks."""
    COMMAND = "command"          # Execute shell command
    SCRIPT = "script"            # Run a script file
    AGENT = "agent"              # Delegate to agent
    WORKFLOW = "workflow"        # Multi-step workflow
    SCHEDULED = "scheduled"      # Cron-scheduled task
    EVENT = "event"              # Event-triggered task


class TaskConfig(BaseModel):
    """Configuration for a task."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="")
    task_type: TaskType = Field(default=TaskType.COMMAND)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    
    # Execution
    command: str = Field(default="")
    script_path: str = Field(default="")
    agent_id: Optional[str] = Field(default=None)
    working_directory: str = Field(default="/tmp")
    environment: dict[str, str] = Field(default_factory=dict)
    
    # Scheduling
    schedule_cron: Optional[str] = Field(default=None)
    schedule_at: Optional[datetime] = Field(default=None)
    repeat_count: int = Field(default=0)  # 0 = infinite
    repeat_interval_minutes: int = Field(default=0)
    
    # Limits
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=30, ge=1, le=3600)
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    
    # Notifications
    notify_on_complete: bool = Field(default=False)
    notify_on_failure: bool = Field(default=True)
    notification_email: Optional[str] = Field(default=None)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class TaskResult(BaseModel):
    """Result of a task execution."""
    
    task_id: str
    success: bool
    exit_code: int = Field(default=0)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    retry_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task:
    """
    A task that can be executed by the system or delegated to an agent.
    """
    
    def __init__(self, config: TaskConfig):
        self.config = config
        self.status = TaskStatus.PENDING
        self.current_retry = 0
        self.last_result: Optional[TaskResult] = None
        self.history: list[TaskResult] = []
        self._callbacks: dict[str, list[Callable]] = {
            "on_start": [],
            "on_complete": [],
            "on_failure": [],
            "on_retry": [],
        }
        self._lock = asyncio.Lock()
        self._process: Optional[asyncio.subprocess.Process] = None
    
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
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
    
    async def execute(self) -> TaskResult:
        """Execute the task."""
        async with self._lock:
            started_at = datetime.now()
            self.status = TaskStatus.RUNNING
            self._emit("on_start", self)
            
            try:
                if self.config.task_type == TaskType.COMMAND:
                    result = await self._execute_command()
                elif self.config.task_type == TaskType.SCRIPT:
                    result = await self._execute_script()
                elif self.config.task_type == TaskType.AGENT:
                    result = await self._execute_agent()
                else:
                    result = await self._execute_command()
                
                completed_at = datetime.now()
                
                task_result = TaskResult(
                    task_id=self.id,
                    success=result["success"],
                    exit_code=result.get("exit_code", 0),
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    retry_count=self.current_retry,
                )
                
                if task_result.success:
                    self.status = TaskStatus.COMPLETED
                    self._emit("on_complete", self, task_result)
                else:
                    if self.current_retry < self.config.max_retries:
                        self.current_retry += 1
                        self._emit("on_retry", self, self.current_retry)
                        await asyncio.sleep(self.config.retry_delay_seconds)
                        return await self.execute()
                    else:
                        self.status = TaskStatus.FAILED
                        self._emit("on_failure", self, task_result)
                
                self.last_result = task_result
                self.history.append(task_result)
                return task_result
                
            except Exception as e:
                completed_at = datetime.now()
                task_result = TaskResult(
                    task_id=self.id,
                    success=False,
                    exit_code=-1,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    error_message=str(e),
                )
                self.status = TaskStatus.FAILED
                self._emit("on_failure", self, task_result)
                self.last_result = task_result
                self.history.append(task_result)
                return task_result
    
    async def _execute_command(self) -> dict[str, Any]:
        """Execute a shell command."""
        try:
            # Merge system environment with task-specific environment
            task_env = os.environ.copy()
            task_env.update(self.config.environment)
            
            self._process = await asyncio.create_subprocess_shell(
                self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_directory,
                env=task_env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    self._process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
                return {
                    "success": False,
                    "exit_code": -1,
                    "stderr": "Task timed out",
                }
            
            return {
                "success": self._process.returncode == 0,
                "exit_code": self._process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
            
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stderr": str(e),
            }
    
    async def _execute_script(self) -> dict[str, Any]:
        """Execute a script file."""
        script_path = Path(self.config.script_path)
        if not script_path.exists():
            return {
                "success": False,
                "exit_code": -1,
                "stderr": f"Script not found: {script_path}",
            }
        
        # Determine interpreter
        with open(script_path) as f:
            first_line = f.readline()
        
        if first_line.startswith("#!"):
            interpreter = first_line[2:].strip()
            command = f"{interpreter} {script_path}"
        else:
            command = f"bash {script_path}"
        
        self.config.command = command
        return await self._execute_command()
    
    async def _execute_agent(self) -> dict[str, Any]:
        """Execute task via an agent."""
        # This would integrate with the AgentManager
        # For now, return a placeholder
        return {
            "success": True,
            "exit_code": 0,
            "stdout": f"Agent {self.config.agent_id} executed task",
        }
    
    async def cancel(self) -> bool:
        """Cancel the task."""
        if self.status != TaskStatus.RUNNING:
            return False
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._process.kill()
        
        self.status = TaskStatus.CANCELLED
        return True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config.model_dump(),
            "current_retry": self.current_retry,
            "last_result": self.last_result.model_dump() if self.last_result else None,
            "history_count": len(self.history),
        }
    
    def __repr__(self) -> str:
        return f"Task(id={self.id}, name={self.name}, status={self.status.value})"


class TaskManager:
    """
    Manager for tasks.
    
    Handles task scheduling, execution, and lifecycle management.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".config" / "debai" / "tasks"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def create_task(self, config: TaskConfig) -> Task:
        """Create a new task."""
        async with self._lock:
            if config.id in self.tasks:
                raise ValueError(f"Task with id {config.id} already exists")
            
            task = Task(config)
            self.tasks[config.id] = task
            
            # Save configuration
            self._save_task_config(task)
            
            logger.info(f"Created task: {task.name}")
            return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        priority: Optional[TaskPriority] = None,
    ) -> list[Task]:
        """List tasks with optional filtering."""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if task_type:
            tasks = [t for t in tasks if t.config.task_type == task_type]
        
        if priority:
            tasks = [t for t in tasks if t.config.priority == priority]
        
        return tasks
    
    async def run_task(self, task_id: str) -> Optional[TaskResult]:
        """Run a task immediately."""
        task = self.get_task(task_id)
        if task:
            return await task.execute()
        return None
    
    async def queue_task(self, task_id: str) -> bool:
        """Add a task to the execution queue."""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.SCHEDULED
            await self.queue.put(task)
            return True
        return False
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self.get_task(task_id)
        if task:
            return await task.cancel()
        return False
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            # Cancel if running
            await task.cancel()
            
            # Remove configuration
            config_path = self.config_dir / f"{task_id}.yaml"
            if config_path.exists():
                config_path.unlink()
            
            del self.tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
    
    async def start_worker(self) -> None:
        """Start the task queue worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Task worker started")
    
    async def stop_worker(self) -> None:
        """Stop the task queue worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Task worker stopped")
    
    async def _worker_loop(self) -> None:
        """Worker loop that processes queued tasks."""
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await task.execute()
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
    
    def load_tasks(self) -> int:
        """Load tasks from configuration directory."""
        count = 0
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f)
                
                config = TaskConfig(**data)
                task = Task(config)
                self.tasks[config.id] = task
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to load task from {config_file}: {e}")
        
        logger.info(f"Loaded {count} tasks from {self.config_dir}")
        return count
    
    def save_tasks(self) -> int:
        """Save all task configurations."""
        count = 0
        for task in self.tasks.values():
            try:
                self._save_task_config(task)
                count += 1
            except Exception as e:
                logger.error(f"Failed to save task {task.id}: {e}")
        return count
    
    def _save_task_config(self, task: Task) -> None:
        """Save task configuration to file."""
        config_path = self.config_dir / f"{task.id}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(task.config.model_dump(), f, default_flow_style=False)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get task statistics."""
        total = len(self.tasks)
        by_status = {}
        by_type = {}
        by_priority = {}
        
        for task in self.tasks.values():
            status = task.status.value
            task_type = task.config.task_type
            priority = task.config.priority
            
            by_status[status] = by_status.get(status, 0) + 1
            by_type[task_type] = by_type.get(task_type, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_priority": by_priority,
            "queue_size": self.queue.qsize(),
        }


# Predefined task templates
TASK_TEMPLATES = {
    "update_packages": TaskConfig(
        name="Update System Packages",
        description="Update all system packages to latest versions",
        task_type=TaskType.COMMAND,
        command="apt update && apt upgrade -y",
        priority=TaskPriority.NORMAL,
        timeout_seconds=1800,
    ),
    "cleanup_temp": TaskConfig(
        name="Cleanup Temporary Files",
        description="Remove temporary files older than 7 days",
        task_type=TaskType.COMMAND,
        command="find /tmp -type f -mtime +7 -delete",
        priority=TaskPriority.LOW,
    ),
    "check_disk": TaskConfig(
        name="Check Disk Usage",
        description="Check disk usage and report if above 80%",
        task_type=TaskType.COMMAND,
        command="df -h | awk 'NR>1 && int($5)>80 {print $0}'",
        priority=TaskPriority.HIGH,
    ),
    "security_updates": TaskConfig(
        name="Security Updates",
        description="Install security updates only",
        task_type=TaskType.COMMAND,
        command="apt update && apt upgrade -y --only-upgrade $(apt list --upgradable 2>/dev/null | grep -i security | cut -d'/' -f1)",
        priority=TaskPriority.CRITICAL,
        timeout_seconds=1800,
    ),
    "system_health": TaskConfig(
        name="System Health Check",
        description="Comprehensive system health check",
        task_type=TaskType.COMMAND,
        command="echo '=== System Health ===' && uptime && echo && echo '=== Memory ===' && free -h && echo && echo '=== Disk ===' && df -h && echo && echo '=== Load ===' && cat /proc/loadavg",
        priority=TaskPriority.NORMAL,
    ),
}


def get_task_template(template_name: str) -> Optional[TaskConfig]:
    """Get a predefined task template."""
    template = TASK_TEMPLATES.get(template_name)
    if template:
        # Return a copy with a new ID
        data = template.model_dump()
        data["id"] = str(uuid.uuid4())[:8]
        return TaskConfig(**data)
    return None


def list_task_templates() -> list[str]:
    """List available task templates."""
    return list(TASK_TEMPLATES.keys())
