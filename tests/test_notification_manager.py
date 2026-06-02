import os
import unittest
from unittest.mock import Mock, patch

from src.utils.notification_manager import NotificationSystem


class TestNotificationSystem(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("src.utils.notification_manager.load_dotenv")
    def test_env_file_overrides_existing_process_env(self, mock_load_dotenv):
        NotificationSystem()

        self.assertTrue(mock_load_dotenv.called)
        self.assertTrue(mock_load_dotenv.call_args.kwargs["override"])

    @patch("src.utils.notification_manager.load_dotenv")
    @patch("src.utils.notification_manager.requests.post")
    def test_teams_ssl_verify_false_is_passed_to_requests(self, mock_post, _):
        os.environ["TEAMS_WEBHOOK_URL"] = "https://example.test/webhook"
        os.environ["TEAMS_VERIFY_SSL"] = "false"
        mock_post.return_value = Mock(status_code=202, text="")

        notifier = NotificationSystem()
        sent = notifier.send_report("task", {"success": True, "output": "ok"})

        self.assertTrue(sent)
        self.assertFalse(mock_post.call_args.kwargs["verify"])

    @patch("src.utils.notification_manager.load_dotenv")
    @patch.object(NotificationSystem, "_send_to_email")
    @patch.object(NotificationSystem, "_send_to_teams")
    def test_email_fallback_runs_when_teams_fails(
        self,
        mock_send_to_teams,
        mock_send_to_email,
        _,
    ):
        os.environ["TEAMS_WEBHOOK_URL"] = "https://example.test/webhook"
        os.environ["GMAIL_USER"] = "sender@example.com"
        os.environ["GMAIL_APP_PASSWORD"] = "secret"
        mock_send_to_teams.return_value = False
        mock_send_to_email.return_value = True

        notifier = NotificationSystem()
        sent = notifier.send_report("task", {"success": False, "error": "boom"})

        self.assertTrue(sent)
        mock_send_to_email.assert_called_once()


if __name__ == "__main__":
    unittest.main()
