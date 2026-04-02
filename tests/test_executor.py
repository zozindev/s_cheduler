import unittest
import os
import platform
import subprocess
from src.core.executor import TaskExecutor

class TestTaskExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = TaskExecutor()
        # 현재 리눅스 환경이므로 .sh 확장자 사용
        self.success_script = "scripts/success_test.sh"
        self.fail_script = "scripts/fail_test.sh"
        
        # 파일이 실제로 존재하는지 확인 (없으면 생성)
        if not os.path.exists(self.success_script):
            with open(self.success_script, "w") as f:
                f.write("#!/bin/bash\necho 'Hello World'\n")
            os.chmod(self.success_script, 0o755)
            
        if not os.path.exists(self.fail_script):
            with open(self.fail_script, "w") as f:
                f.write("#!/bin/bash\nexit 1\n")
            os.chmod(self.fail_script, 0o755)

    def test_execute_success(self):
        """성공적인 스크립트 실행 테스트"""
        # 리눅스 환경에서는 파일 경로만으로 실행 가능하도록 shell=True 사용
        res = self.executor.execute(f"./{self.success_script}")
        
        print(f"\n성공 테스트 결과: {res}")
        self.assertTrue(res["success"])
        self.assertEqual(res["return_code"], 0)
        # Hello World가 출력되는지 확인 (개행 문자 제거)
        self.assertEqual(res["output"], "Hello World")

    def test_execute_fail(self):
        """실패하는 스크립트 실행 테스트 (exit 1)"""
        res = self.executor.execute(f"./{self.fail_script}")
        
        print(f"실패 테스트 결과: {res}")
        self.assertFalse(res["success"])
        # exit 1에 의해 return_code가 1이어야 함
        self.assertEqual(res["return_code"], 1)

    def test_file_not_found(self):
        """존재하지 않는 파일 실행 테스트"""
        res = self.executor.execute("non_existent_file.bat")
        
        print(f"미존재 파일 결과: {res}")
        self.assertFalse(res["success"])
        self.assertEqual(res["return_code"], -1)
        self.assertIn("파일을 찾을 수 없습니다", res["error"])

if __name__ == "__main__":
    unittest.main()
