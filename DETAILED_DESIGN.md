# S-cheduler 상세 설계서

문서 기준 버전: **v3.0**

## 1. 시스템 개요

S-cheduler는 CustomTkinter GUI와 백그라운드 스케줄러 스레드가 하나의 JSON 설정 파일을 공유하는 단일 데스크톱 프로그램입니다.

```text
GUI ───────────────┐
  │                │
  ├─ ConfigManager ├─ data/s_cheduler_config.json
  │                │
SchedulerEngine ───┤
  ├─ TaskExecutor
  ├─ PowerManager
  └─ NotificationSystem
```

GUI는 Tk 메인 스레드에서 동작하고, 예약 실행과 수동 실행은 작업 스레드에서 수행합니다. 실행 결과는 ConfigManager를 통해 JSON에 저장되며 GUI가 주기적으로 다시 읽어 목록을 갱신합니다.

## 2. 데이터 모델

`src/models/task.py`의 `Task`는 다음 필드를 가집니다.

| 필드 | 형식 | 설명 | 기본값 |
| --- | --- | --- | --- |
| `task_name` | string | 고유 작업 이름 | 필수 |
| `execution_time` | `HH:MM` | 하루 한 번 실행할 시각 | 필수 |
| `file_path` | string | 실행 파일 경로 | 필수 |
| `wakeup_enabled` | boolean | 절전 중 PC 깨우기 | `true` |
| `recipients` | string[] | 이메일 수신자 | `[]` |
| `enabled` | boolean | 예약 실행 활성화 여부 | `true` |
| `timeout_minutes` | integer | 최대 실행 시간(분) | `30` |
| `last_run_status` | string | `Not Started`, `Success`, `Fail` | `Not Started` |
| `last_run_time` | ISO 8601 string/null | 최근 실행 시각 | `null` |
| `last_run_return_code` | integer/null | 프로세스 종료 코드 | `null` |
| `last_run_output` | string | 표준 출력, 최대 10,000자 | `""` |
| `last_run_error` | string | 오류 출력 또는 제한 시간 사유 | `""` |
| `last_run_duration_seconds` | number/null | 실행 시간(초) | `null` |

`from_dict()`는 새 필드가 없는 v2 JSON도 읽을 수 있도록 기본값을 적용하고, 알 수 없는 필드는 무시합니다.

## 3. ConfigManager

파일: `src/utils/config_manager.py`

주요 인터페이스:

- `load_config()`: JSON을 읽고 유효한 Task 목록을 반환합니다.
- `save_config()`: 같은 디렉터리의 임시 파일에 기록·flush·fsync 후 `os.replace()`로 교체합니다.
- `add_task(task)`, `update_task(original_name, task)`, `delete_task(name)`: 작업 CRUD입니다.
- `set_task_enabled(name, enabled)`: 작업을 삭제하지 않고 예약 대상에서 제외하거나 다시 활성화합니다.
- `get_next_task(exclude_task_names=None)`: 활성 작업 중 가장 가까운 다음 작업을 찾습니다.
- `get_tasks_at_time(execution_time, exclude_task_names=None)`: 같은 시각에 실행할 활성 작업을 등록 순서대로 반환합니다.
- `update_task_result(task_name, result)`: 상태, 시각, 종료 코드, 출력, 오류, 실행 시간을 저장합니다.
- `export_config(path)`, `import_config(path)`: JSON 백업·복원입니다.

작업 이름은 고유해야 하며, 저장 시 파일 경로는 운영체제 기준으로 정규화됩니다. JSON이 손상되거나 읽기 실패하면 로그를 남기고 빈 목록으로 동작합니다.

## 4. 스케줄러 엔진

파일: `main.py`의 `SchedulerEngine`

1. 설정에서 활성 작업만 조회합니다.
2. 각 작업의 다음 실행 날짜와 시각을 계산합니다. 현재 시각을 지난 작업은 다음 날로 계산합니다.
3. 실행 시각이 30초보다 멀면 PowerManager에 웨이크업 타이머를 설정합니다.
4. 실행 시각이 되면 TaskExecutor로 작업을 실행합니다.
5. 결과를 저장하고 설정된 알림을 전송합니다.
6. 같은 시각의 다른 작업이 있으면 등록 순서대로 이어서 실행합니다.
7. 하루가 바뀌면 당일 완료 목록을 초기화합니다.

엔진은 약 2초마다 설정 변경을 확인합니다. 실행 중인 작업의 경로·시각·활성 여부·웨이크업 여부·제한 시간·수신자가 바뀌면 다음 예약 계산을 다시 수행합니다. 엔진 종료 시 웨이크업 타이머를 취소합니다.

## 5. TaskExecutor

파일: `src/core/executor.py`

확장자에 따라 안전한 인자 배열을 구성해 `shell=False`로 실행합니다.

- `.bat`, `.cmd`: Windows `cmd /d /c`
- `.py`: 현재 Python 인터프리터
- `.ps1`: Windows PowerShell
- 기타 실행 파일: 파일 자체 실행

반환 결과는 다음 형태입니다.

```python
{
    "success": bool,
    "return_code": int,
    "output": str,
    "error": str,
    "duration_seconds": float,
    "timed_out": bool,
}
```

`subprocess.run(..., timeout=...)`으로 제한 시간을 적용합니다. 제한 시간 초과 시 프로세스를 종료하고 `return_code=-2`, `timed_out=True`와 함께 `실행시간 N분 초과: 작업을 종료했습니다.`를 반환합니다.

## 6. 전원 제어

파일: `src/core/power_manager.py`

- `SetThreadExecutionState`: 프로그램 실행 중 시스템·디스플레이 절전 방지
- `CreateWaitableTimerW`, `SetWaitableTimer`: 예약 시각의 웨이크업 타이머
- `CancelWaitableTimer`, `CloseHandle`: 타이머 취소 및 핸들 정리
- `IsUserAnAdmin`: 관리자 권한 확인

작업이 비활성화되거나 예약 대상이 없으면 기존 웨이크업 타이머를 취소합니다. Windows 이외 환경에서는 전원 제어를 건너뛰고 안전한 기본값을 반환합니다.

## 7. 알림

파일: `src/utils/notification_manager.py`

`send_report()`는 실행 결과를 Teams Webhook 또는 SMTP 이메일로 전송합니다. 네트워크 오류는 작업 실행 자체의 결과와 분리해 로그로 기록합니다.

## 8. GUI 동작

파일: `src/gui_manager.py`

GUI는 밝은 배경의 카드 목록과 오른쪽 실행 상세 패널로 구성됩니다. 카드에는 작업명, 예약 상태, 다음 실행, 최근 실행, 결과를 표시하고, 경로·웨이크업·제한 시간·출력은 선택한 작업의 상세 패널에서 확인합니다.

작업 추가와 작업 수정은 동일한 공통 입력 폼을 사용합니다. 예약 활성화 입력은 폼에서 제거했으며 새 작업은 항상 활성 상태로 저장됩니다. 실행 제한 시간 입력도 제거하고 GUI에서 저장할 때 30분을 기본값으로 저장합니다. 기존 비활성 작업을 수정하는 경우에는 현재 비활성 상태를 유지합니다.

목록과 상세 패널은 가로 `PanedWindow`로 나뉘며 가운데 구분선을 드래그해 상세 패널 폭을 조절할 수 있습니다. 상세 패널의 작업명과 필드 값은 현재 폭에 맞춰 줄바꿈됩니다.

- 오른쪽 위 **+**: 작업 추가
- 작업 카드 선택: 상세 패널 갱신 및 수동 실행 대상 선택
- 작업 카드 더블클릭: 작업 수정 창 열기
- 카드 스위치: `set_task_enabled()`를 호출해 예약만 중지/재개
- 상세 패널의 빨간 **[삭제]**: 경고 확인 후 선택 작업 삭제
- 목록 우측 상단 정렬 컨트롤: 정렬 기준과 방향 변경
- 오른쪽 위 **⋯**: 수정, 복제, 백업·복원, 새로고침, 절전 방지
- **F5**: 메인 작업 목록 새로고침
- **전체 실행 상세**: 최근 결과와 로그 파일 열기 제공
- **수동 실행**: GUI를 멈추지 않도록 별도 스레드에서 실행

Windows 실행 시 창과 작업 표시줄에 동일한 앱 아이콘을 사용하며, 명시적 앱 ID로 작업 표시줄 그룹도 안정적으로 유지합니다.

Tk 위젯 변경은 `root.after()`로 메인 스레드에서 수행합니다. 실행 출력은 `Text` 위젯에서 읽기 전용으로 보여줍니다.

## 9. 검증과 예외 처리

- 작업 이름은 비어 있을 수 없고 중복될 수 없습니다.
- 실행 시각은 `00:00`부터 `23:59`까지의 `HH:MM` 형식이어야 합니다.
- GUI에서 저장하는 제한 시간은 30분이며, 실행 엔진은 설정 JSON의 제한 시간 값을 기준으로 동작합니다.
- 존재하지 않는 경로는 실행하지 않고 실패 결과로 저장합니다.
- 표준 출력·오류 출력은 각각 10,000자로 제한해 설정 파일의 비정상적인 성장을 방지합니다.
- 설정 저장은 원자적 교체 방식이며, 저장 실패 시 기존 작업 목록을 되돌립니다.
- 알림·전원 제어 실패가 스케줄러 스레드 전체를 종료하지 않도록 예외를 로그로 남깁니다.

## 10. 호환성과 운영

기존 v2 설정에는 `enabled`, `timeout_minutes`, 실행 상세 필드가 없을 수 있습니다. Task 모델이 기본값을 적용하므로 별도 마이그레이션 없이 사용할 수 있습니다. 새 GUI에서 저장하면 새 필드가 JSON에 추가됩니다.

운영 로그는 `logs/scheduler.log`에 남습니다. 로그 레벨은 `.env`의 `LOG_LEVEL`로 조정할 수 있습니다. 단위 테스트는 다음 명령으로 실행합니다.

```powershell
python -m unittest discover -s tests -v
```
