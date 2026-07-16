import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaskExecutor:
    """실행 파일과 스크립트를 실행하고 결과를 수집하는 클래스."""

    DEFAULT_TIMEOUT_SECONDS = 30 * 60
    MAX_OUTPUT_CHARS = 10000

    @staticmethod
    def _as_text(value: Optional[Any]) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value)

    @classmethod
    def _limit_output(cls, value: Optional[Any]) -> str:
        text = cls._as_text(value)
        if len(text) > cls.MAX_OUTPUT_CHARS:
            return text[:cls.MAX_OUTPUT_CHARS] + "\n... (출력이 너무 길어 일부 생략됨)"
        return text

    @staticmethod
    def _build_command(normalized_path: str):
        extension = os.path.splitext(normalized_path)[1].lower()
        if extension in (".bat", ".cmd"):
            # cmd.exe가 필요한 배치 파일만 명시적으로 cmd를 사용합니다.
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", normalized_path]
        if extension == ".py":
            return [sys.executable, normalized_path]
        if extension == ".ps1":
            return [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                normalized_path,
            ]
        return [normalized_path]

    def execute(
        self,
        file_path: str,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """작업을 실행합니다. 기본 제한 시간은 30분입니다."""
        normalized_path = os.path.abspath(os.path.normpath(file_path))
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        started_at = time.perf_counter()

        if not os.path.isfile(normalized_path):
            error_msg = f"파일을 찾을 수 없습니다: {normalized_path}"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": error_msg,
                "duration_seconds": 0,
                "timed_out": False,
            }

        command = self._build_command(normalized_path)
        logger.info("작업 실행 시작: %s", normalized_path)

        try:
            result = subprocess.run(
                command,
                shell=False,
                cwd=os.path.dirname(normalized_path) or None,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            duration = round(time.perf_counter() - started_at, 2)
            success = result.returncode == 0

            if success:
                logger.info("작업 실행 성공: %s", normalized_path)
            else:
                logger.error("작업 실행 실패 (코드: %s): %s", result.returncode, normalized_path)

            return {
                "success": success,
                "return_code": result.returncode,
                "output": self._limit_output(result.stdout).strip(),
                "error": self._limit_output(result.stderr).strip(),
                "duration_seconds": duration,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as error:
            duration = round(time.perf_counter() - started_at, 2)
            timeout_minutes = max(1, round(timeout / 60))
            error_msg = f"실행시간 {timeout_minutes}분 초과: 작업을 종료했습니다."
            logger.error("%s (%s)", error_msg, normalized_path)
            return {
                "success": False,
                "return_code": -2,
                "output": self._limit_output(error.stdout).strip(),
                "error": error_msg,
                "duration_seconds": duration,
                "timed_out": True,
            }
        except (OSError, ValueError) as error:
            duration = round(time.perf_counter() - started_at, 2)
            error_msg = f"작업 실행 중 오류 발생: {error}"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": error_msg,
                "duration_seconds": duration,
                "timed_out": False,
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor = TaskExecutor()
    print(executor.execute(sys.executable))
