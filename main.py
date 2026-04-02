import os
import time
import threading
import logging
from datetime import datetime, timedelta

# 필수 디렉토리 생성 (오류 방지)
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

from src.core.power_manager import PowerManager
from src.core.executor import TaskExecutor
from src.utils.config_manager import ConfigManager
from src.utils.mail_sender import NotificationSystem
from src.gui_manager import GUIManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MainLoop")

class SchedulerEngine:
    """백그라운드에서 스케줄을 감시하고 작업을 실행하는 엔진"""

    def __init__(self, cm: ConfigManager, pm: PowerManager, ex: TaskExecutor, ns: NotificationSystem):
        self.cm = cm
        self.pm = pm
        self.ex = ex
        self.ns = ns
        self.running = True

    def run(self):
        """스케줄링 메인 루프"""
        logger.info("스케줄링 엔진 시작...")
        
        while self.running:
            try:
                task = self.cm.get_next_task()
                
                if not task:
                    logger.info("등록된 작업이 없습니다. 1분 후 재확인합니다.")
                    time.sleep(60)
                    continue

                # 실행 시간 계산
                now = datetime.now()
                target_time = datetime.strptime(task.execution_time, "%H:%M")
                target_datetime = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)

                # 이미 지난 시간이라면 내일로 설정
                if target_datetime <= now:
                    target_datetime += timedelta(days=1)

                wait_seconds = (target_datetime - now).total_seconds()
                
                logger.info(f"다음 작업: [{task.task_name}] - 실행 예정: {target_datetime} ({int(wait_seconds)}초 후)")

                # 웨이크업 타이머 설정 (작업 시작 10초 전으로 설정하여 여유 확보)
                if wait_seconds > 30:
                    self.pm.set_wakeup_timer(int(wait_seconds - 10), enabled=task.wakeup_enabled)
                
                # 대기 (10초 단위로 쪼개서 대기하여 프로그램 종료에 즉각 반응)
                while wait_seconds > 0 and self.running:
                    sleep_time = min(10, wait_seconds)
                    time.sleep(sleep_time)
                    wait_seconds -= sleep_time
                    
                    # 도중에 스케줄이 바뀌었을 수도 있으므로 루프를 빠져나가서 다시 get_next_task() 실행
                    # 하지만 여기서는 단순화를 위해 wait_seconds가 0이 될 때까지 대기
                
                if not self.running:
                    break

                # 작업 실행
                logger.info(f"작업 실행 시작: {task.task_name}")
                result = self.ex.execute(task.file_path)
                
                # 상태 업데이트
                status = "Success" if result["success"] else "Fail"
                self.cm.update_task_status(task.task_name, status)
                
                # 이메일 알림 발송 (비동기 처리 권장되나 여기서는 동기 처리)
                self.ns.send_report(task.task_name, result, recipients=task.recipients)
                
                # 다음 작업을 위해 짧은 휴식 (중복 실행 방지용 Jitter)
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"스케줄링 엔진 실행 중 오류 발생: {e}")
                time.sleep(10) # 오류 발생 시 잠시 대기 후 재시도

    def stop(self):
        self.running = False
        self.pm.cancel_timer()

def main():
    # 1. 모듈 초기화
    try:
        cm = ConfigManager()
        pm = PowerManager()
        ex = TaskExecutor()
        ns = NotificationSystem()
    except Exception as e:
        print(f"초기화 중 치명적 오류 발생: {e}")
        return
    
    # 2. 스케줄링 엔진을 백그라운드 스레드에서 실행
    engine = SchedulerEngine(cm, pm, ex, ns)
    engine_thread = threading.Thread(target=engine.run, daemon=True)
    engine_thread.start()

    # 3. GUI 실행 (메인 스레드)
    try:
        gui = GUIManager(cm, pm)
        logger.info("GUI 시작...")
        gui.run()
    except Exception as e:
        logger.error(f"GUI 실행 중 오류 발생: {e}")
    finally:
        logger.info("프로그램 종료 중...")
        engine.stop()

if __name__ == "__main__":
    main()
