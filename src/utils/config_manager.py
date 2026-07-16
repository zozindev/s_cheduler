import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from src.models.task import Task

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "s_cheduler_config.json")
MAX_RESULT_LENGTH = 10000


class ConfigManager:
    """JSON 설정 파일 관리 및 스케줄 조회를 담당하는 클래스."""

    def __init__(self, config_path: Optional[str] = None):
        path = config_path or DEFAULT_CONFIG_PATH
        self.config_path = os.path.abspath(os.path.normpath(path))
        self.tasks: List[Task] = []
        self._lock = threading.RLock()
        self._ensure_config_exists()
        self.load_config()

    def _ensure_config_exists(self):
        """설정 파일이 없으면 초기 폴더와 빈 파일을 생성합니다."""
        directory = os.path.dirname(self.config_path) or "."
        os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.config_path):
            self.save_config([])
            logger.info("초기 설정 파일 생성 완료: %s", self.config_path)

    @staticmethod
    def _truncate(value: Any) -> str:
        text = str(value or "")
        if len(text) > MAX_RESULT_LENGTH:
            return text[:MAX_RESULT_LENGTH] + "\n... (내용이 너무 길어 일부 생략됨)"
        return text

    @classmethod
    def _read_tasks_from_file(cls, path: str) -> List[Task]:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("설정 파일의 최상위 구조는 작업 목록이어야 합니다.")

        tasks: List[Task] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                logger.warning("설정 파일 %d번째 항목을 건너뜁니다: 객체가 아닙니다.", index)
                continue
            try:
                task = Task.from_dict(item)
                if not task.task_name:
                    raise ValueError("작업명이 비어 있습니다.")
                tasks.append(task)
            except (TypeError, ValueError, KeyError) as error:
                logger.error("설정 파일 %d번째 작업을 건너뜁니다: %s", index, error)
        return tasks

    def load_config(self) -> List[Task]:
        """JSON 파일을 읽어 Task 객체 리스트로 변환합니다."""
        try:
            tasks = self._read_tasks_from_file(self.config_path)
        except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError) as error:
            logger.error("설정 파일 로드 실패: %s", error)
            with self._lock:
                self.tasks = []
            return self.tasks

        with self._lock:
            self.tasks = tasks
            return list(self.tasks)

    def save_config(self, tasks: Optional[List[Task]] = None) -> bool:
        """설정을 임시 파일에 저장한 뒤 원자적으로 교체합니다."""
        with self._lock:
            if tasks is not None:
                self.tasks = list(tasks)

            directory = os.path.dirname(self.config_path) or "."
            os.makedirs(directory, exist_ok=True)
            temp_path = None
            try:
                file_descriptor, temp_path = tempfile.mkstemp(
                    prefix=".s_cheduler_",
                    suffix=".tmp",
                    dir=directory,
                )
                with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
                    json.dump(
                        [task.to_dict() for task in self.tasks],
                        file,
                        indent=4,
                        ensure_ascii=False,
                    )
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temp_path, self.config_path)
                return True
            except Exception as error:
                logger.error("설정 파일 저장 실패: %s", error)
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                return False

    def add_task(self, task: Task) -> bool:
        """새 작업을 추가하고 저장합니다."""
        with self._lock:
            if any(existing.task_name == task.task_name for existing in self.tasks):
                logger.warning("작업 이름 중복: %s", task.task_name)
                return False

            task.file_path = os.path.normpath(task.file_path)
            self.tasks.append(task)
            if not self.save_config():
                self.tasks.pop()
                return False
            logger.info("작업 추가 완료: %s", task.task_name)
            return True

    def update_task(self, original_name: str, task: Task) -> bool:
        """작업을 교체하고 저장합니다."""
        with self._lock:
            if any(
                existing.task_name == task.task_name and existing.task_name != original_name
                for existing in self.tasks
            ):
                return False

            for index, existing in enumerate(self.tasks):
                if existing.task_name == original_name:
                    task.file_path = os.path.normpath(task.file_path)
                    self.tasks[index] = task
                    if not self.save_config():
                        self.tasks[index] = existing
                        return False
                    return True
        return False

    def delete_task(self, task_name: str) -> bool:
        """작업을 삭제하고 저장합니다."""
        with self._lock:
            original_tasks = list(self.tasks)
            self.tasks = [task for task in self.tasks if task.task_name != task_name]
            if len(original_tasks) == len(self.tasks):
                return False
            if not self.save_config():
                self.tasks = original_tasks
                return False
            return True

    def set_task_enabled(self, task_name: str, enabled: bool) -> bool:
        """작업의 예약 활성화 상태를 변경합니다."""
        with self._lock:
            task = next((item for item in self.tasks if item.task_name == task_name), None)
            if task is None:
                return False
            previous = task.enabled
            task.enabled = bool(enabled)
            if not self.save_config():
                task.enabled = previous
                return False
            return True

    def get_next_run_datetime(self, task: Task, now: Optional[datetime] = None) -> Optional[datetime]:
        """활성 작업의 다음 일일 실행 시각을 반환합니다."""
        if not task.enabled:
            return None

        current = now or datetime.now()
        try:
            task_time = datetime.strptime(task.execution_time, "%H:%M").time()
        except (TypeError, ValueError):
            logger.error("잘못된 시간 형식: %s (%s)", task.task_name, task.execution_time)
            return None

        target = current.replace(
            hour=task_time.hour,
            minute=task_time.minute,
            second=0,
            microsecond=0,
        )
        if target <= current:
            target += timedelta(days=1)
        return target

    def get_next_task(self, exclude_task_names: Optional[Set[str]] = None) -> Optional[Task]:
        """현재 시각 기준으로 가장 빨리 실행되어야 할 작업을 찾습니다."""
        excluded = exclude_task_names or set()
        with self._lock:
            candidates = [
                task
                for task in self.tasks
                if task.enabled and task.task_name not in excluded
            ]

        scheduled = [
            (task, next_run)
            for task in candidates
            if (next_run := self.get_next_run_datetime(task)) is not None
        ]
        if not scheduled:
            return None
        return min(scheduled, key=lambda item: item[1])[0]

    def get_tasks_at_time(
        self,
        execution_time: str,
        exclude_task_names: Optional[Set[str]] = None,
    ) -> List[Task]:
        """같은 실행 시각의 활성 작업을 원래 등록 순서대로 반환합니다."""
        excluded = exclude_task_names or set()
        with self._lock:
            return [
                task
                for task in self.tasks
                if task.enabled
                and task.execution_time == execution_time
                and task.task_name not in excluded
            ]

    def update_task_result(self, task_name: str, result: Dict[str, Any]) -> bool:
        """작업의 최근 실행 결과와 상세 정보를 저장합니다."""
        with self._lock:
            task = next((item for item in self.tasks if item.task_name == task_name), None)
            if task is None:
                return False

            task.last_run_status = "Success" if result.get("success") else "Fail"
            task.last_run_time = datetime.now().isoformat(timespec="seconds")
            task.last_run_return_code = result.get("return_code")
            task.last_run_output = self._truncate(result.get("output"))
            task.last_run_error = self._truncate(result.get("error"))
            try:
                task.last_run_duration_seconds = round(float(result.get("duration_seconds", 0)), 2)
            except (TypeError, ValueError):
                task.last_run_duration_seconds = None
            return self.save_config()

    def update_task_status(self, task_name: str, status: str):
        """이전 호출부와의 호환성을 위한 상태 업데이트 메서드."""
        self.update_task_result(
            task_name,
            {
                "success": status == "Success",
                "return_code": 0 if status == "Success" else -1,
                "output": "",
                "error": "",
                "duration_seconds": 0,
            },
        )

    def export_config(self, destination_path: str) -> bool:
        """현재 설정을 다른 JSON 파일로 복사합니다."""
        destination = os.path.abspath(os.path.normpath(destination_path))
        if destination == self.config_path:
            return True
        try:
            directory = os.path.dirname(destination) or "."
            os.makedirs(directory, exist_ok=True)
            if not self.save_config():
                return False
            shutil.copy2(self.config_path, destination)
            return True
        except (OSError, shutil.Error) as error:
            logger.error("설정 내보내기 실패: %s", error)
            return False

    def import_config(self, source_path: str) -> bool:
        """외부 JSON 설정을 검증한 뒤 현재 설정으로 복원합니다."""
        source = os.path.abspath(os.path.normpath(source_path))
        try:
            imported_tasks = self._read_tasks_from_file(source)
        except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError) as error:
            logger.error("설정 가져오기 실패: %s", error)
            return False

        return self.save_config(imported_tasks)
