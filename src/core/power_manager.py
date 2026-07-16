import ctypes
import logging
import platform
from ctypes import wintypes

# 로거 설정
logger = logging.getLogger(__name__)

class PowerManager:
    """Windows Win32 API를 사용하여 시스템 전원 및 웨이크업 타이머를 제어하는 클래스"""

    def __init__(self):
        self._h_timer = None
        self._is_windows = platform.system() == "Windows"
        self._kernel32 = None
        self._shell32 = None

        if self._is_windows:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            self._configure_api_types()
        
        if not self._is_windows:
            logger.warning("PowerManager는 Windows 환경에서만 완전히 동작합니다. 현재 OS: %s", platform.system())

    def _configure_api_types(self):
        """64비트 Windows에서도 HANDLE이 잘리지 않도록 Win32 타입을 명시합니다."""
        self._shell32.IsUserAnAdmin.restype = wintypes.BOOL

        self._kernel32.SetThreadExecutionState.argtypes = [wintypes.ULONG]
        self._kernel32.SetThreadExecutionState.restype = wintypes.ULONG

        self._kernel32.CreateWaitableTimerW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self._kernel32.CreateWaitableTimerW.restype = wintypes.HANDLE

        self._kernel32.SetWaitableTimer.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.LONG,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.BOOL,
        ]
        self._kernel32.SetWaitableTimer.restype = wintypes.BOOL
        self._kernel32.CancelWaitableTimer.argtypes = [wintypes.HANDLE]
        self._kernel32.CancelWaitableTimer.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def is_admin(self) -> bool:
        """현재 프로세스가 관리자 권한으로 실행 중인지 확인합니다."""
        if not self._is_windows:
            return False
        try:
            return self._shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False

    def set_sleep_prevention(self, enabled: bool):
        """
        시스템이 자동으로 절전 모드에 진입하는 것을 방지하거나 다시 허용합니다.
        
        Args:
            enabled (bool): True이면 절전 방지 활성화, False이면 다시 허용
        """
        if not self._is_windows:
            return

        # ES_CONTINUOUS (0x80000000): 상태를 계속 유지 (필수)
        # ES_SYSTEM_REQUIRED (0x00000001): 시스템(CPU)을 깨어있는 상태로 유지
        # ES_DISPLAY_REQUIRED (0x00000002): 디스플레이(모니터)를 켜진 상태로 유지
        
        if enabled:
            # 시스템과 디스플레이 모두 깨어있도록 설정
            flags = 0x80000000 | 0x00000001 | 0x00000002
            logger.info("절전 모드 진입 방지(Stay-Awake) 활성화됨 (시스템 + 디스플레이)")
        else:
            # ES_CONTINUOUS만 단독으로 호출하여 이전 상태를 리셋
            flags = 0x80000000
            logger.info("절전 모드 진입 방지 비활성화됨 (시스템 기본 설정 따름)")

        try:
            # Win32 API 호출
            result = self._kernel32.SetThreadExecutionState(flags)
            if result == 0:
                logger.error("SetThreadExecutionState 호출 실패 (결과값 0)")
        except Exception as e:
            logger.error(f"절전 상태 제어 중 오류 발생: {e}")

    def set_wakeup_timer(self, seconds: int, enabled: bool = True) -> bool:
        """
        지정된 초(seconds) 후에 시스템을 깨우는 하드웨어 타이머를 설정합니다.
        
        Args:
            seconds (int): 현재로부터 타이머가 작동할 시간(초 단위)
            enabled (bool): 실제로 하드웨어 타이머를 설정할지 여부
            
        Returns:
            bool: 타이머 설정 성공 여부
        """
        if not enabled:
            # 새 작업에서 웨이크업을 끈 경우 이전 작업의 타이머도 반드시 취소합니다.
            self.cancel_timer()
            logger.info("웨이크업 타이머 기능이 비활성화되어 있어 타이머를 설정하지 않습니다.")
            return True

        if not self._is_windows:
            logger.error("Windows가 아닌 환경에서는 웨이크업 타이머를 설정할 수 없습니다.")
            return False

        if seconds <= 0:
            logger.error("웨이크업 타이머 시간은 1초 이상이어야 합니다.")
            return False

        if not self.is_admin():
            logger.error("웨이크업 타이머를 설정하려면 관리자 권한이 필요합니다.")
            return False

        # 1. 기존 타이머가 있다면 취소
        self.cancel_timer()

        # 2. 대기 가능한 타이머 생성 (CreateWaitableTimerW)
        # lpTimerAttributes=None, bManualReset=True, lpTimerName=None
        self._h_timer = self._kernel32.CreateWaitableTimerW(None, True, None)
        if not self._h_timer:
            logger.error("WaitableTimer 생성 실패: %d", ctypes.get_last_error())
            return False

        # 3. 타이머 만료 시간 설정 (SetWaitableTimer)
        # pDueTime은 100나노초 단위의 음수값 (상대적 시간)
        # 1초 = 10,000,000 (10^7) 100나노초 단위
        due_time = ctypes.c_longlong(-seconds * 10000000)
        
        # BOOL SetWaitableTimer(HANDLE hTimer, const LARGE_INTEGER *pDueTime, LONG lPeriod, 
        #                      PTIMERAPCROUTINE pfnCompletionRoutine, LPVOID lpArgToCompletionRoutine, BOOL fResume)
        # fResume (마지막 인자)을 True(1)로 설정해야 절전 모드에서 깨어남
        success = self._kernel32.SetWaitableTimer(
            self._h_timer,
            ctypes.byref(due_time),
            0,      # lPeriod (0 = 일회성)
            None,   # pfnCompletionRoutine
            None,   # lpArgToCompletionRoutine
            True    # fResume (Wake-up 핵심!)
        )

        if success:
            logger.info(f"시스템 웨이크업 타이머 설정 완료: {seconds}초 후 실행")
            return True
        else:
            logger.error("SetWaitableTimer 설정 실패: %d", ctypes.get_last_error())
            self.cancel_timer()
            return False

    def cancel_timer(self):
        """설정된 타이머를 취소하고 핸들을 닫습니다."""
        if self._h_timer:
            self._kernel32.CancelWaitableTimer(self._h_timer)
            self._kernel32.CloseHandle(self._h_timer)
            self._h_timer = None
            logger.info("기존 웨이크업 타이머 취소 및 리소스 정리 완료")

# 모듈 독립 테스트 (관리자 권한으로 실행 시 확인 가능)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pm = PowerManager()
    print(f"관리자 권한 여부: {pm.is_admin()}")
    # pm.set_wakeup_timer(60) # 1분 후 깨어남 테스트
