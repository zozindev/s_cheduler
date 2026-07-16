import logging
import os
import threading
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from src.core.executor import TaskExecutor
from src.core.power_manager import PowerManager
from src.models.task import Task
from src.utils.config_manager import ConfigManager
from src.utils.notification_manager import NotificationSystem

logger = logging.getLogger(__name__)


class GUIManager:
    """스케줄 목록과 작업 관리 기능을 제공하는 CustomTkinter GUI."""

    LOG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logs",
        "scheduler.log",
    )

    def __init__(
        self,
        config_manager: ConfigManager,
        power_manager: PowerManager,
        task_executor: TaskExecutor = None,
        notification_system: NotificationSystem = None,
    ):
        self.cm = config_manager
        self.pm = power_manager
        self.executor = task_executor or TaskExecutor()
        self.notification_system = notification_system
        self.sort_column = "execution_time"
        self.sort_reverse = False
        self.sortable_columns = {
            "task_name",
            "enabled",
            "execution_time",
            "next_run",
            "file_path",
            "last_status",
        }
        self.is_manual_run_active = False
        self.is_notification_test_active = False

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("스케줄러 (S-cheduler) v3.0")
        self.root.geometry("1250x700")
        self.root.minsize(900, 520)
        self._setup_main_window()

    def _setup_main_window(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0, minsize=100)

        header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header_frame,
            text="📅 작업 스케줄 관리",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(side=ctk.LEFT)
        ctk.CTkLabel(
            header_frame,
            text="예약 실행 상태를 확인하고 작업을 관리하세요.",
            text_color=("gray35", "gray70"),
        ).pack(side=ctk.LEFT, padx=16, pady=(7, 0))

        power_frame = ctk.CTkFrame(self.root)
        power_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.stay_awake_var = ctk.BooleanVar(value=False)

        def on_toggle_stay_awake():
            self.pm.set_sleep_prevention(self.stay_awake_var.get())
            status = "활성화" if self.stay_awake_var.get() else "비활성화"
            logger.info("시스템 절전 방지 모드: %s", status)

        ctk.CTkSwitch(
            power_frame,
            text="프로그램 실행 중 자동 절전 모드 진입 방지 (Stay-Awake)",
            variable=self.stay_awake_var,
            command=on_toggle_stay_awake,
            font=ctk.CTkFont(size=12),
        ).pack(side=ctk.LEFT, padx=15, pady=10)

        list_frame = ctk.CTkFrame(self.root)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            rowheight=30,
            fieldbackground="#343638",
            bordercolor="#343638",
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#1f538d")])
        style.configure(
            "Treeview.Heading",
            background="#565b5e",
            foreground="white",
            relief="flat",
            font=("Arial", 10, "bold"),
        )

        columns = (
            "task_name",
            "enabled",
            "execution_time",
            "next_run",
            "file_path",
            "wakeup",
            "last_run_time",
            "last_status",
        )
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            style="Treeview",
        )
        self.tree.bind("<Double-1>", lambda event: self._edit_task_window())

        self.column_labels = {
            "task_name": "작업명",
            "enabled": "예약",
            "execution_time": "실행 시각",
            "next_run": "다음 실행",
            "file_path": "파일 경로",
            "wakeup": "절전 해제",
            "last_run_time": "최근 실행",
            "last_status": "실행 결과",
        }
        self.tree.heading("task_name", command=lambda: self._set_sort("task_name"))
        self.tree.heading("enabled", command=lambda: self._set_sort("enabled"))
        self.tree.heading("execution_time", command=lambda: self._set_sort("execution_time"))
        self.tree.heading("next_run", command=lambda: self._set_sort("next_run"))
        self.tree.heading("file_path", command=lambda: self._set_sort("file_path"))
        self.tree.heading("wakeup", text="절전 해제")
        self.tree.heading("last_run_time", command=lambda: self._set_sort("last_run_time"))
        self.tree.heading("last_status", command=lambda: self._set_sort("last_status"))
        self._refresh_sort_headings()

        self.tree.column("task_name", width=140, anchor="center")
        self.tree.column("enabled", width=70, anchor="center")
        self.tree.column("execution_time", width=90, anchor="center")
        self.tree.column("next_run", width=120, anchor="center")
        self.tree.column("file_path", width=360)
        self.tree.column("wakeup", width=90, anchor="center")
        self.tree.column("last_run_time", width=145, anchor="center")
        self.tree.column("last_status", width=100, anchor="center")

        y_scrollbar = ctk.CTkScrollbar(list_frame, orientation="vertical", command=self.tree.yview)
        x_scrollbar = ctk.CTkScrollbar(list_frame, orientation="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(5, 15))
        button_frame.grid_columnconfigure(0, weight=1)

        primary_button_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        primary_button_frame.grid(row=0, column=0, sticky="ew")
        utility_button_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        utility_button_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        ctk.CTkButton(primary_button_frame, text="✚ 스케줄 추가", width=115, command=self._add_task_window).pack(side=ctk.LEFT, padx=3)
        ctk.CTkButton(primary_button_frame, text="✎ 수정", width=80, fg_color="gray30", hover_color="gray40", command=self._edit_task_window).pack(side=ctk.LEFT, padx=3)
        ctk.CTkButton(primary_button_frame, text="복제", width=80, fg_color="#6a1b9a", hover_color="#4a148c", command=self._duplicate_selected_task).pack(side=ctk.LEFT, padx=3)
        self.toggle_button = ctk.CTkButton(primary_button_frame, text="예약 중지/재개", width=115, fg_color="#ef6c00", hover_color="#e65100", command=self._toggle_selected_task)
        self.toggle_button.pack(side=ctk.LEFT, padx=3)
        ctk.CTkButton(primary_button_frame, text="🗑 삭제", width=80, fg_color="#d32f2f", hover_color="#b71c1c", command=self._delete_task).pack(side=ctk.LEFT, padx=3)
        self.run_now_button = ctk.CTkButton(primary_button_frame, text="지금 실행", width=95, fg_color="#1565c0", hover_color="#0d47a1", command=self._run_selected_task_now)
        self.run_now_button.pack(side=ctk.LEFT, padx=3)
        ctk.CTkButton(primary_button_frame, text="실행 상세", width=95, fg_color="#455a64", hover_color="#263238", command=self._show_task_details).pack(side=ctk.LEFT, padx=3)

        self.notification_test_button = ctk.CTkButton(utility_button_frame, text="알림 테스트", width=100, fg_color="#00897b", hover_color="#00695c", command=self._test_notification)
        self.notification_test_button.pack(side=ctk.RIGHT, padx=3)
        ctk.CTkButton(utility_button_frame, text="설정 복원", width=95, fg_color="#795548", hover_color="#5d4037", command=self._restore_config).pack(side=ctk.RIGHT, padx=3)
        ctk.CTkButton(utility_button_frame, text="설정 백업", width=95, fg_color="#795548", hover_color="#5d4037", command=self._backup_config).pack(side=ctk.RIGHT, padx=3)
        ctk.CTkButton(utility_button_frame, text="🔄 새로고침", width=95, fg_color="#2e7d32", hover_color="#1b5e20", command=self.refresh_list).pack(side=ctk.RIGHT, padx=3)

        self.refresh_list()
        self.root.after(5000, self._auto_refresh)

    def _auto_refresh(self):
        try:
            if self.root.winfo_exists():
                self.refresh_list()
                self.root.after(5000, self._auto_refresh)
        except Exception:
            # 창이 닫히는 순간 예약된 after 콜백이 실행될 수 있습니다.
            return

    @staticmethod
    def _format_next_run(next_run: datetime):
        if next_run is None:
            return "-"
        now = datetime.now()
        if next_run.date() == now.date():
            return f"오늘 {next_run:%H:%M}"
        if next_run.date() == (now + timedelta(days=1)).date():
            return f"내일 {next_run:%H:%M}"
        return next_run.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _format_last_run(value):
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return str(value)

    def refresh_list(self):
        """작업 목록과 실행 상태를 새로고침합니다."""
        selected_name = None
        selected = self.tree.selection()
        if selected:
            selected_name = self.tree.item(selected[0])["values"][0]

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.cm.load_config()
        for task in self._sort_tasks_for_display(self.cm.tasks):
            next_run = self.cm.get_next_run_datetime(task)
            item_id = self.tree.insert(
                "",
                ctk.END,
                values=(
                    task.task_name,
                    "✅ 사용" if task.enabled else "⏸ 중지",
                    task.execution_time,
                    self._format_next_run(next_run),
                    task.file_path,
                    "✅ 사용" if task.wakeup_enabled else "❌ 미사용",
                    self._format_last_run(task.last_run_time),
                    task.last_run_status,
                ),
            )
            if selected_name == task.task_name:
                self.tree.selection_set(item_id)

    def _set_sort(self, column: str):
        if column not in self.sortable_columns:
            return
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self._refresh_sort_headings()
        self.refresh_list()

    def _sort_tasks_for_display(self, tasks):
        return sorted(tasks, key=self._get_sort_key, reverse=self.sort_reverse)

    def _get_sort_key(self, task: Task):
        if self.sort_column == "execution_time":
            try:
                hour, minute = str(task.execution_time).split(":", 1)
                return int(hour), int(minute)
            except (ValueError, TypeError):
                return 99, 99
        if self.sort_column == "next_run":
            return self.cm.get_next_run_datetime(task) or datetime.max
        if self.sort_column == "last_run_time":
            try:
                return datetime.fromisoformat(task.last_run_time) if task.last_run_time else datetime.min
            except ValueError:
                return datetime.min
        if self.sort_column == "enabled":
            return task.enabled
        return str(getattr(task, self.sort_column, "")).casefold()

    def _refresh_sort_headings(self):
        for column in self.sortable_columns:
            direction = ""
            if column == self.sort_column:
                direction = " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(
                column,
                text=f"{self.column_labels[column]}{direction}",
                command=lambda col=column: self._set_sort(col),
            )

    def _selected_task(self):
        selected = self.tree.selection()
        if not selected:
            return None
        task_name = self.tree.item(selected[0])["values"][0]
        return self._find_task_by_name(task_name)

    def _add_task_window(self):
        self._task_popup("새 작업 추가")

    def _edit_task_window(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "수정할 작업을 목록에서 선택하세요.")
            return
        self._task_popup("작업 정보 수정", task)

    def _find_task_by_name(self, task_name: str):
        return next((task for task in self.cm.tasks if task.task_name == task_name), None)

    def _toggle_selected_task(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "예약을 중지하거나 재개할 작업을 선택하세요.")
            return
        enabled = not task.enabled
        if self.cm.set_task_enabled(task.task_name, enabled):
            self.refresh_list()
            logger.info("작업 예약 상태 변경: %s -> %s", task.task_name, enabled)
        else:
            messagebox.showerror("저장 오류", "작업 예약 상태를 저장하지 못했습니다.")

    def _duplicate_selected_task(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "복제할 작업을 목록에서 선택하세요.")
            return

        base_name = f"{task.task_name} (복사본)"
        new_name = base_name
        suffix = 2
        existing_names = {item.task_name for item in self.cm.tasks}
        while new_name in existing_names:
            new_name = f"{base_name} {suffix}"
            suffix += 1

        duplicate = Task(
            task_name=new_name,
            execution_time=task.execution_time,
            file_path=task.file_path,
            wakeup_enabled=task.wakeup_enabled,
            recipients=list(task.recipients),
            enabled=task.enabled,
            timeout_minutes=task.timeout_minutes,
        )
        if self.cm.add_task(duplicate):
            self.refresh_list()
            messagebox.showinfo("복제 완료", f"'{new_name}' 작업이 추가되었습니다.")
        else:
            messagebox.showerror("복제 오류", "작업을 복제하지 못했습니다.")

    def _run_selected_task_now(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "실행할 스케줄을 목록에서 선택하세요.")
            return
        if self.is_manual_run_active:
            messagebox.showinfo("실행 중", "이미 수동 실행 중입니다. 완료 후 다시 시도하세요.")
            return
        if not messagebox.askyesno("스케줄 실행", f"'{task.task_name}' 스케줄을 지금 실행할까요?"):
            return

        self.is_manual_run_active = True
        self.run_now_button.configure(state="disabled", text="실행 중...")
        threading.Thread(target=self._run_task_worker, args=(task,), daemon=True).start()

    def _run_task_worker(self, task: Task):
        logger.info("수동 스케줄 실행 시작: %s", task.task_name)
        try:
            result = self.executor.execute(
                task.file_path,
                timeout_seconds=task.timeout_minutes * 60,
            )
        except Exception as error:
            result = {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": f"작업 실행 중 오류 발생: {error}",
                "duration_seconds": 0,
            }

        self.cm.update_task_result(task.task_name, result)
        if self.notification_system:
            try:
                self.notification_system.send_report(
                    task.task_name,
                    result,
                    recipients=task.recipients,
                )
            except Exception:
                logger.exception("수동 실행 알림 처리 중 오류 발생: %s", task.task_name)

        self.root.after(0, lambda: self._on_manual_run_complete(task, result))

    def _on_manual_run_complete(self, task: Task, result: dict):
        self.is_manual_run_active = False
        self.run_now_button.configure(state="normal", text="지금 실행")
        self.refresh_list()

        if result["success"]:
            messagebox.showinfo("스케줄 실행 완료", f"'{task.task_name}' 실행이 완료되었습니다.")
        else:
            error_text = result.get("error") or "알 수 없는 오류"
            messagebox.showerror("스케줄 실행 실패", f"'{task.task_name}' 실행에 실패했습니다.\n\n{error_text}")

    def _show_task_details(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "실행 상세를 확인할 작업을 선택하세요.")
            return

        popup = ctk.CTkToplevel(self.root)
        popup.title(f"실행 상세 - {task.task_name}")
        popup.geometry("760x650")
        popup.transient(self.root)
        popup.grab_set()

        container = ctk.CTkFrame(popup, fg_color="transparent")
        container.pack(fill=ctk.BOTH, expand=True, padx=25, pady=20)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(4, weight=1)
        container.rowconfigure(6, weight=1)

        details = (
            ("작업명", task.task_name),
            ("최근 상태", task.last_run_status),
            ("최근 실행", self._format_last_run(task.last_run_time)),
            ("종료 코드", "-" if task.last_run_return_code is None else str(task.last_run_return_code)),
            ("실행 시간", "-" if task.last_run_duration_seconds is None else f"{task.last_run_duration_seconds:.2f}초"),
        )
        for row, (label, value) in enumerate(details):
            ctk.CTkLabel(container, text=label, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, sticky="nw", padx=(0, 15), pady=5)
            ctk.CTkLabel(container, text=value, anchor="w", justify="left", wraplength=600).grid(row=row, column=1, sticky="ew", pady=5)

        ctk.CTkLabel(container, text="표준 출력", font=ctk.CTkFont(weight="bold")).grid(row=5, column=0, sticky="nw", padx=(0, 15), pady=(15, 5))
        output_box = ctk.CTkTextbox(container, height=130)
        output_box.grid(row=5, column=1, sticky="nsew", pady=(15, 5))
        output_box.insert("1.0", task.last_run_output or "(출력 없음)")
        output_box.configure(state="disabled")

        ctk.CTkLabel(container, text="오류 출력", font=ctk.CTkFont(weight="bold")).grid(row=6, column=0, sticky="nw", padx=(0, 15), pady=5)
        error_box = ctk.CTkTextbox(container, height=130)
        error_box.grid(row=6, column=1, sticky="nsew", pady=5)
        error_box.insert("1.0", task.last_run_error or "(오류 없음)")
        error_box.configure(state="disabled")

        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(15, 0))
        ctk.CTkButton(button_frame, text="로그 파일 열기", command=self._open_log_file).pack(side=ctk.LEFT)
        ctk.CTkButton(button_frame, text="닫기", command=popup.destroy).pack(side=ctk.RIGHT)

    def _open_log_file(self):
        if not os.path.exists(self.LOG_PATH):
            messagebox.showinfo("로그 없음", "아직 생성된 로그 파일이 없습니다.")
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(self.LOG_PATH)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", self.LOG_PATH])
        except OSError as error:
            messagebox.showerror("로그 열기 오류", str(error))

    def _test_notification(self):
        if self.notification_system is None:
            messagebox.showwarning("알림 설정", "알림 시스템이 초기화되지 않았습니다.")
            return
        if self.is_notification_test_active:
            return

        self.is_notification_test_active = True
        self.notification_test_button.configure(state="disabled", text="전송 중...")
        threading.Thread(target=self._notification_test_worker, daemon=True).start()

    def _notification_test_worker(self):
        try:
            sent = self.notification_system.send_report(
                "알림 테스트",
                {
                    "success": True,
                    "return_code": 0,
                    "output": "S-cheduler 알림 테스트가 정상적으로 실행되었습니다.",
                    "error": "",
                    "duration_seconds": 0,
                },
            )
        except Exception:
            logger.exception("알림 테스트 중 오류 발생")
            sent = False
        self.root.after(0, lambda: self._on_notification_test_complete(sent))

    def _on_notification_test_complete(self, sent: bool):
        self.is_notification_test_active = False
        self.notification_test_button.configure(state="normal", text="알림 테스트")
        if sent:
            messagebox.showinfo("알림 테스트", "알림이 정상적으로 전송되었습니다.")
        else:
            messagebox.showerror("알림 테스트", "알림 전송에 실패했습니다. 설정과 로그를 확인하세요.")

    def _backup_config(self):
        default_name = f"s_cheduler_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
        path = filedialog.asksaveasfilename(
            title="설정 백업/내보내기",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        if self.cm.export_config(path):
            messagebox.showinfo("백업 완료", f"설정을 저장했습니다.\n{path}")
        else:
            messagebox.showerror("백업 실패", "설정 파일을 저장하지 못했습니다.")

    def _restore_config(self):
        path = filedialog.askopenfilename(
            title="설정 복원",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno("설정 복원", "현재 작업 목록을 선택한 파일로 교체할까요?"):
            return
        if self.cm.import_config(path):
            self.refresh_list()
            messagebox.showinfo("복원 완료", "설정을 복원했습니다.")
        else:
            messagebox.showerror("복원 실패", "설정 파일 형식이 올바르지 않거나 읽을 수 없습니다.")

    def _task_popup(self, title, task: Task = None):
        popup = ctk.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("620x780")
        popup.transient(self.root)
        popup.grab_set()

        container = ctk.CTkFrame(popup, fg_color="transparent")
        container.pack(fill=ctk.BOTH, expand=True, padx=30, pady=20)
        container.columnconfigure(0, weight=1)

        def create_entry(label_text, row, initial_value=""):
            ctk.CTkLabel(container, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, sticky="w", pady=(10, 0))
            entry = ctk.CTkEntry(container, placeholder_text=label_text)
            entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(5, 10))
            if initial_value:
                entry.insert(0, initial_value)
            return entry

        ent_name = create_entry("작업 이름 (고유 식별값)", 0, task.task_name if task else "")

        ctk.CTkLabel(container, text="실행 시각 설정 (HH:MM)", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=(10, 0))
        time_frame = ctk.CTkFrame(container, fg_color="transparent")
        time_frame.grid(row=3, column=0, sticky="w", pady=(5, 10))
        initial_hh, initial_mm = ("00", "00")
        if task and ":" in task.execution_time:
            initial_hh, initial_mm = task.execution_time.split(":", 1)

        def create_spinner(parent, initial_value, max_value):
            value_var = ctk.StringVar(value=initial_value)

            def change_value(delta):
                try:
                    current = int(value_var.get())
                except ValueError:
                    current = 0
                value_var.set(f"{(current + delta) % (max_value + 1):02d}")

            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(side=ctk.LEFT, padx=5)
            ctk.CTkButton(frame, text="▲", width=45, height=25, command=lambda: change_value(1)).pack(pady=2)
            ctk.CTkEntry(
                frame,
                textvariable=value_var,
                width=55,
                height=35,
                justify="center",
                font=ctk.CTkFont(size=20, weight="bold"),
            ).pack(pady=2)
            ctk.CTkButton(frame, text="▼", width=45, height=25, command=lambda: change_value(-1)).pack(pady=2)
            return value_var

        hh_var = create_spinner(time_frame, initial_hh, 23)
        ctk.CTkLabel(time_frame, text=":", font=ctk.CTkFont(size=24, weight="bold")).pack(side=ctk.LEFT, padx=10)
        mm_var = create_spinner(time_frame, initial_mm, 59)

        ctk.CTkLabel(container, text="파일 경로", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, sticky="w", pady=(10, 0))
        path_frame = ctk.CTkFrame(container, fg_color="transparent")
        path_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 10))
        ent_path = ctk.CTkEntry(path_frame, placeholder_text="선택된 파일 경로...")
        ent_path.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 10))
        if task:
            ent_path.insert(0, task.file_path)

        def browse_file():
            filename = filedialog.askopenfilename(title="실행할 파일을 선택하세요")
            if filename:
                ent_path.delete(0, ctk.END)
                ent_path.insert(0, os.path.normpath(filename))

        ctk.CTkButton(path_frame, text="찾기", width=80, command=browse_file).pack(side=ctk.RIGHT)

        enabled_var = ctk.BooleanVar(value=task.enabled if task else True)
        ctk.CTkCheckBox(container, text="이 작업의 예약 실행 활성화", variable=enabled_var).grid(row=6, column=0, sticky="w", pady=(12, 5))

        wakeup_var = ctk.BooleanVar(value=task.wakeup_enabled if task else True)
        ctk.CTkCheckBox(container, text="하드웨어 웨이크업(Wake-up) 사용", variable=wakeup_var).grid(row=7, column=0, sticky="w", pady=5)

        timeout_entry = create_entry("실행 제한 시간(분, 기본 30)", 8, str(task.timeout_minutes if task else 30))

        ctk.CTkLabel(container, text="알림 수신 이메일 (쉼표 또는 줄바꿈으로 구분)", font=ctk.CTkFont(weight="bold")).grid(row=10, column=0, sticky="w", pady=(10, 0))
        txt_emails = ctk.CTkTextbox(container, height=80)
        txt_emails.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(5, 20))
        if task:
            txt_emails.insert("1.0", "\n".join(task.recipients))

        def save():
            name = ent_name.get().strip()
            path = ent_path.get().strip()
            hh_text, mm_text = hh_var.get().strip(), mm_var.get().strip()
            timeout_text = timeout_entry.get().strip()
            if not name or not path:
                messagebox.showerror("입력 오류", "작업 이름과 파일 경로는 필수입니다.", parent=popup)
                return
            if not (hh_text.isdigit() and mm_text.isdigit() and 0 <= int(hh_text) <= 23 and 0 <= int(mm_text) <= 59):
                messagebox.showerror("입력 오류", "실행 시각은 00:00부터 23:59 사이여야 합니다.", parent=popup)
                return
            if not timeout_text.isdigit() or int(timeout_text) < 1:
                messagebox.showerror("입력 오류", "실행 제한 시간은 1분 이상이어야 합니다.", parent=popup)
                return

            raw_emails = txt_emails.get("1.0", ctk.END).replace(",", "\n")
            emails = [email.strip() for email in raw_emails.splitlines() if email.strip()]
            new_task = Task(
                task_name=name,
                execution_time=f"{int(hh_text):02d}:{int(mm_text):02d}",
                file_path=path,
                wakeup_enabled=wakeup_var.get(),
                recipients=emails,
                enabled=enabled_var.get(),
                timeout_minutes=int(timeout_text),
            )

            if task:
                # 작업 정보를 수정해도 기존 실행 이력은 유지합니다.
                new_task.last_run_status = task.last_run_status
                new_task.last_run_time = task.last_run_time
                new_task.last_run_return_code = task.last_run_return_code
                new_task.last_run_output = task.last_run_output
                new_task.last_run_error = task.last_run_error
                new_task.last_run_duration_seconds = task.last_run_duration_seconds
                saved = self.cm.update_task(task.task_name, new_task)
            else:
                saved = self.cm.add_task(new_task)

            if not saved:
                messagebox.showerror("저장 오류", "작업을 저장하지 못했습니다. 이름 중복이나 파일 권한을 확인하세요.", parent=popup)
                return
            self.refresh_list()
            popup.grab_release()
            popup.destroy()

        ctk.CTkButton(container, text="💾 설정 저장하기", height=40, font=ctk.CTkFont(size=14, weight="bold"), command=save).grid(row=12, column=0, columnspan=2, pady=10, sticky="ew")
        ctk.CTkButton(container, text="취소", fg_color="gray30", hover_color="gray40", command=popup.destroy).grid(row=13, column=0, columnspan=2, pady=(0, 5), sticky="ew")

    def _delete_task(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "삭제할 작업을 목록에서 선택하세요.")
            return
        if messagebox.askyesno("삭제 확인", f"'{task.task_name}' 작업을 정말로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            if self.cm.delete_task(task.task_name):
                self.refresh_list()
            else:
                messagebox.showerror("삭제 오류", "작업을 삭제하지 못했습니다.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gui = GUIManager(ConfigManager(), PowerManager())
    gui.run()
