import unittest
import importlib.util

if importlib.util.find_spec("customtkinter") is None:
    raise unittest.SkipTest("customtkinter is not installed")

from src.gui_manager import GUIManager
from src.models.task import Task


class TestGUISorting(unittest.TestCase):
    def setUp(self):
        self.gui = GUIManager.__new__(GUIManager)
        self.tasks = [
            Task("Beta", "14:00", "C:\\jobs\\b.bat"),
            Task("alpha", "02:00", "C:\\jobs\\c.bat"),
            Task("Gamma", "08:30", "C:\\jobs\\a.bat"),
        ]

    def test_sort_by_task_name_case_insensitive(self):
        self.gui.sort_column = "task_name"
        self.gui.sort_reverse = False

        sorted_tasks = self.gui._sort_tasks_for_display(self.tasks)

        self.assertEqual([task.task_name for task in sorted_tasks], ["alpha", "Beta", "Gamma"])

    def test_sort_by_execution_time_as_time(self):
        self.gui.sort_column = "execution_time"
        self.gui.sort_reverse = False

        sorted_tasks = self.gui._sort_tasks_for_display(self.tasks)

        self.assertEqual([task.execution_time for task in sorted_tasks], ["02:00", "08:30", "14:00"])

    def test_sort_by_file_path_descending(self):
        self.gui.sort_column = "file_path"
        self.gui.sort_reverse = True

        sorted_tasks = self.gui._sort_tasks_for_display(self.tasks)

        self.assertEqual(
            [task.file_path for task in sorted_tasks],
            ["C:\\jobs\\c.bat", "C:\\jobs\\b.bat", "C:\\jobs\\a.bat"],
        )


if __name__ == "__main__":
    unittest.main()
