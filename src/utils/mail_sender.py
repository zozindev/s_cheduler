import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

# 환경 변수 로드 (.env 파일)
try:
    load_dotenv()
except ImportError:
    # python-dotenv가 없는 경우 환경 변수만 사용
    pass

logger = logging.getLogger(__name__)

class NotificationSystem:
    """Gmail SMTP를 사용하여 작업 실행 결과를 이메일로 알리는 클래스"""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        # .env 파일 존재 여부 확인 및 로드
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            load_result = load_dotenv(env_path)
            if load_result:
                logger.info("환경 설정 파일(.env) 로드 성공")
            else:
                logger.warning("환경 설정 파일(.env)은 존재하지만 로드에 실패했습니다.")
        else:
            logger.warning(f"환경 설정 파일(.env)을 찾을 수 없습니다. 경로: {env_path}")

        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        # 설정 확인 및 상세 안내
        missing_vars = []
        if not self.gmail_user:
            missing_vars.append("GMAIL_USER")
        if not self.gmail_password:
            missing_vars.append("GMAIL_APP_PASSWORD")
            
        if not missing_vars:
            logger.info(f"이메일 알림 시스템 준비 완료 (계정: {self.gmail_user})")
        else:
            logger.error(f"이메일 발송 설정이 누락되었습니다: {', '.join(missing_vars)}")
            logger.error("루트 디렉토리에 .env 파일을 생성하고 GMAIL_USER와 GMAIL_APP_PASSWORD(앱 비밀번호 16자리)를 입력하세요.")

    def send_report(self, task_name: str, result: Dict[str, Any], recipients: list = None) -> bool:
        """
        작업 실행 결과를 이메일로 전송합니다.
        
        Args:
            task_name (str): 실행된 작업의 이름
            result (dict): TaskExecutor.execute()가 반환한 결과 딕셔너리
            recipients (list): 수신 이메일 주소 리스트
            
        Returns:
            bool: 이메일 전송 성공 여부
        """
        logger.info(f"이메일 발송 프로세스 시작: {task_name}")
        
        if not self.gmail_user or not self.gmail_password:
            logger.error("SMTP 계정 정보 부족으로 이메일을 보낼 수 없습니다. (.env 파일에 GMAIL_USER, GMAIL_APP_PASSWORD를 설정했는지 확인하세요.)")
            return False

        # 수신자 목록 정제
        actual_recipients = []
        if recipients:
            # 유효한 문자열 이메일만 추출
            actual_recipients = [r for r in recipients if r and isinstance(r, str) and "@" in r]
        
        # 유효한 수신자가 없으면 자기 자신(GMAIL_USER)에게 발송
        if not actual_recipients:
            logger.info(f"유효한 수신자가 지정되지 않아 기본 계정({self.gmail_user})으로 발송합니다.")
            actual_recipients = [self.gmail_user]

        success = result.get("success", False)
        status_str = "성공" if success else "실패"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. 메일 제목 설정
        subject = f"[슼케줄러] 작업 {status_str} 알림: {task_name}"
        
        # 2. 메일 본문 구성 (HTML 대신 일반 텍스트 사용)
        body = f"""
안녕하세요, 슼케줄러 알림입니다.

예약된 작업이 실행되었습니다.

-----------------------------------------
■ 작업명: {task_name}
■ 상태: {status_str}
■ 실행 시각: {timestamp}
■ 반환 코드: {result.get('return_code')}
-----------------------------------------

"""
        if success:
            body += f"■ 상세 출력:\n{result.get('output', '내용 없음')}\n"
        else:
            body += f"■ 에러 메시지:\n{result.get('error', '내용 없음')}\n"

        body += "\n감사합니다."

        # 3. MIME 메시지 생성
        try:
            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = ", ".join(actual_recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        except Exception as e:
            logger.error(f"메일 메시지 생성 중 오류 발생: {e}")
            return False

        # 4. SMTP 서버 접속 및 발송
        try:
            logger.info(f"SMTP 서버({self.smtp_server}) 접속 시도...")
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            server.set_debuglevel(0)
            server.starttls()  # TLS 보안 연결 시작
            
            logger.info(f"SMTP 로그인 시도: {self.gmail_user}")
            server.login(self.gmail_user, self.gmail_password)
            server.send_message(msg, from_addr=self.gmail_user, to_addrs=actual_recipients)
            server.quit()
            
            logger.info(f"이메일 알림 전송 완료: {task_name} ({status_str}) -> {actual_recipients}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP 인증 실패: 계정 이름 또는 앱 비밀번호(16자리)를 확인하세요.")
        except Exception as e:
            logger.error(f"이메일 전송 중 오류 발생: {str(e)}")
        
        return False

# 모듈 독립 테스트
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ns = NotificationSystem()
    test_result = {
        "success": True,
        "return_code": 0,
        "output": "테스트 실행 성공 메시지",
        "error": ""
    }
    # ns.send_report("Test_Task", test_result)
