from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
import threading

from asset_scanner.config import APIConfig


class TaskPriority(Enum):
    HIGH = auto()    # Config files and core PBOs
    MEDIUM = auto()  # Content PBOs
    LOW = auto()     # Optional content

class TaskStatus(Enum):
    PENDING = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class ScanTask:
    """Represents a single scanning task"""
    path: Path
    priority: TaskPriority
    task_type: str  # 'pbo', 'config', 'asset'
    source: str
    dependencies: Optional[Set[Path]] = None
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)  # Fixed: Use field with default_factory
    
    def __post_init__(self) -> None:
        if self.dependencies is None:
            self.dependencies = set()
        
class TaskManager:
    """Manages scan tasks with priority and dependencies"""
    
    def __init__(self, max_workers: int = None, config: Optional[APIConfig] = None):
        self.tasks: Dict[Path, ScanTask] = {}
        self.active_tasks: Set[Path] = set()
        self.max_workers = max_workers
        self.config = config or APIConfig()
        self._pbo_count = 0
        self._lock = threading.Lock()
    
    def add_task(self, task: ScanTask) -> bool:
        """Add task if within limits"""
        with self._lock:
            if task.task_type == 'pbo':
                if self.config.pbo_limit and self._pbo_count >= self.config.pbo_limit:
                    return False
                self._pbo_count += 1
                
            self.tasks[task.path] = task
            return True
        
    def get_next_tasks(self, limit: int = None) -> List[ScanTask]:
        """Get next batch of tasks that can be processed"""
        with self._lock:
            available = []
            
            # First get all pending tasks
            pending = [
                task for task in self.tasks.values() 
                if task.status == TaskStatus.PENDING
            ]
            
            # Filter only tasks with no pending dependencies
            for task in pending:
                if task.path not in self.active_tasks:
                    # Check if any dependencies are still pending or processing
                    deps_ready = True
                    if task.dependencies:
                        for dep in task.dependencies:
                            if (dep in self.tasks and 
                                self.tasks[dep].status not in 
                                {TaskStatus.COMPLETED, TaskStatus.FAILED}):
                                deps_ready = False
                                break
                                
                    if deps_ready:
                        available.append(task)
            
            # Sort by priority (HIGH before MEDIUM before LOW)
            available.sort(key=lambda t: t.priority.value)
            
            if limit:
                available = available[:limit]
                
            # Mark selected tasks as active
            for task in available:
                self.active_tasks.add(task.path)
                task.status = TaskStatus.PROCESSING
                task.start_time = datetime.now()
                
            return available
        
    def complete_task(self, path: Path, error: str = None, failed: bool = False) -> None:
        """Mark a task as completed or failed with proper locking and status transition"""
        with self._lock:
            if path in self.tasks:
                task = self.tasks[path]
                # Only update if task is still processing or pending
                if task.status in {TaskStatus.PROCESSING, TaskStatus.PENDING}:
                    task.end_time = datetime.now()
                    task.error = error
                    task.status = TaskStatus.FAILED if (error is not None or failed) else TaskStatus.COMPLETED
                
                # Always remove from active tasks if present
                if path in self.active_tasks:
                    self.active_tasks.remove(path)
                    
    def get_stats(self) -> Dict[TaskStatus, int]:
        """Get task processing statistics with proper typing"""
        with self._lock:
            stats = {status: 0 for status in TaskStatus}
            for task in self.tasks.values():
                stats[task.status] += 1
            return stats
          