import unittest
import logging
import platform
from src.core.power_manager import PowerManager

class TestPowerManager(unittest.TestCase):
    def setUp(self):
        # 테스트 시 로깅을 활성화하여 에러 메시지 확인 가능하게 함
        logging.basicConfig(level=logging.INFO)
        self.pm = PowerManager()

    def test_initialization(self):
        """객체가 정상적으로 생성되는지 확인"""
        self.assertIsNotNone(self.pm)
        print(f"\n현재 OS: {platform.system()}")

    def test_windows_specific_functions(self):
        """비-Windows 환경(리눅스 등)에서 안전하게 종료되는지 확인"""
        if platform.system() != "Windows":
            # 윈도우가 아니면 is_admin은 False여야 함
            self.assertFalse(self.pm.is_admin())
            # 윈도우가 아니면 타이머 설정은 실패(False)해야 함
            success = self.pm.set_wakeup_timer(60)
            self.assertFalse(success)
            print("비-Windows 환경 예외 처리 검증 완료")
        else:
            print("Windows 환경 감지됨 (로컬 실행 시 권한에 따라 결과가 다를 수 있음)")

if __name__ == "__main__":
    unittest.main()
