# Debai - AI Agent Management System for GNU/Linux

<div align="center">

![Debai Logo](data/icons/hicolor/scalable/apps/debai.svg)

**Automate your Linux system with intelligent AI agents**

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![GTK4](https://img.shields.io/badge/GTK-4.0-orange.svg)](https://gtk.org)

</div>

---

## Overview

Debai is a comprehensive application for generating and managing AI agents that automate system tasks on GNU/Linux. From package updates to configuration management and resource monitoring, Debai provides intelligent automation without requiring constant user intervention.

### Key Features

- 🤖 **AI Agents**: Create and manage intelligent agents that handle system tasks
- 🧠 **Local AI Models**: Run models locally using Docker Model Runner
- 💻 **Modern Interface**: Beautiful GTK4/Adwaita GUI and powerful CLI
- 📦 **Image Generation**: Create ISO, QCOW2, and Docker Compose deployments
- 🔒 **Secure**: Sandboxed execution with configurable permissions
- ♿ **Accessible**: Designed with accessibility in mind

## Quick Start

### Installation

#### From Debian Package

```bash
# Download the latest release
wget https://github.com/debai/debai/releases/latest/download/debai_1.0.0-1_all.deb

# Install
sudo dpkg -i debai_1.0.0-1_all.deb
sudo apt-get install -f
```

#### From Source

```bash
# Clone the repository
git clone https://github.com/debai/debai.git
cd debai

# Install dependencies
sudo apt install python3-pip python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 docker.io

# Install Debai
pip install -e .

# Initialize
debai init
```

### First Steps

1. **Initialize Debai**:
   ```bash
   debai init
   ```

2. **Pull a model**:
   ```bash
   debai model pull llama3.2:3b
   ```

3. **Create your first agent**:
   ```bash
   debai agent create --name "Package Updater" --template package_updater
   ```

4. **Start the GUI**:
   ```bash
   debai-gui
   ```

## Usage

### Command-Line Interface

Debai provides a comprehensive CLI with rich output:

```bash
# Show system status
debai status

# Agent management
debai agent list                          # List all agents
debai agent create --name "My Agent"      # Create a new agent
debai agent start <agent-id>              # Start an agent
debai agent stop <agent-id>               # Stop an agent
debai agent chat <agent-id>               # Chat with an agent

# Model management
debai model list                          # List available models
debai model pull llama3.2:3b              # Pull a model
debai model recommended                   # Show recommended models

# Task management
debai task list                           # List all tasks
debai task create --name "Update"         # Create a task
debai task run <task-id>                  # Run a task

# Generate deployments
debai generate iso --output debai.iso     # Generate ISO image
debai generate qcow2 --output debai.qcow2 # Generate QCOW2 image
debai generate compose                    # Generate Docker Compose

# Monitoring
debai monitor                             # Real-time resource monitor
```

### Graphical Interface

Launch the modern GTK4 GUI:

```bash
debai-gui
```

Features:
- Dashboard with system metrics
- Agent management with one-click start/stop
- Model browser and download
- Task scheduler
- Image generator
- Settings and preferences

### Agent Templates

Debai includes pre-configured agent templates:

| Template | Description |
|----------|-------------|
| `package_updater` | Automatically updates system packages |
| `config_manager` | Manages application configurations |
| `resource_monitor` | Monitors and optimizes system resources |
| `security_guard` | Monitors system security |
| `backup_agent` | Manages system backups |

Use a template:
```bash
debai agent create --name "Updates" --template package_updater
```

### Generate Deployments

#### ISO Image

Create a bootable ISO with Debai pre-installed:

```bash
debai generate iso \
    --output debai-live.iso \
    --base debian \
    --include-agents
```

#### QCOW2 for QEMU/KVM

Generate a virtual machine image:

```bash
debai generate qcow2 \
    --output debai-vm.qcow2 \
    --size 20G

# Run with QEMU
./run-debai-vm.sh
```

#### Docker Compose

Generate a containerized deployment:

```bash
debai generate compose \
    --output docker-compose.yml \
    --include-gui

# Start services
docker compose up -d
```

## Configuration

The main configuration file is located at `/etc/debai/config.yaml`:

```yaml
general:
  log_level: info
  data_dir: /var/lib/debai

agents:
  max_concurrent: 5
  auto_start: true

models:
  default: llama3.2:3b
  gpu_layers: 0

monitoring:
  enabled: true
  interval: 5
```

User-specific configuration: `~/.config/debai/config.yaml`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Debai                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   CLI       │  │   GUI       │  │   API               │  │
│  │   (Click)   │  │   (GTK4)    │  │   (REST)            │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │                    Core Library                        │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │   Agents    │ │   Models    │ │     Tasks       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │   System    │ │  Generators │ │    Monitors     │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
├──────────────────────────┼──────────────────────────────────┤
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │                 External Services                      │  │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐ │  │
│  │  │  Docker Model       │  │       cagent            │ │  │
│  │  │  Runner             │  │                         │ │  │
│  │  └─────────────────────┘  └─────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

### System Requirements

- GNU/Linux (Debian/Ubuntu recommended)
- Python 3.10 or later
- GTK 4.0 and libadwaita 1.0 (for GUI)
- 4GB RAM minimum (8GB recommended)
- 10GB disk space (more for AI models)

### Dependencies

- **Required**: python3, python3-pip, python3-gi
- **For GUI**: gir1.2-gtk-4.0, gir1.2-adw-1
- **For Models**: docker.io
- **For Images**: qemu-utils, genisoimage

## Building from Source

### Build Requirements

```bash
sudo apt install \
    build-essential \
    debhelper \
    dh-python \
    python3-all \
    python3-setuptools \
    python3-pip
```

### Build Debian Package

```bash
# Install build dependencies
sudo apt build-dep .

# Build the package
dpkg-buildpackage -us -uc -b

# Install
sudo dpkg -i ../debai_1.0.0-1_all.deb
```

### Run Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=debai tests/
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

Debai is released under the [GNU General Public License v3.0](LICENSE).

## Acknowledgments

- [Docker Model Runner](https://docs.docker.com/model-runner/) - Local AI model inference
- [cagent](https://github.com/cagent/cagent) - Agent framework
- [GTK4](https://gtk.org) - GUI toolkit
- [Adwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/) - GNOME design language
- [Rich](https://rich.readthedocs.io) - Beautiful terminal output

## Support

- 📚 [Documentation](https://debai.readthedocs.io)
- 🐛 [Issue Tracker](https://github.com/debai/debai/issues)
- 💬 [Discussions](https://github.com/debai/debai/discussions)

---

<div align="center">
Made with ❤️ for the Linux community
</div>
