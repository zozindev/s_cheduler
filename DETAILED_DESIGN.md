# 슼케줄러 (S-cheduler) 상세 설계서 (Detailed Design) - v2.1 (Stay-Awake 및 Teams 연동 지원)

이 문서는 `spec.md`의 최신 요구사항(GUI 제공, 절전 방지, Teams 연동 등)을 바탕으로 각 모듈의 상세 구조와 인터페이스를 정의합니다.

---

## 1. PowerManager (전원 제어 모듈)
**역할:** Windows 커널 API를 호출하여 시스템의 절전 모드 해제 타이머를 설정하거나, 자동 절전 진입을 방지합니다.

### 주요 기능
- `set_wakeup_timer(seconds: int, enabled: bool)`: `enabled`가 `True`일 때 하드웨어 타이머를 설정하여 절전 모드에서 시스템을 깨움.
- `set_sleep_prevention(enabled: bool)`: `SetThreadExecutionState` API를 사용하여 프로그램 실행 중 시스템이 자동으로 절전 모드에 진입하는 것을 방지(Stay-Awake). 관리자 권한 없이도 동작 가능.
- `cancel_timer()`: 설정된 하드웨어 타이머 취소 및 핸들 정리.
- `is_admin()`: 하드웨어 타이머 설정을 위한 관리자 권한 확인.

---

## 2. ConfigManager (설정 및 데이터 관리 모듈)
**역할:** 작업을 관리하며, 확장된 데이터 구조를 JSON 파일에 유지합니다.

### 데이터 구조 (Task 모델)
```json
{
    "task_name": "string (Unique ID)",
    "execution_time": "HH:MM",
    "file_path": "string (Absolute Path)",
    "wakeup_enabled": "boolean",
    "recipients": ["email1@test.com", "email2@test.com"],
    "last_run_status": "string",
    "last_run_time": "ISO 8601 Timestamp"
}
```

---

## 3. TaskExecutor (작업 실행 모듈)
**역할:** `.bat`, `.exe` 등 실행 파일을 독립 프로세스로 구동하고 결과를 캡처합니다.

---

## 4. NotificationSystem (알림 모듈) - 업데이트됨
**역할:** 작업 결과를 하나 이상의 수신자에게 전송합니다. 이메일(SMTP)과 MS Teams(Webhook)를 모두 지원합니다.

### 주요 기능
- `send_report(task_name, result_dict, recipients: list)`: 
    1. **MS Teams**: `TEAMS_WEBHOOK_URL`이 설정되어 있으면 가장 먼저 Adaptive Card 형태로 알림 전송.
    2. **Email (Fallback)**: Teams 전송 실패 또는 미설정 시, 등록된 수신자 리스트(`recipients`)로 이메일 전송.
- **환경 설정**: `.env` 파일을 통해 Webhook URL, 이메일 계정 정보(SMTP)를 관리.

---

## 5. GUIManager (사용자 인터페이스 모듈) - 업데이트됨
**역할:** `tkinter`를 사용하여 사용자에게 시각적인 관리 환경을 제공합니다.

### 메인 화면 (Schedule List)
- **목록 표시**: 등록된 스케줄 목록 표시 (Treeview 사용).
- **시스템 전원 제어 (신규)**: "프로그램 실행 중 자동 절전 방지(Stay-Awake)" 체크박스 제공.
- **버튼**: [추가], [수정], [삭제], [새로고침] 버튼 제공.

### 설정 팝업 (Schedule Setup)
- **입력 항목**:
    - 작업 실행 시간 (HH:MM)
    - 파일의 절대 경로 (파일 탐색기 버튼 연동)
    - 하드웨어 웨이크업(Wake-up) 사용 여부 (Checkbutton)
    - 이메일 주소 입력 칸 (쉼표 구분 다중 입력 지원)

---

## 6. Main Loop 및 워크플로우
1.  **GUI 시작**: 프로그램 실행 시 GUI 메인 화면 표시.
2.  **Background Thread**: GUI와 별개로 스케줄링 엔진이 백그라운드에서 동작하여 시간을 감시.
3.  **Event Handling**: GUI에서 스케줄 변경 시 즉시 JSON 파일과 엔진에 반영.

---

## 7. 예외 처리 및 보안
- **자격 증명 보호**: 이메일 비밀번호 및 Webhook URL 등은 소스 코드에 하드코딩하지 않고 `.env` 파일에 저장.
- **GUI 에러 핸들링**: 잘못된 시간 형식이나 비어있는 경로 입력 시 경고창 표시.
- **로그 기록**: 알림 전송 실패나 타이머 설정 오류 등을 `logs/` 폴더에 기록.
