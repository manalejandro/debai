# Installation Guide

This guide provides detailed instructions for installing Debai on your GNU/Linux system.

## Prerequisites

### System Requirements

- **Operating System**: Debian 13 (Trixie) or newer, Ubuntu 24.04 or newer, or compatible
- **Python**: 3.10 or later
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space (more for AI models)
- **Architecture**: x86_64 (amd64)

### Dependencies

#### Required

```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1
```

#### Recommended

**Docker Engine from Official Repository:**

```bash
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker Engine, containerd, and Docker Compose
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

**For Ubuntu:**

```bash
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker Engine, containerd, and Docker Compose
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

**Other utilities:**

```bash
sudo apt install -y \
    qemu-utils \
    genisoimage
```

## Installation Methods

### Method 1: Debian Package (Recommended)

Download and install the `.deb` package:

```bash
# Download the latest release
wget https://github.com/manalejandro/debai/releases/latest/download/debai_1.0.0-1_all.deb

# Install
sudo dpkg -i debai_1.0.0-1_all.deb

# Install missing dependencies
sudo apt-get install -f
```

### Method 2: From PyPI

```bash
# Install from PyPI
pip install debai

# Or with GUI support
pip install debai[gui]
```

### Method 3: From Source

```bash
# Clone the repository
git clone https://github.com/debai/debai.git
cd debai

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .

# Or with all extras
pip install -e ".[gui,dev,docs]"
```

**Note:** Docker Engine must be installed separately from the official Docker repository. See the "Recommended" dependencies section above for installation instructions.

### Method 4: Build Debian Package

```bash
# Clone the repository
git clone https://github.com/manalejandro/debai.git
cd debai

# Install build dependencies
sudo apt install -y \
    build-essential \
    debhelper \
    dh-python \
    python3-all \
    python3-setuptools

# Build the package
dpkg-buildpackage -us -uc -b

# Install
sudo dpkg -i ../debai_1.0.0-1_all.deb
sudo apt-get install -f
```

## Post-Installation

### Initialize Debai

```bash
# Basic initialization
debai init

# Full initialization (includes pulling recommended model)
debai init --full
```

### Configure Docker (Required for Models)

After installing Docker Engine from the official repository:

```bash
# Verify Docker installation
docker --version

# Add your user to docker group
sudo usermod -aG docker $USER

# Restart Docker service
sudo systemctl restart docker

# Enable Docker to start on boot
sudo systemctl enable docker

# You may need to log out and back in for group changes to take effect
# Or use: newgrp docker
```

**Test Docker installation:**

```bash
# Run test container
docker run hello-world

# Check if Docker daemon is running
sudo systemctl status docker
```

### Verify Installation

```bash
# Check version
debai --version

# Show status
debai status

# List available models
debai model list
```

### Enable System Service (Optional)

```bash
# Enable Debai service to start on boot
sudo systemctl enable debai

# Start the service
sudo systemctl start debai

# Check status
sudo systemctl status debai
```

## Configuration

### User Configuration

Create or edit `~/.config/debai/config.yaml`:

```yaml
general:
  log_level: info

agents:
  max_concurrent: 5
  auto_start: true

models:
  default: llama3.2:3b
```

### System Configuration

Edit `/etc/debai/config.yaml` for system-wide settings (requires root).

## Troubleshooting

### Docker Permission Denied

If you get "Permission denied" errors with Docker:

```bash
sudo usermod -aG docker $USER
newgrp docker  # Or log out and back in
```

### GTK/GUI Not Working

Install additional GTK dependencies:

```bash
sudo apt install -y \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    python3-gi \
    python3-gi-cairo
```

### Models Not Pulling

Check Docker status:

```bash
# Check if Docker is running
sudo systemctl status docker

# Check Docker Model Runner
docker ps | grep model
```

### Import Errors

Ensure all Python dependencies are installed:

```bash
pip install -r requirements.txt
```

## Upgrading

### Debian Package

```bash
# Download new version
wget https://github.com/manalejandro/debai/releases/latest/download/debai_1.0.0-1_all.deb

# Upgrade
sudo dpkg -i debai_1.0.0-1_all.deb
```

### pip

```bash
pip install --upgrade debai
```

### From Source

```bash
cd debai
git pull
pip install -e .
```

## Uninstallation

### Debian Package

```bash
# Remove package
sudo apt remove debai

# Remove package and configuration
sudo apt purge debai
```

### pip

```bash
pip uninstall debai
```

### Clean Up Data

```bash
# Remove user data (optional)
rm -rf ~/.config/debai
rm -rf ~/.local/share/debai

# Remove system data (requires root)
sudo rm -rf /var/lib/debai
sudo rm -rf /etc/debai
```

## Next Steps

After installation:

1. **Pull a Model**: `debai model pull llama3.2:3b`
2. **Create an Agent**: `debai agent create --template package_updater`
3. **Launch GUI**: `debai-gui`
4. Read the [User Guide](USER_GUIDE.md)

## Getting Help

- 📚 [Documentation](https://debai.readthedocs.io)
- 🐛 [Issue Tracker](https://github.com/manalejandro/debai/issues)
- 💬 [Discussions](https://github.com/manalejandro/debai/discussions)
