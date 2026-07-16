# S-cheduler

Windows에서 정해진 시각에 배치 파일, Python 스크립트, PowerShell 스크립트, 실행 파일을 실행하는 가벼운 작업 스케줄러입니다. 작업을 JSON으로 관리하고, GUI에서 실행 상태와 결과를 확인할 수 있습니다.

현재 문서와 코드 기준 버전은 **v3.0**입니다.

## 주요 기능

- 작업별 활성화/비활성화: 작업을 삭제하지 않고 일시 중지합니다.
- 다음 실행 시각, 최근 실행 시각, 실행 결과를 목록에서 확인합니다.
- 실행 상세 보기: 종료 코드, 표준 출력, 오류 출력, 실행 시간, 로그 파일 열기를 제공합니다.
- 작업별 실행 제한 시간: 기본 30분. 제한 시간을 넘기면 프로세스를 종료하고 `실행시간 30분 초과` 오류로 기록합니다.
- Teams 또는 이메일 알림 테스트: 실제 작업을 실행하지 않고 알림 설정만 확인합니다.
- 설정 백업·복원: 작업 설정을 JSON 파일로 내보내거나 다른 PC에서 복원합니다.
- 작업 복제: 기존 작업의 경로, 실행 시각, 알림 수신자를 복사해 새 작업을 만듭니다.
- 하루 단위 다중 작업 스케줄링
- Windows 절전 방지 및 절전 모드 해제 타이머
- 작업 성공·실패 결과의 파일 로그 기록

같은 시각에 여러 작업이 있으면 등록된 순서대로 하나씩 실행합니다. 비활성화된 작업은 실행 대상과 절전 타이머에서 제외됩니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.10 이상 권장 |
| GUI | CustomTkinter, tkinter/ttk |
| 프로세스 실행 | Python 표준 라이브러리 `subprocess` |
| Windows 제어 | 표준 라이브러리 `ctypes`와 Win32 API |
| 설정 저장 | JSON, 원자적 파일 교체 방식 |
| 알림 | `requests` 기반 Teams Webhook, `smtplib` 기반 SMTP 이메일 |
| 환경 변수 | `python-dotenv` |
| 백그라운드 실행 | Python `threading` |

Windows 10/11에 맞춰 개발되었습니다. GUI와 전원 제어는 Windows에서 가장 안정적으로 동작합니다.

## 설치 및 실행

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

PowerShell 실행 정책 때문에 가상 환경이 활성화되지 않으면 다음 명령을 한 번 실행한 뒤 다시 시도할 수 있습니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

절전 모드 해제 타이머를 사용하려면 프로그램을 관리자 권한으로 실행하는 것이 좋습니다. Windows 전원 옵션에서 `절전 모드 해제 타이머 허용`도 활성화되어 있어야 합니다.

## 알림 설정

알림을 사용하려면 프로젝트 루트의 `.env.example`을 `.env`로 복사하고 필요한 값을 입력합니다.

```powershell
Copy-Item .env.example .env
```

Teams는 `TEAMS_WEBHOOK_URL`, 이메일은 `GMAIL_USER`와 `GMAIL_APP_PASSWORD`를 설정합니다. Gmail은 일반 비밀번호가 아닌 Google 앱 비밀번호를 사용해야 합니다. Teams와 이메일이 모두 설정되어 있으면 Teams를 우선 시도하고 필요할 때 이메일을 사용합니다.

`TEAMS_VERIFY_SSL=false`는 회사 네트워크의 SSL 검사로 인증서 검증이 실패할 때만 사용합니다. `.env`에는 비밀번호와 Webhook 주소가 들어갈 수 있으므로 Git에 커밋하지 마십시오.

## 사용 방법

### 작업 추가·수정

1. **스케줄 추가**를 누릅니다.
2. 작업 이름, `HH:MM` 형식의 실행 시각, 실행 파일 경로를 입력합니다.
3. 필요하면 **활성화**, **절전 모드 해제**, 수신 이메일, 실행 제한 시간을 설정합니다.
4. 저장하면 백그라운드 스케줄러가 즉시 새 설정을 읽습니다.

지원 경로는 `.bat`, `.cmd`, `.exe`, `.py`, `.ps1` 등입니다. Python 파일은 현재 프로그램을 실행한 Python 인터프리터로 실행하고, PowerShell 파일은 Windows PowerShell로 실행합니다.

### 작업 관리

- **활성/중지**: 선택한 작업의 예약 실행만 켜거나 끕니다. 작업 정보와 실행 이력은 유지됩니다.
- **복제**: 선택한 작업을 `작업명 (복사본)`으로 추가합니다. 실행 이력은 복사하지 않습니다.
- **지금 실행**: 예약 시각을 기다리지 않고 선택한 작업을 실행합니다. 실행 제한 시간은 작업 설정을 따릅니다.
- **실행 상세**: 마지막 실행의 종료 코드, 출력, 오류, 실행 시간과 로그를 확인합니다.
- **알림 테스트**: 작업을 실행하지 않고 현재 Teams/이메일 설정으로 테스트 알림을 전송합니다.
- **설정 백업**: 원하는 위치에 JSON을 저장합니다.
- **설정 복원**: JSON을 선택해 현재 작업 목록을 교체합니다. 복원 전 백업을 권장합니다.

목록의 `다음 실행`은 오늘 실행할 수 있으면 오늘 시각으로, 이미 지난 시각이면 내일 시각으로 표시됩니다. `최근 실행`은 마지막 실행 시각이며, 아직 실행하지 않은 작업은 `-`로 표시됩니다.

## 실행 제한 시간과 결과

작업별 제한 시간의 기본값은 30분입니다. 1분 이상으로 설정할 수 있습니다. 제한 시간을 넘기면 실행 프로세스를 종료하고 다음 정보로 저장합니다.

- 상태: `Fail`
- 종료 코드: `-2`
- 오류: `실행시간 N분 초과: 작업을 종료했습니다.`

일반 실패는 프로세스 종료 코드와 표준 오류를 함께 저장합니다. 표준 출력과 오류 출력은 너무 큰 로그가 GUI를 차지하지 않도록 각각 최대 10,000자까지 보관합니다. 전체 실행 로그는 `logs/scheduler.log`에서 확인할 수 있습니다.

## 설정 JSON 형식

`data/s_cheduler_config.json`은 다음과 같은 배열 형식입니다. 기존 v2 설정에 새 필드가 없어도 기본값으로 읽을 수 있습니다.

```json
[
  {
    "task_name": "DailyReport",
    "execution_time": "09:00",
    "file_path": "C:\\work\\daily_report.bat",
    "wakeup_enabled": true,
    "recipients": ["admin@example.com"],
    "enabled": true,
    "timeout_minutes": 30,
    "last_run_status": "Not Started",
    "last_run_time": null,
    "last_run_return_code": null,
    "last_run_output": "",
    "last_run_error": "",
    "last_run_duration_seconds": null
  }
]
```

프로그램은 설정을 임시 파일에 먼저 저장한 뒤 원본과 교체합니다. 저장 중 프로그램이 종료되어도 기존 JSON이 손상될 가능성을 줄이는 방식입니다.

## 프로젝트 구조

```text
main.py                    실행 진입점과 백그라운드 스케줄러
src/models/task.py         작업 데이터 모델과 이전 설정 호환
src/utils/config_manager.py JSON 로드·저장·백업·복원
src/core/executor.py       프로세스 실행·출력 수집·제한 시간 처리
src/core/power_manager.py  Windows 절전 방지·웨이크업 타이머
src/utils/notification_manager.py Teams·이메일 알림
src/gui_manager.py         작업 목록과 설정 GUI
data/                      기본 설정 JSON
logs/                      실행 로그
tests/                     단위 테스트
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

테스트는 설정 저장, 이전 형식 호환, 활성/비활성 필터, 같은 시각 작업 순서, 실행 결과 저장, 백업·복원, 프로세스 성공·실패·제한 시간 처리를 확인합니다.

## 문제 해결

- 작업이 실행되지 않으면 작업이 활성화되어 있는지, 실행 시각이 올바른지, 파일 경로가 실제로 존재하는지 확인합니다.
- `.bat` 또는 `.cmd` 경로에 공백이 있어도 지원하지만, GUI에서 파일 선택으로 정확한 경로를 입력하는 것이 안전합니다.
- 웨이크업이 동작하지 않으면 관리자 권한과 Windows 전원 옵션의 웨이크 타이머 허용 여부를 확인합니다.
- 알림 오류는 먼저 GUI의 **알림 테스트**를 실행하고, 그 다음 `logs/scheduler.log`를 확인합니다.
- 프로그램이 실행 중인 동안 설정을 수정하면 스케줄러가 최대 약 2초 안에 변경을 반영합니다.
