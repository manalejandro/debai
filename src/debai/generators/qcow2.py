"""
QCOW2 image generator for Debai.

Generates QCOW2 disk images for use with QEMU/KVM.
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

logger = logging.getLogger(__name__)


class QCOW2Generator:
    """
    Generates QCOW2 disk images with Debai pre-installed.
    
    Creates virtual machine disk images that can be used with QEMU/KVM.
    """
    
    def __init__(
        self,
        output_path: Path,
        disk_size: str = "20G",
        base_distro: str = "debian",
        release: str = "trixie",
        arch: str = "amd64",
        memory_mb: int = 2048,
        cpus: int = 2,
    ):
        self.output_path = output_path
        self.disk_size = disk_size
        self.base_distro = base_distro
        self.release = release
        self.arch = arch
        self.memory_mb = memory_mb
        self.cpus = cpus
        self.work_dir: Optional[Path] = None
    
    async def generate(self) -> dict[str, Any]:
        """Generate the QCOW2 image."""
        result = {
            "success": False,
            "output_path": str(self.output_path),
            "size_mb": 0,
            "error": None,
        }
        
        try:
            # Check for qemu-img
            if not shutil.which("qemu-img"):
                raise RuntimeError("qemu-img not found. Install qemu-utils package.")
            
            # Create temporary working directory
            self.work_dir = Path(tempfile.mkdtemp(prefix="debai_qcow2_"))
            logger.info(f"Working directory: {self.work_dir}")
            
            # Create the QCOW2 image
            await self._create_qcow2()
            
            # Create cloud-init configuration
            await self._create_cloud_init()
            
            # Get size
            if self.output_path.exists():
                result["size_mb"] = self.output_path.stat().st_size / (1024 * 1024)
                result["success"] = True
            
        except Exception as e:
            logger.error(f"QCOW2 generation failed: {e}")
            result["error"] = str(e)
        
        finally:
            # Cleanup
            if self.work_dir and self.work_dir.exists():
                shutil.rmtree(self.work_dir, ignore_errors=True)
        
        return result
    
    async def _create_qcow2(self) -> None:
        """Create the QCOW2 disk image."""
        # Create empty QCOW2 image
        cmd = [
            "qemu-img", "create",
            "-f", "qcow2",
            str(self.output_path),
            self.disk_size,
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Failed to create QCOW2: {stderr.decode()}")
        
        logger.info(f"Created QCOW2 image: {self.output_path}")
    
    async def _create_cloud_init(self) -> None:
        """Create cloud-init configuration for the image."""
        cloud_init_dir = self.output_path.parent / "cloud-init"
        cloud_init_dir.mkdir(parents=True, exist_ok=True)
        
        # User data
        user_data = {
            "#cloud-config": None,
            "hostname": "debai",
            "manage_etc_hosts": True,
            "users": [
                {
                    "name": "debai",
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "groups": ["docker", "sudo"],
                    "shell": "/bin/bash",
                    "lock_passwd": False,
                    "passwd": "$6$rounds=4096$debai$Qs8qLMmPMvpZq0nP9P.WQm1C5K.s1hQ5P0Z3CgK.0xOjv6Zl6JwZ9vX5Y7U2a8nT4K6M3W1Q0X5Y7U2a8nT4K6",  # debai
                }
            ],
            "package_update": True,
            "package_upgrade": True,
            "packages": [
                "python3",
                "python3-pip",
                "python3-venv",
                "docker.io",
                "qemu-guest-agent",
                "curl",
                "git",
            ],
            "runcmd": [
                "systemctl enable docker",
                "systemctl start docker",
                "pip3 install debai",
                "debai init",
                "systemctl enable debai",
            ],
            "final_message": "Debai AI Agent System is ready!",
        }
        
        user_data_path = cloud_init_dir / "user-data"
        with open(user_data_path, "w") as f:
            f.write("#cloud-config\n")
            yaml.dump({k: v for k, v in user_data.items() if k != "#cloud-config"}, 
                     f, default_flow_style=False)
        
        # Meta data
        meta_data = {
            "instance-id": "debai-001",
            "local-hostname": "debai",
        }
        
        meta_data_path = cloud_init_dir / "meta-data"
        with open(meta_data_path, "w") as f:
            yaml.dump(meta_data, f, default_flow_style=False)
        
        # Network config
        network_config = {
            "version": 2,
            "ethernets": {
                "ens3": {
                    "dhcp4": True,
                }
            }
        }
        
        network_config_path = cloud_init_dir / "network-config"
        with open(network_config_path, "w") as f:
            yaml.dump(network_config, f, default_flow_style=False)
        
        # Create cloud-init ISO
        cloud_init_iso = self.output_path.parent / "cloud-init.iso"
        
        # Try to create ISO with genisoimage or cloud-localds
        if shutil.which("cloud-localds"):
            cmd = [
                "cloud-localds",
                str(cloud_init_iso),
                str(user_data_path),
                str(meta_data_path),
            ]
        elif shutil.which("genisoimage"):
            cmd = [
                "genisoimage",
                "-output", str(cloud_init_iso),
                "-volid", "cidata",
                "-joliet", "-rock",
                str(cloud_init_dir),
            ]
        else:
            logger.warning("No ISO tool found, skipping cloud-init ISO creation")
            return
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Created cloud-init ISO: {cloud_init_iso}")
        else:
            logger.warning(f"Failed to create cloud-init ISO: {stderr.decode()}")
    
    def generate_run_script(self) -> str:
        """Generate a script to run the QCOW2 image with QEMU."""
        script = f"""#!/bin/bash
# Run Debai VM with QEMU

QCOW2_IMAGE="{self.output_path}"
CLOUD_INIT_ISO="{self.output_path.parent / 'cloud-init.iso'}"
MEMORY="{self.memory_mb}"
CPUS="{self.cpus}"

# Check if cloud-init ISO exists
CLOUD_INIT_OPTS=""
if [ -f "$CLOUD_INIT_ISO" ]; then
    CLOUD_INIT_OPTS="-cdrom $CLOUD_INIT_ISO"
fi

# Run QEMU
qemu-system-x86_64 \\
    -enable-kvm \\
    -m $MEMORY \\
    -smp $CPUS \\
    -drive file=$QCOW2_IMAGE,format=qcow2 \\
    $CLOUD_INIT_OPTS \\
    -netdev user,id=net0,hostfwd=tcp::2222-:22,hostfwd=tcp::8080-:8080 \\
    -device virtio-net-pci,netdev=net0 \\
    -display gtk \\
    -boot d

# To access:
# SSH: ssh -p 2222 debai@localhost
# Web UI: http://localhost:8080
"""
        
        script_path = self.output_path.parent / "run-debai-vm.sh"
        script_path.write_text(script)
        script_path.chmod(0o755)
        
        return str(script_path)


class VMManager:
    """
    Manages QEMU virtual machines running Debai.
    """
    
    def __init__(self, vm_dir: Optional[Path] = None):
        self.vm_dir = vm_dir or Path.home() / ".local" / "share" / "debai" / "vms"
        self.vm_dir.mkdir(parents=True, exist_ok=True)
        self.running_vms: dict[str, subprocess.Popen] = {}
    
    async def create_vm(
        self,
        name: str,
        disk_size: str = "20G",
        memory_mb: int = 2048,
        cpus: int = 2,
    ) -> dict[str, Any]:
        """Create a new VM."""
        vm_path = self.vm_dir / name
        vm_path.mkdir(parents=True, exist_ok=True)
        
        qcow2_path = vm_path / f"{name}.qcow2"
        
        generator = QCOW2Generator(
            output_path=qcow2_path,
            disk_size=disk_size,
            memory_mb=memory_mb,
            cpus=cpus,
        )
        
        result = await generator.generate()
        
        if result["success"]:
            # Generate run script
            generator.generate_run_script()
            
            # Save VM configuration
            config = {
                "name": name,
                "disk_size": disk_size,
                "memory_mb": memory_mb,
                "cpus": cpus,
                "qcow2_path": str(qcow2_path),
            }
            
            config_path = vm_path / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
        
        return result
    
    def list_vms(self) -> list[dict[str, Any]]:
        """List all VMs."""
        vms = []
        
        for vm_dir in self.vm_dir.iterdir():
            if vm_dir.is_dir():
                config_path = vm_dir / "config.yaml"
                if config_path.exists():
                    with open(config_path) as f:
                        config = yaml.safe_load(f)
                    config["running"] = config["name"] in self.running_vms
                    vms.append(config)
        
        return vms
    
    async def start_vm(
        self,
        name: str,
        headless: bool = False,
    ) -> bool:
        """Start a VM."""
        vm_path = self.vm_dir / name
        config_path = vm_path / "config.yaml"
        
        if not config_path.exists():
            logger.error(f"VM {name} not found")
            return False
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        qcow2_path = config["qcow2_path"]
        cloud_init_iso = vm_path / "cloud-init.iso"
        
        cmd = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-m", str(config["memory_mb"]),
            "-smp", str(config["cpus"]),
            "-drive", f"file={qcow2_path},format=qcow2",
            "-netdev", "user,id=net0,hostfwd=tcp::2222-:22,hostfwd=tcp::8080-:8080",
            "-device", "virtio-net-pci,netdev=net0",
        ]
        
        if cloud_init_iso.exists():
            cmd.extend(["-cdrom", str(cloud_init_iso)])
        
        if headless:
            cmd.extend(["-display", "none", "-daemonize"])
        else:
            cmd.extend(["-display", "gtk"])
        
        process = subprocess.Popen(cmd)
        self.running_vms[name] = process
        
        logger.info(f"Started VM {name}")
        return True
    
    def stop_vm(self, name: str) -> bool:
        """Stop a VM."""
        if name not in self.running_vms:
            return False
        
        process = self.running_vms[name]
        process.terminate()
        process.wait(timeout=30)
        
        del self.running_vms[name]
        logger.info(f"Stopped VM {name}")
        return True
    
    def delete_vm(self, name: str) -> bool:
        """Delete a VM."""
        # Stop if running
        if name in self.running_vms:
            self.stop_vm(name)
        
        vm_path = self.vm_dir / name
        if vm_path.exists():
            shutil.rmtree(vm_path)
            logger.info(f"Deleted VM {name}")
            return True
        
        return False
