"""Resource limit enforcement for sandbox execution."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from patchgoblin.sandbox.models import SandboxConfig


@dataclass
class ResourceUsage:
    """Measured resource usage from a sandbox run."""

    cpu_time_seconds: float
    wall_time_seconds: float
    memory_mb: float
    disk_mb: float
    process_count: int
    killed_by_limit: bool = False
    limit_reason: str | None = None


class ResourceLimitError(Exception):
    """Raised when a resource limit is exceeded."""


class ResourceLimiter:
    """Enforces resource limits on subprocess execution."""

    def __init__(self, config: SandboxConfig):
        """Initialize with sandbox configuration."""
        self._config = config
        self._start_time: float | None = None
        self._process_start_time: float | None = None

    def start_timing(self) -> None:
        """Start timing the execution."""
        self._start_time = time.time()
        self._process_start_time = time.process_time()

    def get_usage(self, workspace_path: Path) -> ResourceUsage:
        """Get current resource usage."""
        if self._start_time is None or self._process_start_time is None:
            raise RuntimeError("Timing not started")

        wall_time = time.time() - self._start_time
        cpu_time = time.process_time() - self._process_start_time

        # Estimate memory and disk usage (platform-specific)
        memory_mb = self._estimate_memory_usage()
        disk_mb = self._estimate_disk_usage(workspace_path)
        process_count = self._count_processes()

        return ResourceUsage(
            cpu_time_seconds=cpu_time,
            wall_time_seconds=wall_time,
            memory_mb=memory_mb,
            disk_mb=disk_mb,
            process_count=process_count,
        )

    def check_limits(self, usage: ResourceUsage) -> None:
        """Check if resource limits have been exceeded."""
        if usage.cpu_time_seconds > self._config.max_cpu_time_seconds:
            raise ResourceLimitError(
                f"CPU time limit exceeded: {usage.cpu_time_seconds:.2f}s > "
                f"{self._config.max_cpu_time_seconds:.2f}s"
            )

        if usage.wall_time_seconds > self._config.max_wall_time_seconds:
            raise ResourceLimitError(
                f"Wall time limit exceeded: {usage.wall_time_seconds:.2f}s > "
                f"{self._config.max_wall_time_seconds:.2f}s"
            )

        if usage.memory_mb > self._config.max_memory_mb:
            raise ResourceLimitError(
                f"Memory limit exceeded: {usage.memory_mb:.2f}MB > {self._config.max_memory_mb}MB"
            )

        if usage.disk_mb > self._config.max_disk_mb:
            raise ResourceLimitError(
                f"Disk limit exceeded: {usage.disk_mb:.2f}MB > {self._config.max_disk_mb}MB"
            )

        if usage.process_count > self._config.max_processes:
            raise ResourceLimitError(
                f"Process count limit exceeded: {usage.process_count} > "
                f"{self._config.max_processes}"
            )

    def _estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            # Fallback: return a conservative estimate
            return 100.0

    def _estimate_disk_usage(self, workspace_path: Path) -> float:
        """Estimate disk usage of workspace in MB."""
        try:
            total_size = 0
            for item in workspace_path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
            return total_size / (1024 * 1024)
        except Exception:
            return 0.0

    def _count_processes(self) -> int:
        """Count current number of processes."""
        try:
            import os

            import psutil

            current_process = psutil.Process(os.getpid())
            return len(current_process.children(recursive=True))
        except ImportError:
            return 1
