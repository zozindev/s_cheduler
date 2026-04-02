from dataclasses import dataclass, asdict
from typing import Optional
import datetime

@dataclass
class Task:
    """스케줄링할 작업의 정보를 담는 데이터 클래스"""
    task_name: str
    execution_time: str  # HH:MM 형식
    file_path: str       # 실행할 파일의 절대 경로
    wakeup_enabled: bool = True  # 절전 모드 해제 여부
    recipients: list = None      # 수신 이메일 리스트 (기본값: [GMAIL_USER])
    last_run_status: str = "Not Started"
    last_run_time: Optional[str] = None

    def __post_init__(self):
        if self.recipients is None:
            self.recipients = []

    def to_dict(self):
        """JSON 저장을 위해 사전(dict) 형태로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        """JSON 데이터로부터 Task 객체 생성"""
        return cls(**data)
