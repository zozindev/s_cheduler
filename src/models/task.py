from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Task:
    """스케줄링할 작업의 정보를 담는 데이터 클래스"""
    task_name: str
    execution_time: str  # HH:MM 형식
    file_path: str       # 실행할 파일의 절대 경로
    wakeup_enabled: bool = True  # 절전 모드 해제 여부
    recipients: List[str] = field(default_factory=list)
    last_run_status: str = "Not Started"
    last_run_time: Optional[str] = None
    enabled: bool = True
    timeout_minutes: int = 30
    last_run_return_code: Optional[int] = None
    last_run_output: str = ""
    last_run_error: str = ""
    last_run_duration_seconds: Optional[float] = None

    def __post_init__(self):
        if self.recipients is None:
            self.recipients = []
        elif isinstance(self.recipients, str):
            self.recipients = [self.recipients]
        else:
            self.recipients = [str(recipient).strip() for recipient in self.recipients if str(recipient).strip()]

        try:
            self.timeout_minutes = max(1, int(self.timeout_minutes))
        except (TypeError, ValueError):
            self.timeout_minutes = 30

        self.enabled = bool(self.enabled)
        self.wakeup_enabled = bool(self.wakeup_enabled)

        if self.last_run_return_code is not None:
            try:
                self.last_run_return_code = int(self.last_run_return_code)
            except (TypeError, ValueError):
                self.last_run_return_code = None

        if self.last_run_duration_seconds is not None:
            try:
                self.last_run_duration_seconds = float(self.last_run_duration_seconds)
            except (TypeError, ValueError):
                self.last_run_duration_seconds = None

    def to_dict(self):
        """JSON 저장을 위해 사전(dict) 형태로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """JSON 데이터로부터 Task 객체 생성"""
        # 이전 버전에서 저장된 JSON에는 새 필드가 없을 수 있으므로
        # 명시적으로 필드를 골라 하위 호환성을 유지합니다.
        return cls(
            task_name=str(data.get("task_name", "")).strip(),
            execution_time=str(data.get("execution_time", "")).strip(),
            file_path=str(data.get("file_path", "")).strip(),
            wakeup_enabled=data.get("wakeup_enabled", True),
            recipients=data.get("recipients") or [],
            last_run_status=str(data.get("last_run_status", "Not Started")),
            last_run_time=data.get("last_run_time"),
            enabled=data.get("enabled", True),
            timeout_minutes=data.get("timeout_minutes", 30),
            last_run_return_code=data.get("last_run_return_code"),
            last_run_output=str(data.get("last_run_output", "") or ""),
            last_run_error=str(data.get("last_run_error", "") or ""),
            last_run_duration_seconds=data.get("last_run_duration_seconds"),
        )
