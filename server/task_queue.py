"""轻量级异步任务队列

使用 Python threading + 内存队列实现，无需引入 Celery 等重量级依赖。
适合单实例部署场景下的异步报告生成。

用法：
    from task_queue import task_manager
    
    task_id = task_manager.submit(my_function, arg1=val1)
    status  = task_manager.get_status(task_id)
"""

import uuid
import threading
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """单个异步任务"""

    def __init__(self, task_id: str, func: Callable, kwargs: dict):
        self.task_id = task_id
        self.func = func
        self.kwargs = kwargs
        self.status = TaskStatus.PENDING
        self.progress: int = 0
        self.message: str = ""
        self.result: Any = None
        self.error: Optional[str] = None
        self.created_at: str = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskManager:
    """任务管理器（线程安全）"""

    def __init__(self, max_workers: int = 2):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_workers)

    def submit(self, func: Callable, **kwargs) -> str:
        """提交异步任务，立即返回 task_id"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(task_id, func, kwargs)

        with self._lock:
            self._tasks[task_id] = task

        thread = threading.Thread(target=self._run_task, args=(task,), daemon=True)
        thread.start()
        return task_id

    def get_status(self, task_id: str) -> Optional[dict]:
        """查询任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()

    def update_progress(self, task_id: str, progress: int, message: str = ""):
        """任务内部调用：更新进度"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.progress = progress
                task.message = message

    def list_tasks(self, limit: int = 20) -> list[dict]:
        """列出最近的任务"""
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def _run_task(self, task: Task):
        """在后台线程中执行任务"""
        self._semaphore.acquire()
        try:
            with self._lock:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()

            # 将 task_id 注入 kwargs，方便任务函数内调用 update_progress
            task.kwargs["_task_id"] = task.task_id
            task.kwargs["_task_manager"] = self

            result = task.func(**task.kwargs)

            with self._lock:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.result = result
                task.completed_at = datetime.now().isoformat()
        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.message = traceback.format_exc()
                task.completed_at = datetime.now().isoformat()
        finally:
            self._semaphore.release()

    def cleanup(self, max_age_hours: int = 24):
        """清理过期任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self._lock:
            expired = [
                tid for tid, t in self._tasks.items()
                if t.completed_at and datetime.fromisoformat(t.completed_at) < cutoff
            ]
            for tid in expired:
                del self._tasks[tid]


# 全局单例
task_manager = TaskManager(max_workers=2)
