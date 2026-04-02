import subprocess
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TaskExecutor:
    """배치 파일(.bat) 및 실행 파일(.exe)을 실행하고 결과를 수집하는 클래스"""

    def execute(self, file_path: str) -> Dict[str, Any]:
        """
        지정된 파일을 실행하고 결과를 반환합니다.
        
        Args:
            file_path (str): 실행할 파일의 절대 경로
            
        Returns:
            dict: {
                "success": bool,
                "return_code": int,
                "output": str,
                "error": str
            }
        """
        # 경로 정규화
        normalized_path = os.path.normpath(file_path)
        
        # 파일 존재 여부 확인
        if not os.path.exists(normalized_path):
            error_msg = f"파일을 찾을 수 없습니다: {normalized_path}"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": error_msg
            }

        logger.info(f"작업 실행 시작: {normalized_path}")

        try:
            # subprocess.run을 사용하여 프로세스 실행
            # shell=True: .bat 파일 실행 및 환경 변수 확장에 필요
            # capture_output=True: stdout, stderr를 캡처
            # text=True: 출력을 문자열로 변환
            result = subprocess.run(
                normalized_path,
                shell=True,
                capture_output=True,
                text=True,
                check=False  # 에러 발생 시 예외를 던지는 대신 return_code 확인
            )

            success = result.returncode == 0
            
            if success:
                logger.info(f"작업 실행 성공: {normalized_path}")
            else:
                logger.error(f"작업 실행 실패 (코드: {result.returncode}): {normalized_path}")

            return {
                "success": success,
                "return_code": result.returncode,
                "output": result.stdout.strip(),
                "error": result.stderr.strip()
            }

        except Exception as e:
            error_msg = f"작업 실행 중 예외 발생: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": error_msg
            }

# 모듈 독립 테스트
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor = TaskExecutor()
    # 예시: 현재 디렉토리 목록 출력 명령 실행 테스트 (OS 독립적)
    test_command = "dir" if os.name == "nt" else "ls"
    res = executor.execute(test_command)
    print(res)
