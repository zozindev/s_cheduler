import os
import platform
import shutil
import unittest

from src.core.executor import TaskExecutor


class TestTaskExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = TaskExecutor()
        self.script_dir = "tests/temp_scripts"
        os.makedirs(self.script_dir, exist_ok=True)

        if platform.system() == "Windows":
            self.success_script = os.path.join(self.script_dir, "success_test.bat")
            self.fail_script = os.path.join(self.script_dir, "fail_test.bat")
            success_body = "@echo off\necho Hello World\n"
            fail_body = "@echo off\nexit /b 1\n"
        else:
            self.success_script = os.path.join(self.script_dir, "success_test.sh")
            self.fail_script = os.path.join(self.script_dir, "fail_test.sh")
            success_body = "#!/bin/bash\necho 'Hello World'\n"
            fail_body = "#!/bin/bash\nexit 1\n"

        with open(self.success_script, "w") as f:
            f.write(success_body)
        with open(self.fail_script, "w") as f:
            f.write(fail_body)

        if platform.system() != "Windows":
            os.chmod(self.success_script, 0o755)
            os.chmod(self.fail_script, 0o755)

    def tearDown(self):
        if os.path.exists(self.script_dir):
            shutil.rmtree(self.script_dir)

    def test_execute_success(self):
        res = self.executor.execute(self.success_script)

        self.assertTrue(res["success"])
        self.assertEqual(res["return_code"], 0)
        self.assertEqual(res["output"], "Hello World")

    def test_execute_fail(self):
        res = self.executor.execute(self.fail_script)

        self.assertFalse(res["success"])
        self.assertEqual(res["return_code"], 1)

    def test_file_not_found(self):
        res = self.executor.execute("non_existent_file.bat")

        self.assertFalse(res["success"])
        self.assertEqual(res["return_code"], -1)
        self.assertTrue(res["error"])


if __name__ == "__main__":
    unittest.main()
