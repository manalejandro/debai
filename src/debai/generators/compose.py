"""
Docker Compose configuration generator for Debai.

Generates Docker Compose configurations for running Debai in containers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class ComposeGenerator:
    """
    Generates Docker Compose configurations for Debai.
    
    Creates production-ready compose files with all necessary services.
    """
    
    def __init__(
        self,
        output_path: Path,
        include_gui: bool = True,
        include_monitoring: bool = True,
        include_models: bool = True,
        model_ids: Optional[list[str]] = None,
    ):
        self.output_path = output_path
        self.include_gui = include_gui
        self.include_monitoring = include_monitoring
        self.include_models = include_models
        self.model_ids = model_ids or ["llama3.2:3b"]
    
    def generate(self) -> dict[str, Any]:
        """Generate the Docker Compose configuration."""
        result = {
            "success": False,
            "output_path": str(self.output_path),
            "services": [],
            "error": None,
        }
        
        try:
            compose = self._build_compose()
            
            # Write the compose file
            with open(self.output_path, "w") as f:
                yaml.dump(compose, f, default_flow_style=False, sort_keys=False)
            
            result["success"] = True
            result["services"] = list(compose.get("services", {}).keys())
            
            # Also create .env file
            self._create_env_file()
            
            # Create helper scripts
            self._create_helper_scripts()
            
            logger.info(f"Docker Compose configuration generated: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Compose generation failed: {e}")
            result["error"] = str(e)
        
        return result
    
    def _build_compose(self) -> dict[str, Any]:
        """Build the compose configuration dictionary."""
        compose = {
            "version": "3.8",
            "name": "debai",
            "services": {},
            "volumes": {},
            "networks": {
                "debai-network": {
                    "driver": "bridge",
                }
            },
        }
        
        # Core Debai service
        compose["services"]["debai-core"] = {
            "image": "debai/core:latest",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile",
            },
            "container_name": "debai-core",
            "restart": "unless-stopped",
            "environment": [
                "DEBAI_CONFIG_DIR=/etc/debai",
                "DEBAI_DATA_DIR=/var/lib/debai",
                "DEBAI_LOG_LEVEL=${DEBAI_LOG_LEVEL:-info}",
            ],
            "volumes": [
                "debai-config:/etc/debai",
                "debai-data:/var/lib/debai",
                "/var/run/docker.sock:/var/run/docker.sock:ro",
            ],
            "networks": ["debai-network"],
            "healthcheck": {
                "test": ["CMD", "debai", "status"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        }
        compose["volumes"]["debai-config"] = {}
        compose["volumes"]["debai-data"] = {}
        
        # Model service (Docker Model Runner)
        if self.include_models:
            compose["services"]["debai-models"] = {
                "image": "aimodel/runner:latest",
                "container_name": "debai-models",
                "restart": "unless-stopped",
                "environment": [
                    "MODEL_CACHE_DIR=/models",
                ],
                "volumes": [
                    "debai-models:/models",
                ],
                "networks": ["debai-network"],
                "ports": [
                    "11434:11434",
                ],
                "deploy": {
                    "resources": {
                        "limits": {
                            "memory": "8G",
                        },
                        "reservations": {
                            "memory": "4G",
                        },
                    },
                },
            }
            compose["volumes"]["debai-models"] = {}
        
        # Agent service (cagent)
        compose["services"]["debai-agents"] = {
            "image": "debai/agents:latest",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile.agents",
            },
            "container_name": "debai-agents",
            "restart": "unless-stopped",
            "depends_on": ["debai-core"],
            "environment": [
                "DEBAI_CORE_URL=http://debai-core:8000",
                "DEBAI_MODEL_URL=http://debai-models:11434",
            ],
            "volumes": [
                "debai-config:/etc/debai:ro",
                "debai-agents:/var/lib/debai/agents",
            ],
            "networks": ["debai-network"],
        }
        compose["volumes"]["debai-agents"] = {}
        
        # API service
        compose["services"]["debai-api"] = {
            "image": "debai/api:latest",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile.api",
            },
            "container_name": "debai-api",
            "restart": "unless-stopped",
            "depends_on": ["debai-core", "debai-agents"],
            "environment": [
                "DEBAI_API_PORT=8000",
                "DEBAI_API_HOST=0.0.0.0",
            ],
            "ports": [
                "8000:8000",
            ],
            "networks": ["debai-network"],
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        }
        
        # GUI service
        if self.include_gui:
            compose["services"]["debai-gui"] = {
                "image": "debai/gui:latest",
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile.gui",
                },
                "container_name": "debai-gui",
                "restart": "unless-stopped",
                "depends_on": ["debai-api"],
                "environment": [
                    "DEBAI_API_URL=http://debai-api:8000",
                ],
                "ports": [
                    "8080:8080",
                ],
                "networks": ["debai-network"],
            }
        
        # Monitoring services
        if self.include_monitoring:
            # Prometheus for metrics
            compose["services"]["prometheus"] = {
                "image": "prom/prometheus:latest",
                "container_name": "debai-prometheus",
                "restart": "unless-stopped",
                "volumes": [
                    "./prometheus.yml:/etc/prometheus/prometheus.yml:ro",
                    "prometheus-data:/prometheus",
                ],
                "ports": [
                    "9090:9090",
                ],
                "networks": ["debai-network"],
                "command": [
                    "--config.file=/etc/prometheus/prometheus.yml",
                    "--storage.tsdb.path=/prometheus",
                ],
            }
            compose["volumes"]["prometheus-data"] = {}
            
            # Grafana for dashboards
            compose["services"]["grafana"] = {
                "image": "grafana/grafana:latest",
                "container_name": "debai-grafana",
                "restart": "unless-stopped",
                "depends_on": ["prometheus"],
                "environment": [
                    "GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-debai}",
                    "GF_USERS_ALLOW_SIGN_UP=false",
                ],
                "volumes": [
                    "grafana-data:/var/lib/grafana",
                    "./grafana/provisioning:/etc/grafana/provisioning:ro",
                ],
                "ports": [
                    "3000:3000",
                ],
                "networks": ["debai-network"],
            }
            compose["volumes"]["grafana-data"] = {}
        
        return compose
    
    def _create_env_file(self) -> None:
        """Create the .env file with configuration."""
        env_content = """# Debai Docker Environment Configuration

# Logging
DEBAI_LOG_LEVEL=info

# API Configuration
DEBAI_API_PORT=8000

# Model Configuration
DEBAI_DEFAULT_MODEL=llama3.2:3b

# Monitoring
GRAFANA_PASSWORD=debai

# Security
# Generate a secure key for production:
# python3 -c "import secrets; print(secrets.token_hex(32))"
DEBAI_SECRET_KEY=change-me-in-production

# GPU Support (uncomment for NVIDIA GPU)
# NVIDIA_VISIBLE_DEVICES=all
"""
        
        env_path = self.output_path.parent / ".env"
        env_path.write_text(env_content)
        logger.info(f"Created .env file: {env_path}")
    
    def _create_helper_scripts(self) -> None:
        """Create helper scripts for Docker Compose management."""
        output_dir = self.output_path.parent
        
        # Start script
        start_script = """#!/bin/bash
# Start Debai services

set -e

echo "Starting Debai services..."

# Build images if needed
docker compose build

# Start services
docker compose up -d

echo ""
echo "Debai is starting up..."
echo ""
echo "Services:"
echo "  - API: http://localhost:8000"
echo "  - GUI: http://localhost:8080"
echo "  - Grafana: http://localhost:3000 (admin/debai)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "View logs: docker compose logs -f"
echo "Stop: ./stop.sh"
"""
        
        start_path = output_dir / "start.sh"
        start_path.write_text(start_script)
        start_path.chmod(0o755)
        
        # Stop script
        stop_script = """#!/bin/bash
# Stop Debai services

echo "Stopping Debai services..."
docker compose down

echo "Services stopped."
"""
        
        stop_path = output_dir / "stop.sh"
        stop_path.write_text(stop_script)
        stop_path.chmod(0o755)
        
        # Logs script
        logs_script = """#!/bin/bash
# View Debai service logs

SERVICE=${1:-}

if [ -z "$SERVICE" ]; then
    docker compose logs -f
else
    docker compose logs -f "$SERVICE"
fi
"""
        
        logs_path = output_dir / "logs.sh"
        logs_path.write_text(logs_script)
        logs_path.chmod(0o755)
        
        # Create Dockerfile for core service
        dockerfile = """FROM python:3.11-slim

LABEL maintainer="Debai Team"
LABEL description="Debai AI Agent System"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Create debai user
RUN useradd -m -s /bin/bash debai

# Install Debai
RUN pip install --no-cache-dir debai

# Create directories
RUN mkdir -p /etc/debai /var/lib/debai /var/log/debai \\
    && chown -R debai:debai /etc/debai /var/lib/debai /var/log/debai

# Switch to debai user
USER debai
WORKDIR /home/debai

# Initialize Debai
RUN debai init

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Start Debai
CMD ["debai", "serve", "--host", "0.0.0.0", "--port", "8000"]
"""
        
        dockerfile_path = output_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile)
        
        # Create Prometheus configuration
        prometheus_config = """global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'debai-api'
    static_configs:
      - targets: ['debai-api:8000']
    metrics_path: '/metrics'

  - job_name: 'debai-core'
    static_configs:
      - targets: ['debai-core:8000']
    metrics_path: '/metrics'

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
"""
        
        prometheus_path = output_dir / "prometheus.yml"
        prometheus_path.write_text(prometheus_config)
        
        logger.info("Created helper scripts and configurations")


# Quick compose templates for common scenarios
COMPOSE_TEMPLATES = {
    "minimal": {
        "description": "Minimal setup with core and one model",
        "include_gui": False,
        "include_monitoring": False,
        "include_models": True,
        "model_ids": ["llama3.2:1b"],
    },
    "standard": {
        "description": "Standard setup with GUI and monitoring",
        "include_gui": True,
        "include_monitoring": True,
        "include_models": True,
        "model_ids": ["llama3.2:3b"],
    },
    "production": {
        "description": "Production setup with all features",
        "include_gui": True,
        "include_monitoring": True,
        "include_models": True,
        "model_ids": ["llama3.2:3b", "codellama:7b"],
    },
}


def get_compose_template(name: str) -> Optional[dict[str, Any]]:
    """Get a compose template by name."""
    return COMPOSE_TEMPLATES.get(name)


def list_compose_templates() -> list[str]:
    """List available compose templates."""
    return list(COMPOSE_TEMPLATES.keys())
