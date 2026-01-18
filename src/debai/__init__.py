"""
Debai - AI Agent Management System for GNU/Linux

A comprehensive application for generating and managing AI agents that automate
system tasks like package updates, application configuration, and resource management.

Features:
- Local AI models via Docker Model
- Local agents via cagent
- Interactive CLI and GTK GUI
- ISO, QCOW2, and Docker Compose generation
- Debian packaging support
"""

__version__ = "1.0.0"
__author__ = "Debai Team"
__license__ = "GPL-3.0-or-later"

from debai.core.agent import Agent, AgentConfig, AgentManager
from debai.core.model import Model, ModelConfig, ModelManager
from debai.core.task import Task, TaskConfig, TaskManager

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "Agent",
    "AgentConfig",
    "AgentManager",
    "Model",
    "ModelConfig",
    "ModelManager",
    "Task",
    "TaskConfig",
    "TaskManager",
]
