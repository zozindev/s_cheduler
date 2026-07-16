import logging
import os
import subprocess
import sys
import threading
import time
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def detach_to_pythonw_if_needed():
    if os.name != "nt":
        return

    if os.environ.get("SCHEDULER_DETACHED") == "1":
        return

    executable_name = os.path.basename(sys.executable).lower()
    if executable_name != "python.exe":
        return

    pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw_path):
        print("pythonw.exe를 찾을 수 없어 콘솔 모드로 실행합니다.")
        return

    env = os.environ.copy()
    env["SCHEDULER_DETACHED"] = "1"
    creation_flags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )

    subprocess.Popen(
        [pythonw_path, os.path.abspath(__file__), *sys.argv[1:]],
        cwd=BASE_DIR,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )
    sys.exit(0)


os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

log_handlers = [
    logging.FileHandler(os.path.join(BASE_DIR, "logs", "scheduler.log"), encoding="utf-8")
]
if os.environ.get("SCHEDULER_DETACHED") != "1":
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("MainLoop")

from src.core.executor import TaskExecutor
from src.core.power_manager import PowerManager
from src.gui_manager import GUIManager
from src.models.task import Task
from src.utils.config_manager import ConfigManager
from src.utils.notification_manager import NotificationSystem


class SchedulerEngine:
    """백그라운드에서 스케줄을 감시하고 작업을 실행하는 엔진."""

    def __init__(self, cm: ConfigManager, pm: PowerManager, ex: TaskExecutor, ns: NotificationSystem):
        self.cm = cm
        self.pm = pm
        self.ex = ex
        self.ns = ns
        self._stop_event = threading.Event()
        self._completed_today = set()
        self._completed_date = date.today()
        self._pending_same_time = None

    def _reset_daily_progress_if_needed(self):
        today = date.today()
        if today != self._completed_date:
            self._completed_today.clear()
            self._completed_date = today
            self._pending_same_time = None

    @staticmethod
    def _task_signature(task: Task):
        return (
            task.task_name,
            task.execution_time,
            os.path.normpath(task.file_path),
            task.wakeup_enabled,
            task.enabled,
            task.timeout_minutes,
            tuple(task.recipients),
        )

    def _get_next_task(self):
        """같은 시각에 등록된 작업을 순차 실행할 수 있도록 다음 작업을 찾습니다."""
        self._reset_daily_progress_if_needed()

        if self._pending_same_time:
            same_time_tasks = self.cm.get_tasks_at_time(
                self._pending_same_time,
                exclude_task_names=self._completed_today,
            )
            if same_time_tasks:
                return same_time_tasks[0], True
            self._pending_same_time = None

        return (
            self.cm.get_next_task(exclude_task_names=self._completed_today),
            False,
        )

    def run(self):
        logger.info("스케줄링 엔진 시작...")

        while not self._stop_event.is_set():
            try:
                task, run_immediately = self._get_next_task()

                if not task:
                    self.pm.cancel_timer()
                    logger.info("등록된 작업이 없거나 오늘 작업을 모두 실행했습니다. 30초 후 재확인합니다.")
                    self._stop_event.wait(30)
                    continue

                now = datetime.now()
                if run_immediately:
                    target_datetime = now
                else:
                    target_datetime = self.cm.get_next_run_datetime(task, now)
                    if target_datetime is None:
                        self._stop_event.wait(2)
                        continue

                wait_seconds = max(0, (target_datetime - now).total_seconds())
                logger.info(
                    "다음 작업: [%s] - 실행 예정: %s (%s초 후)",
                    task.task_name,
                    target_datetime,
                    int(wait_seconds),
                )

                if run_immediately or wait_seconds <= 30:
                    self.pm.cancel_timer()
                else:
                    self.pm.set_wakeup_timer(
                        int(wait_seconds - 10),
                        enabled=task.wakeup_enabled,
                    )

                last_tick_time = time.monotonic()
                last_check_time = last_tick_time
                is_modified = False

                while wait_seconds > 0 and not self._stop_event.is_set():
                    if self._stop_event.wait(min(1, wait_seconds)):
                        break

                    current_time = time.monotonic()
                    wait_seconds = max(0, wait_seconds - (current_time - last_tick_time))
                    last_tick_time = current_time

                    # 2초마다 최신 스케줄을 확인합니다. 현재 시각을 다시 기록해
                    # 시스템 시간 변경에도 대기 시간이 누적 오차를 만들지 않게 합니다.
                    if current_time - last_check_time >= 2:
                        last_check_time = current_time
                        new_task, new_run_immediately = self._get_next_task()
                        if (
                            not new_task
                            or self._task_signature(new_task) != self._task_signature(task)
                            or new_run_immediately != run_immediately
                        ):
                            logger.info("스케줄 변경이 감지되어 대기를 갱신합니다.")
                            is_modified = True
                            self.pm.cancel_timer()
                            break

                if is_modified or self._stop_event.is_set():
                    continue

                logger.info("작업 실행 시작: %s", task.task_name)
                result = self.ex.execute(
                    task.file_path,
                    timeout_seconds=task.timeout_minutes * 60,
                )
                self.cm.update_task_result(task.task_name, result)
                self._completed_today.add(task.task_name)
                self._pending_same_time = task.execution_time

                logger.info("알림 발송 시도: %s", task.task_name)
                self.ns.send_report(task.task_name, result, recipients=task.recipients)
                logger.info("알림 발송 호출 완료: %s", task.task_name)

                self._stop_event.wait(5)

            except Exception as error:
                logger.exception("스케줄링 엔진 실행 중 오류 발생: %s", error)
                self._stop_event.wait(10)

    def stop(self):
        self._stop_event.set()
        self.pm.cancel_timer()


def main():
    try:
        cm = ConfigManager()
        pm = PowerManager()
        ex = TaskExecutor()
        ns = NotificationSystem()
    except Exception as error:
        print(f"초기화 중 치명적 오류 발생: {error}")
        return

    engine = SchedulerEngine(cm, pm, ex, ns)
    engine_thread = threading.Thread(target=engine.run, daemon=True)
    engine_thread.start()

    try:
        gui = GUIManager(cm, pm, ex, ns)
        logger.info("GUI 시작...")
        gui.run()
    except Exception as error:
        logger.exception("GUI 실행 중 오류 발생: %s", error)
    finally:
        logger.info("프로그램 종료 중...")
        engine.stop()


if __name__ == "__main__":
    detach_to_pythonw_if_needed()
    main()
