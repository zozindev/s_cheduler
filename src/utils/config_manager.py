import json
import os
import logging
from datetime import datetime, time
from typing import List, Optional
from src.models.task import Task

logger = logging.getLogger(__name__)

class ConfigManager:
    """JSON 설정 파일 관리 및 스케줄 조회를 담당하는 클래스"""

    def __init__(self, config_path: str = "data/s_cheduler_config.json"):
        self.config_path = os.path.normpath(config_path)
        self.tasks: List[Task] = []
        self._ensure_config_exists()
        self.load_config()

    def _ensure_config_exists(self):
        """설정 파일이 없으면 초기 폴더와 빈 파일을 생성합니다."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        if not os.path.exists(self.config_path):
            self.save_config([])
            logger.info(f"초기 설정 파일 생성 완료: {self.config_path}")

    def load_config(self) -> List[Task]:
        """JSON 파일을 읽어 Task 객체 리스트로 변환합니다."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(item) for item in data]
            return self.tasks
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return []

    def save_config(self, tasks: Optional[List[Task]] = None):
        """현재 작업 목록을 JSON 파일로 저장합니다."""
        if tasks is not None:
            self.tasks = tasks
        
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json_data = [task.to_dict() for task in self.tasks]
                json.dump(json_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")

    def add_task(self, task: Task):
        """새 작업을 추가하고 저장합니다 (중복 이름은 무시)."""
        if any(t.task_name == task.task_name for t in self.tasks):
            logger.warning(f"작업 이름 중복: {task.task_name}")
            return
        
        # 경로 정규화 (윈도우 스타일 처리)
        task.file_path = os.path.normpath(task.file_path)
        self.tasks.append(task)
        self.save_config()
        logger.info(f"작업 추가 완료: {task.task_name}")

    def get_next_task(self) -> Optional[Task]:
        """현재 시각 기준으로 가장 빨리 실행되어야 할 작업을 찾습니다."""
        # GUI와 메모리를 공유하므로 매번 파일을 읽을 필요가 없습니다.
        # 초기 로딩은 __init__에서 수행됩니다.
        
        if not self.tasks:
            return None

        now = datetime.now().time()
        
        # 1. 오늘 실행 가능한 작업 중 가장 빠른 것 찾기
        future_tasks = []
        for task in self.tasks:
            try:
                task_time = datetime.strptime(task.execution_time, "%H:%M").time()
                if task_time > now:
                    future_tasks.append((task, task_time))
            except ValueError:
                logger.error(f"잘못된 시간 형식: {task.task_name} ({task.execution_time})")

        if future_tasks:
            # 시간순으로 정렬 후 첫 번째 작업 반환
            future_tasks.sort(key=lambda x: x[1])
            return future_tasks[0][0]

        # 2. 오늘 남은 작업이 없다면 내일 첫 번째 작업 반환
        all_tasks = []
        for task in self.tasks:
            try:
                task_time = datetime.strptime(task.execution_time, "%H:%M").time()
                all_tasks.append((task, task_time))
            except ValueError:
                continue
        
        if all_tasks:
            all_tasks.sort(key=lambda x: x[1])
            return all_tasks[0][0]

        return None

    def update_task_status(self, task_name: str, status: str):
        """작업 실행 후 상태와 시간을 업데이트합니다."""
        for task in self.tasks:
            if task.task_name == task_name:
                task.last_run_status = status
                task.last_run_time = datetime.now().isoformat()
                self.save_config()
                break
