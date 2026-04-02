# 슼케줄러 (S-cheduler) 상세 설계서 (Detailed Design) - v2.0 (GUI 지원)

이 문서는 `spec.md`의 최신 요구사항(GUI 제공 등)을 바탕으로 각 모듈의 상세 구조와 인터페이스를 정의합니다.

---

## 1. PowerManager (전원 제어 모듈)
**역할:** Windows 커널 API를 호출하여 시스템의 절전 모드 해제 타이머를 설정합니다.

### 주요 기능
- `set_wakeup_timer(seconds: int, enabled: bool)`: `enabled`가 `True`일 때만 하드웨어 타이머를 설정.
- `cancel_timer()`: 설정된 타이머 취소 및 핸들 정리.
- `is_admin()`: 타이머 설정을 위한 관리자 권한 확인.

---

## 2. ConfigManager (설정 및 데이터 관리 모듈)
**역할:** 작업을 관리하며, 확장된 데이터 구조를 JSON 파일에 유지합니다.

### 데이터 구조 (Task 모델) - 업데이트됨
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
**역할:** `.bat`, `.exe` 등 실행 파일을 독립 프로세스로 구동하고 결과를 캡처합니다. (변화 없음)

---

## 4. NotificationSystem (알림 모듈) - 업데이트됨
**역할:** 작업 결과를 하나 이상의 수신자에게 전송합니다.

### 주요 기능
- `send_report(task_name, result_dict, recipients: list)`: 수신자 리스트(`recipients`)를 순회하거나 참조하여 모든 주소로 결과 리포트 전송.

---

## 5. GUIManager (사용자 인터페이스 모듈) - 신규 추가
**역할:** `tkinter`를 사용하여 사용자에게 시각적인 관리 환경을 제공합니다.

### 메인 화면 (Schedule List)
- **기능**: 등록된 스케줄 목록 표시 (Treeview 사용).
- **버튼**: [추가], [수정], [삭제] 버튼 제공.
- **동작**: [추가/수정] 클릭 시 설정 팝업 창을 띄움.

### 설정 팝업 (Schedule Setup)
- **입력 항목**:
    - 작업 실행 시간 (Entry/Time Picker)
    - 파일의 절대 경로 (파일 탐색기 버튼 연동)
    - 절전 모드 해제 사용 여부 (Checkbutton)
    - 이메일 주소 입력 칸 (쉼표 등으로 구분하여 여러 개 입력 지원)

---

## 6. Main Loop 및 워크플로우
1.  **GUI 시작**: 프로그램 실행 시 GUI 메인 화면을 먼저 표시.
2.  **Background Thread**: GUI와 별개로 스케줄링 엔진이 백그라운드에서 동작하도록 구성.
3.  **Event Handling**: GUI에서 스케줄 변경 시 즉시 JSON 파일과 엔진에 반영.

---

## 7. 예외 처리 및 보안 (업데이트)
- **GUI 에러 핸들링**: 잘못된 시간 형식이나 비어있는 경로 입력 시 경고창 표시.
- **다중 메일 처리**: 이메일 주소 유효성 검사 및 전송 실패 시 로그 기록.
