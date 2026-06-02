import os
import logging
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

# 상세 로그 설정
logger = logging.getLogger(__name__)

class NotificationSystem:
    """이메일(SMTP) 및 MS Teams(Webhook)를 지원하는 알림 시스템"""

    def __init__(self):
        # .env 파일 로드 (프로젝트 루트 기준으로 절대 경로 생성)
        # 이 파일(notification_manager.py)은 src/utils/에 있으므로 상위의 상위가 루트임
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(base_dir, ".env")
        
        if os.path.exists(env_path):
            load_result = load_dotenv(env_path)
            if load_result:
                logger.info(f"환경 설정 파일(.env) 로드 완료: {env_path}")
            else:
                logger.warning(f"환경 설정 파일(.env)은 존재하지만 로드에 실패했습니다: {env_path}")
        else:
            logger.warning(f"환경 설정 파일(.env)을 찾을 수 없습니다. 경로: {env_path}")
        
        # 1. Teams 설정 (권장: HTTPS 기반이라 방화벽에 안전함)
        self.teams_webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        
        # 2. Email 설정 (SMTP: 사내 방화벽에서 막힐 수 있음)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        # 초기 상태 로그
        if self.teams_webhook_url:
            logger.info("MS Teams 알림 준비 완료 (Webhook 사용)")
        elif self.gmail_user and self.gmail_password:
            logger.info(f"이메일 알림 준비 완료 (계정: {self.gmail_user})")
        else:
            logger.warning("알림 시스템 설정(Teams 또는 Email)이 누락되었습니다. .env 파일을 확인하세요.")

    def send_report(self, task_name: str, result: Dict[str, Any], recipients: list = None) -> bool:
        """작업 결과를 알림 매체(Teams 우선, 실패 시 Email)로 전송합니다."""
        
        # 1. Teams Webhook 발송 시도 (가장 먼저 시도)
        if self.teams_webhook_url:
            return self._send_to_teams(task_name, result)
        
        # 2. Teams가 설정 안 된 경우 이메일 발송 시도
        if self.gmail_user and self.gmail_password:
            return self._send_to_email(task_name, result, recipients)

        logger.error("알림 발송 수단(Teams URL 또는 Email 계정)이 없습니다.")
        return False

    def _send_to_teams(self, task_name: str, result: Dict[str, Any]) -> bool:
        """Power Automate Workflows 웹훅을 사용하여 Teams 알림을 보냅니다.
        
        Note: 2026년 4월 30일부로 기존 Office 365 Connector(Incoming Webhook)가 
        완전 폐기되어, Adaptive Card 형식의 Workflows 웹훅으로 마이그레이션됨.
        .env의 TEAMS_WEBHOOK_URL을 Workflows에서 생성한 새 URL로 교체해야 합니다.
        """
        success = result.get("success", False)
        status_str = "성공 ✅" if success else "실패 ❌"
        status_color = "Good" if success else "Attention"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        output_text = result.get("output") or result.get("error") or "결과 없음"
        # Adaptive Card 본문이 너무 길어지지 않도록 자르기
        if len(str(output_text)) > 500:
            output_text = str(output_text)[:500] + "... (생략됨)"

        # Power Automate Workflows용 Adaptive Card 페이로드
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Large",
                                "weight": "Bolder",
                                "text": "📢 슼케줄러 알림",
                                "wrap": True
                            },
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "작업 이름",
                                                "weight": "Bolder",
                                                "wrap": True
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": "상태",
                                                "weight": "Bolder",
                                                "wrap": True
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": "실행 시각",
                                                "weight": "Bolder",
                                                "wrap": True
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": task_name,
                                                "wrap": True
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": status_str,
                                                "color": status_color,
                                                "wrap": True
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": timestamp,
                                                "wrap": True
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "type": "TextBlock",
                                "text": f"**실행 결과:**\n{output_text}",
                                "wrap": True,
                                "separator": True
                            }
                        ]
                    }
                }
            ]
        }

        try:
            logger.info(f"Teams 알림 전송 시도 (Adaptive Card): {task_name}")
            response = requests.post(
                self.teams_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            # Workflows 웹훅은 성공 시 202 Accepted를 반환할 수도 있음
            if response.status_code in (200, 202):
                logger.info(f"Teams 알림 전송 완료: {task_name}")
                return True
            else:
                logger.error(f"Teams 알림 실패 (HTTP {response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"Teams 알림 전송 중 오류 발생: {e}")
            return False

    def _send_to_email(self, task_name: str, result: Dict[str, Any], recipients: list = None) -> bool:
        """기존 이메일(SMTP) 발송 로직"""
        # (기존 mail_sender.py의 코드를 그대로 유지하여 대체 수단으로 사용)
        actual_recipients = recipients or [self.gmail_user]
        success = result.get("success", False)
        status_str = "성공" if success else "실패"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        subject = f"[슼케줄러] 작업 {status_str} 알림: {task_name}"
        body = f"안녕하세요, 슼케줄러입니다.\n\n작업: {task_name}\n상태: {status_str}\n시각: {timestamp}\n\n결과:\n{result.get('output') or result.get('error')}"

        try:
            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = ", ".join(actual_recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            server.starttls()
            server.login(self.gmail_user, self.gmail_password)
            server.send_message(msg)
            server.quit()
            logger.info(f"이메일 알림 전송 완료: {task_name}")
            return True
        except Exception as e:
            logger.error(f"이메일 전송 중 오류 발생: {e} (사내 보안 정책상 SMTP가 차단되었을 수 있습니다.)")
            return False
