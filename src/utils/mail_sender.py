import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

# 환경 변수 로드 (.env 파일)
load_dotenv()

logger = logging.getLogger(__name__)

class NotificationSystem:
    """Gmail SMTP를 사용하여 작업 실행 결과를 이메일로 알리는 클래스"""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        # 설정 확인
        if not self.gmail_user or not self.gmail_password:
            logger.warning("SMTP 계정 정보가 설정되지 않았습니다. .env 파일을 확인하세요.")

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
        if not self.gmail_user or not self.gmail_password:
            logger.error("SMTP 계정 정보 부족으로 이메일을 보낼 수 없습니다.")
            return False

        # 수신자가 없으면 자기 자신(GMAIL_USER)에게 발송
        if not recipients:
            recipients = [self.gmail_user]

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
        msg = MIMEMultipart()
        msg['From'] = self.gmail_user
        msg['To'] = ", ".join(recipients)  # 여러 수신자 표시
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 4. SMTP 서버 접속 및 발송
        try:
            # SMTP 서버 연결
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.set_debuglevel(0)
            server.starttls()  # TLS 보안 연결 시작
            
            # 로그인 및 발송
            server.login(self.gmail_user, self.gmail_password)
            server.send_message(msg, from_addr=self.gmail_user, to_addrs=recipients)
            server.quit()
            
            logger.info(f"이메일 알림 전송 완료: {task_name} ({status_str}) -> {recipients}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP 인증 실패: 계정 이름 또는 앱 비밀번호를 확인하세요.")
        except Exception as e:
            logger.error(f"이메일 전송 중 오류 발생: {str(e)}")
        
        return False

# 모듈 독립 테스트 (계정 정보가 설정된 경우에만 실행 권장)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ns = NotificationSystem()
    # 가상의 결과 데이터로 테스트
    test_result = {
        "success": True,
        "return_code": 0,
        "output": "테스트 실행 성공 메시지",
        "error": ""
    }
    # ns.send_report("Test_Task", test_result)
