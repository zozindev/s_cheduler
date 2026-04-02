import unittest
import os
import json
import shutil
from datetime import datetime, timedelta
from src.utils.config_manager import ConfigManager
from src.models.task import Task

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        # 테스트 전용 임시 디렉토리 및 파일 설정
        self.test_dir = "tests/temp_data"
        self.config_path = os.path.join(self.test_dir, "test_config.json")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        self.cm = ConfigManager(config_path=self.config_path)

    def tearDown(self):
        # 테스트 후 임시 파일 삭제
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_add_and_save_task(self):
        """작업 추가 및 파일 저장 기능 테스트"""
        new_task = Task(
            task_name="TestTask1",
            execution_time="10:00",
            file_path="C:\\test.bat"
        )
        self.cm.add_task(new_task)
        
        # 파일이 실제로 생성되었는지 확인
        self.assertTrue(os.path.exists(self.config_path))
        
        # 저장된 데이터 로드 후 검증
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["task_name"], "TestTask1")
            # 경로가 정규화되었는지 확인 (OS에 따라 \ 또는 /)
            self.assertEqual(data[0]["file_path"], os.path.normpath("C:\\test.bat"))

    def test_get_next_task_logic(self):
        """다음 실행할 작업을 찾는 로직 테스트"""
        now = datetime.now()
        
        # 1. 1시간 후 작업 (오늘 실행 대상)
        time_today = (now + timedelta(hours=1)).strftime("%H:%M")
        task_today = Task("TodayTask", time_today, "path/to/today.bat")
        
        # 2. 1시간 전 작업 (오늘 이미 지남 -> 내일 실행 대상)
        time_past = (now - timedelta(hours=1)).strftime("%H:%M")
        task_past = Task("PastTask", time_past, "path/to/past.bat")
        
        self.cm.add_task(task_today)
        self.cm.add_task(task_past)

        # 검증: 현재 시간 기준 1시간 후 작업이 반환되어야 함
        next_task = self.cm.get_next_task()
        self.assertEqual(next_task.task_name, "TodayTask")

    def test_get_next_task_tomorrow(self):
        """오늘 남은 작업이 없을 때 내일 첫 작업을 반환하는지 테스트"""
        now = datetime.now()
        
        # 모든 작업이 현재 시간보다 이전인 경우
        time_past1 = (now - timedelta(hours=2)).strftime("%H:%M")
        time_past2 = (now - timedelta(hours=1)).strftime("%H:%M")
        
        task1 = Task("EarlyTask", time_past1, "path1")
        task2 = Task("LateTask", time_past2, "path2")
        
        self.cm.add_task(task1)
        self.cm.add_task(task2)

        # 검증: 오늘 남은 게 없으므로 내일 가장 빠른 EarlyTask가 반환되어야 함
        next_task = self.cm.get_next_task()
        self.assertEqual(next_task.task_name, "EarlyTask")

    def test_update_status(self):
        """작업 상태 업데이트 테스트"""
        task = Task("StatusTask", "12:00", "path")
        self.cm.add_task(task)
        
        self.cm.update_task_status("StatusTask", "Success")
        
        updated_tasks = self.cm.load_config()
        self.assertEqual(updated_tasks[0].last_run_status, "Success")
        self.assertIsNotNone(updated_tasks[0].last_run_time)

if __name__ == "__main__":
    unittest.main()
