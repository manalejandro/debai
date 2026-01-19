"""
System information and resource monitoring module for Debai.

This module provides utilities for gathering system information and
monitoring resource usage.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class CPUInfo:
    """CPU information."""
    
    model: str
    cores_physical: int
    cores_logical: int
    frequency_mhz: float
    usage_percent: float
    temperature: Optional[float] = None


@dataclass
class MemoryInfo:
    """Memory information."""
    
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent_used: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent_used: float


@dataclass
class DiskInfo:
    """Disk information for a partition."""
    
    device: str
    mountpoint: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float


@dataclass
class NetworkInfo:
    """Network interface information."""
    
    interface: str
    ip_address: str
    mac_address: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


@dataclass
class ProcessInfo:
    """Process information."""
    
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float
    memory_bytes: int
    status: str
    created: datetime


class SystemInfo:
    """
    Gathers system information.
    """
    
    @staticmethod
    def get_hostname() -> str:
        """Get the system hostname."""
        return platform.node()
    
    @staticmethod
    def get_os_info() -> dict[str, str]:
        """Get operating system information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }
    
    @staticmethod
    def get_distro_info() -> dict[str, str]:
        """Get Linux distribution information."""
        info = {
            "name": "",
            "version": "",
            "codename": "",
            "id": "",
        }
        
        try:
            # Try /etc/os-release first
            os_release = Path("/etc/os-release")
            if os_release.exists():
                for line in os_release.read_text().splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip('"')
                        if key == "NAME":
                            info["name"] = value
                        elif key == "VERSION_ID":
                            info["version"] = value
                        elif key == "VERSION_CODENAME":
                            info["codename"] = value
                        elif key == "ID":
                            info["id"] = value
        except Exception as e:
            logger.warning(f"Error reading distro info: {e}")
        
        return info
    
    @staticmethod
    def get_cpu_info() -> CPUInfo:
        """Get CPU information."""
        freq = psutil.cpu_freq()
        
        # Get CPU model
        model = ""
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":")[1].strip()
                        break
        except Exception:
            model = platform.processor()
        
        # Get temperature if available
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp = entries[0].current
                        break
        except Exception:
            pass
        
        return CPUInfo(
            model=model,
            cores_physical=psutil.cpu_count(logical=False) or 1,
            cores_logical=psutil.cpu_count(logical=True) or 1,
            frequency_mhz=freq.current if freq else 0,
            usage_percent=psutil.cpu_percent(interval=0.1),
            temperature=temp,
        )
    
    @staticmethod
    def get_memory_info() -> MemoryInfo:
        """Get memory information."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return MemoryInfo(
            total_bytes=mem.total,
            available_bytes=mem.available,
            used_bytes=mem.used,
            percent_used=mem.percent,
            swap_total_bytes=swap.total,
            swap_used_bytes=swap.used,
            swap_percent_used=swap.percent,
        )
    
    @staticmethod
    def get_disk_info() -> list[DiskInfo]:
        """Get disk information for all partitions."""
        disks = []
        
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append(DiskInfo(
                    device=partition.device,
                    mountpoint=partition.mountpoint,
                    filesystem=partition.fstype,
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                    percent_used=usage.percent,
                ))
            except (PermissionError, OSError):
                continue
        
        return disks
    
    @staticmethod
    def get_network_info() -> list[NetworkInfo]:
        """Get network interface information."""
        interfaces = []
        
        addrs = psutil.net_if_addrs()
        stats = psutil.net_io_counters(pernic=True)
        
        for name, addr_list in addrs.items():
            if name == "lo":
                continue
            
            ip_addr = ""
            mac_addr = ""
            
            for addr in addr_list:
                if addr.family.name == "AF_INET":
                    ip_addr = addr.address
                elif addr.family.name == "AF_PACKET":
                    mac_addr = addr.address
            
            io = stats.get(name)
            
            interfaces.append(NetworkInfo(
                interface=name,
                ip_address=ip_addr,
                mac_address=mac_addr,
                bytes_sent=io.bytes_sent if io else 0,
                bytes_recv=io.bytes_recv if io else 0,
                packets_sent=io.packets_sent if io else 0,
                packets_recv=io.packets_recv if io else 0,
            ))
        
        return interfaces
    
    @staticmethod
    def get_uptime() -> float:
        """Get system uptime in seconds."""
        return datetime.now().timestamp() - psutil.boot_time()
    
    @staticmethod
    def get_uptime_string() -> str:
        """Get human-readable uptime string."""
        uptime = SystemInfo.get_uptime()
        
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        
        return " ".join(parts)
    
    @staticmethod
    def get_load_average() -> tuple[float, float, float]:
        """Get system load average (1, 5, 15 minutes)."""
        return os.getloadavg()
    
    @staticmethod
    def get_logged_users() -> list[str]:
        """Get list of logged-in users."""
        users = []
        for user in psutil.users():
            users.append(f"{user.name}@{user.terminal}")
        return users
    
    @staticmethod
    def get_summary() -> dict[str, Any]:
        """Get a summary of system information."""
        return {
            "hostname": SystemInfo.get_hostname(),
            "os": SystemInfo.get_os_info(),
            "distro": SystemInfo.get_distro_info(),
            "cpu": SystemInfo.get_cpu_info().__dict__,
            "memory": SystemInfo.get_memory_info().__dict__,
            "uptime": SystemInfo.get_uptime_string(),
            "load_average": SystemInfo.get_load_average(),
        }


class ResourceMonitor:
    """
    Monitors system resources continuously.
    """
    
    def __init__(
        self,
        interval_seconds: float = 5.0,
        history_size: int = 100,
    ):
        self.interval = interval_seconds
        self.history_size = history_size
        self.history: list[dict[str, Any]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: list[callable] = []
        
        # Thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "load_1min": psutil.cpu_count() or 1,
        }
        self._alerts: list[dict[str, Any]] = []
    
    def on_update(self, callback: callable) -> None:
        """Register a callback for updates."""
        self._callbacks.append(callback)
    
    def set_threshold(self, metric: str, value: float) -> None:
        """Set a threshold for a metric."""
        self.thresholds[metric] = value
    
    async def start(self) -> None:
        """Start the resource monitor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitor started")
    
    async def stop(self) -> None:
        """Stop the resource monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitor stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                snapshot = self._take_snapshot()
                self._add_to_history(snapshot)
                self._check_thresholds(snapshot)
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(snapshot)
                    except Exception as e:
                        logger.error(f"Error in monitor callback: {e}")
                
                await asyncio.sleep(self.interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(1)
    
    def _take_snapshot(self) -> dict[str, Any]:
        """Take a resource snapshot."""
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        load = os.getloadavg()
        
        # Get top processes by CPU
        top_cpu = []
        for proc in sorted(
            psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
            key=lambda p: p.info.get('cpu_percent', 0) or 0,
            reverse=True,
        )[:5]:
            try:
                info = proc.info
                top_cpu.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": info['cpu_percent'],
                    "memory_percent": info['memory_percent'],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_available_mb": mem.available / (1024 * 1024),
            "load_1min": load[0],
            "load_5min": load[1],
            "load_15min": load[2],
            "top_processes": top_cpu,
        }
    
    def _add_to_history(self, snapshot: dict[str, Any]) -> None:
        """Add a snapshot to history."""
        self.history.append(snapshot)
        if len(self.history) > self.history_size:
            self.history.pop(0)
    
    def _check_thresholds(self, snapshot: dict[str, Any]) -> None:
        """Check thresholds and generate alerts."""
        alerts = []
        
        if snapshot["cpu_percent"] > self.thresholds["cpu_percent"]:
            alerts.append({
                "type": "cpu",
                "message": f"CPU usage is {snapshot['cpu_percent']:.1f}%",
                "value": snapshot["cpu_percent"],
                "threshold": self.thresholds["cpu_percent"],
            })
        
        if snapshot["memory_percent"] > self.thresholds["memory_percent"]:
            alerts.append({
                "type": "memory",
                "message": f"Memory usage is {snapshot['memory_percent']:.1f}%",
                "value": snapshot["memory_percent"],
                "threshold": self.thresholds["memory_percent"],
            })
        
        if snapshot["load_1min"] > self.thresholds["load_1min"]:
            alerts.append({
                "type": "load",
                "message": f"Load average is {snapshot['load_1min']:.2f}",
                "value": snapshot["load_1min"],
                "threshold": self.thresholds["load_1min"],
            })
        
        if alerts:
            for alert in alerts:
                alert["timestamp"] = snapshot["timestamp"]
            self._alerts.extend(alerts)
            
            # Keep only recent alerts
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]
    
    def get_latest(self) -> Optional[dict[str, Any]]:
        """Get the latest snapshot."""
        return self.history[-1] if self.history else None
    
    def get_history(self, count: int = 0) -> list[dict[str, Any]]:
        """Get recent history."""
        if count <= 0:
            return list(self.history)
        return list(self.history[-count:])
    
    def get_alerts(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent alerts."""
        return list(self._alerts[-count:])
    
    def get_average(self, metric: str, minutes: int = 5) -> Optional[float]:
        """Get average value of a metric over a time period."""
        if not self.history:
            return None
        
        # Calculate how many samples to use
        samples_per_minute = 60 / self.interval
        samples = int(samples_per_minute * minutes)
        
        recent = self.history[-samples:] if samples < len(self.history) else self.history
        values = [s.get(metric, 0) for s in recent if metric in s]
        
        return sum(values) / len(values) if values else None
    
    def get_statistics(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        if not self.history:
            return {}
        
        cpu_values = [s["cpu_percent"] for s in self.history]
        mem_values = [s["memory_percent"] for s in self.history]
        
        return {
            "samples": len(self.history),
            "interval_seconds": self.interval,
            "cpu": {
                "current": cpu_values[-1],
                "average": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
            },
            "memory": {
                "current": mem_values[-1],
                "average": sum(mem_values) / len(mem_values),
                "max": max(mem_values),
                "min": min(mem_values),
            },
            "alerts_count": len(self._alerts),
        }


def format_bytes(size: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def get_docker_status() -> dict[str, Any]:
    """Get Docker status."""
    result = {
        "installed": False,
        "running": False,
        "version": "",
        "containers": 0,
        "images": 0,
    }
    
    try:
        # Check if docker is installed
        version = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
        )
        if version.returncode == 0:
            result["installed"] = True
            result["version"] = version.stdout.strip()
        
        # Check if docker is running
        info = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
        )
        if info.returncode == 0:
            result["running"] = True
            import json
            data = json.loads(info.stdout)
            result["containers"] = data.get("Containers", 0)
            result["images"] = data.get("Images", 0)
    
    except Exception as e:
        logger.debug(f"Error checking Docker status: {e}")
    
    return result


def check_dependencies() -> dict[str, bool]:
    """Check if required dependencies are available."""
    deps = {
        "docker": False,
        "docker-model": False,
        "cagent": False,
        "qemu-img": False,
        "genisoimage": False,
    }
    
    # Common binary locations
    search_paths = [
        Path.home() / ".local" / "bin",
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/libexec/docker/cli-plugins"),
    ]
    
    # Also add PATH entries
    path_env = os.environ.get("PATH", "")
    for path_entry in path_env.split(":"):
        if path_entry:
            search_paths.append(Path(path_entry))
    
    for dep in deps:
        # Try which first
        try:
            result = subprocess.run(
                ["which", dep],
                capture_output=True,
            )
            if result.returncode == 0:
                deps[dep] = True
                continue
        except Exception:
            pass
        
        # Manual search in common locations
        for search_path in search_paths:
            binary_path = search_path / dep
            if binary_path.exists() and os.access(binary_path, os.X_OK):
                deps[dep] = True
                break
    
    return deps
