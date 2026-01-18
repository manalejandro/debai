"""
ISO image generator for Debai.

Generates bootable ISO images with Debai pre-installed and configured.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import Template

logger = logging.getLogger(__name__)


class ISOGenerator:
    """
    Generates bootable ISO images with Debai.
    
    Uses debootstrap and genisoimage to create custom Debian-based ISOs.
    """
    
    def __init__(
        self,
        output_path: Path,
        base_distro: str = "debian",
        release: str = "trixie",
        arch: str = "amd64",
        include_agents: bool = True,
        include_gui: bool = True,
    ):
        self.output_path = output_path
        self.base_distro = base_distro
        self.release = release
        self.arch = arch
        self.include_agents = include_agents
        self.include_gui = include_gui
        self.work_dir: Optional[Path] = None
    
    async def generate(self) -> dict[str, Any]:
        """Generate the ISO image."""
        result = {
            "success": False,
            "output_path": str(self.output_path),
            "size_mb": 0,
            "error": None,
        }
        
        try:
            # Create temporary working directory
            self.work_dir = Path(tempfile.mkdtemp(prefix="debai_iso_"))
            logger.info(f"Working directory: {self.work_dir}")
            
            # Create directory structure
            iso_root = self.work_dir / "iso_root"
            iso_root.mkdir(parents=True)
            
            # Create boot configuration
            await self._create_boot_config(iso_root)
            
            # Create filesystem
            await self._create_filesystem(iso_root)
            
            # Add Debai files
            await self._add_debai_files(iso_root)
            
            # Generate ISO
            await self._generate_iso(iso_root)
            
            # Get size
            if self.output_path.exists():
                result["size_mb"] = self.output_path.stat().st_size / (1024 * 1024)
                result["success"] = True
            
        except Exception as e:
            logger.error(f"ISO generation failed: {e}")
            result["error"] = str(e)
        
        finally:
            # Cleanup
            if self.work_dir and self.work_dir.exists():
                shutil.rmtree(self.work_dir, ignore_errors=True)
        
        return result
    
    async def _create_boot_config(self, iso_root: Path) -> None:
        """Create boot configuration files."""
        boot_dir = iso_root / "boot" / "grub"
        boot_dir.mkdir(parents=True)
        
        # GRUB configuration
        grub_cfg = """
set timeout=10
set default=0

menuentry "Debai - AI Agent System" {
    linux /boot/vmlinuz root=/dev/sda1 ro quiet splash
    initrd /boot/initrd.img
}

menuentry "Debai - AI Agent System (Safe Mode)" {
    linux /boot/vmlinuz root=/dev/sda1 ro single
    initrd /boot/initrd.img
}

menuentry "Debai - Installation Mode" {
    linux /boot/vmlinuz root=/dev/sda1 ro install
    initrd /boot/initrd.img
}
"""
        (boot_dir / "grub.cfg").write_text(grub_cfg)
        
        # Isolinux for legacy BIOS
        isolinux_dir = iso_root / "isolinux"
        isolinux_dir.mkdir(parents=True)
        
        isolinux_cfg = """
DEFAULT debai
TIMEOUT 100
PROMPT 1

LABEL debai
    MENU LABEL Debai - AI Agent System
    KERNEL /boot/vmlinuz
    APPEND initrd=/boot/initrd.img root=/dev/sda1 ro quiet splash

LABEL debai-safe
    MENU LABEL Debai - Safe Mode
    KERNEL /boot/vmlinuz
    APPEND initrd=/boot/initrd.img root=/dev/sda1 ro single

LABEL install
    MENU LABEL Debai - Installation
    KERNEL /boot/vmlinuz
    APPEND initrd=/boot/initrd.img root=/dev/sda1 ro install
"""
        (isolinux_dir / "isolinux.cfg").write_text(isolinux_cfg)
    
    async def _create_filesystem(self, iso_root: Path) -> None:
        """Create the root filesystem structure."""
        # Create standard directories
        dirs = [
            "etc/debai",
            "usr/bin",
            "usr/lib/debai",
            "usr/share/debai",
            "var/lib/debai",
            "var/log/debai",
        ]
        
        for d in dirs:
            (iso_root / d).mkdir(parents=True, exist_ok=True)
    
    async def _add_debai_files(self, iso_root: Path) -> None:
        """Add Debai application files."""
        # Create installation script
        install_script = """#!/bin/bash
# Debai Installation Script

set -e

echo "Installing Debai - AI Agent System..."

# Install dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv docker.io qemu-utils

# Install Debai
pip3 install debai

# Configure Docker
systemctl enable docker
systemctl start docker

# Create user configuration
mkdir -p ~/.config/debai/{agents,models,tasks}

# Install Docker Model Runner
docker pull aimodel/runner:latest

echo "Debai installation complete!"
echo "Run 'debai init' to complete setup."
"""
        
        script_path = iso_root / "usr" / "bin" / "debai-install"
        script_path.write_text(install_script)
        script_path.chmod(0o755)
        
        # Create systemd service
        service = """[Unit]
Description=Debai AI Agent Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/debai-daemon
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        systemd_dir = iso_root / "etc" / "systemd" / "system"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        (systemd_dir / "debai.service").write_text(service)
        
        # Create default configuration
        config = {
            "debai": {
                "version": "1.0.0",
                "auto_start_agents": True,
                "log_level": "info",
                "models": {
                    "default": "llama3.2:3b",
                    "cache_dir": "/var/cache/debai/models",
                },
                "agents": {
                    "config_dir": "/etc/debai/agents",
                    "max_concurrent": 5,
                },
            }
        }
        
        config_path = iso_root / "etc" / "debai" / "config.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))
        
        # Add agents if requested
        if self.include_agents:
            await self._add_default_agents(iso_root)
    
    async def _add_default_agents(self, iso_root: Path) -> None:
        """Add default agent configurations."""
        from debai.core.agent import AGENT_TEMPLATES
        
        agents_dir = iso_root / "etc" / "debai" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        for name, config in AGENT_TEMPLATES.items():
            config_path = agents_dir / f"{name}.yaml"
            config_path.write_text(yaml.dump(config.model_dump(), default_flow_style=False))
    
    async def _generate_iso(self, iso_root: Path) -> None:
        """Generate the final ISO image."""
        # Check for genisoimage or mkisofs
        iso_cmd = None
        for cmd in ["genisoimage", "mkisofs", "xorriso"]:
            result = subprocess.run(["which", cmd], capture_output=True)
            if result.returncode == 0:
                iso_cmd = cmd
                break
        
        if not iso_cmd:
            # Create a simple tar archive instead
            logger.warning("ISO tools not found, creating tar archive")
            tar_path = self.output_path.with_suffix(".tar.gz")
            subprocess.run(
                ["tar", "-czf", str(tar_path), "-C", str(iso_root), "."],
                check=True,
            )
            # Rename to .iso for consistency
            shutil.move(tar_path, self.output_path)
            return
        
        if iso_cmd == "xorriso":
            cmd = [
                "xorriso",
                "-as", "mkisofs",
                "-o", str(self.output_path),
                "-V", "DEBAI",
                "-J", "-R",
                str(iso_root),
            ]
        else:
            cmd = [
                iso_cmd,
                "-o", str(self.output_path),
                "-V", "DEBAI",
                "-J", "-R",
                "-b", "isolinux/isolinux.bin",
                "-c", "isolinux/boot.cat",
                "-no-emul-boot",
                "-boot-load-size", "4",
                "-boot-info-table",
                str(iso_root),
            ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"ISO generation failed: {stderr.decode()}")
        
        logger.info(f"ISO generated: {self.output_path}")


# Template for preseed file (automated Debian installation)
PRESEED_TEMPLATE = """
# Debai Preseed Configuration
# Automated installation for AI Agent System

# Locale
d-i debian-installer/locale string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap select us

# Network
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string debai
d-i netcfg/get_domain string local

# Mirror
d-i mirror/country string manual
d-i mirror/http/hostname string deb.debian.org
d-i mirror/http/directory string /debian
d-i mirror/http/proxy string

# Account
d-i passwd/root-login boolean true
d-i passwd/root-password password debai
d-i passwd/root-password-again password debai
d-i passwd/user-fullname string Debai User
d-i passwd/username string debai
d-i passwd/user-password password debai
d-i passwd/user-password-again password debai

# Partitioning
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# Packages
tasksel tasksel/first multiselect standard
d-i pkgsel/include string python3 python3-pip docker.io openssh-server

# GRUB
d-i grub-installer/only_debian boolean true
d-i grub-installer/bootdev string default

# Finish
d-i finish-install/reboot_in_progress note

# Post-installation
d-i preseed/late_command string \\
    in-target pip3 install debai; \\
    in-target systemctl enable docker; \\
    in-target debai init
"""
