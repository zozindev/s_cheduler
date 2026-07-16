import logging
import os
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox

import customtkinter as ctk
from customtkinter.windows.widgets.core_rendering import DrawEngine

from src.core.executor import TaskExecutor
from src.core.power_manager import PowerManager
from src.models.task import Task
from src.utils.config_manager import ConfigManager
from src.utils.notification_manager import NotificationSystem

logger = logging.getLogger(__name__)


class SmoothSwitch(ctk.CTkSwitch):
    """A compact switch with a visible state border and eased knob movement."""

    def __init__(self, *args, **kwargs):
        self._animation_after_id = None
        self._animation_steps = 10
        self._animation_delay = 14
        previous_drawing_method = DrawEngine.preferred_drawing_method
        DrawEngine.preferred_drawing_method = "polygon_shapes"
        try:
            super().__init__(*args, **kwargs)
        finally:
            DrawEngine.preferred_drawing_method = previous_drawing_method
        # Polygon shapes expose a real canvas outline for the knob. The default
        # font-based renderer cannot draw a separate border around the white knob.
        self._draw_engine.preferred_drawing_method = "polygon_shapes"
        self._draw()

    def _button_position(self):
        try:
            coords = self._canvas.coords("slider_parts")
            return coords[0] if coords else None
        except (AttributeError, tk.TclError):
            return None

    def _update_button_border(self):
        if not hasattr(self, "_canvas"):
            return
        border_color = "#007AFF" if self._check_state else "#8E8E93"
        outline = self._apply_appearance_mode(border_color)
        for item in self._canvas.find_withtag("slider_parts"):
            if self._canvas.type(item) in {"oval", "rectangle", "polygon"}:
                self._canvas.itemconfig(
                    item,
                    outline=outline,
                    width=self._apply_widget_scaling(2),
                )

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        self._update_button_border()

    def _on_enter(self, event=0):
        super()._on_enter(event)
        self._update_button_border()

    def _on_leave(self, event=0):
        super()._on_leave(event)
        self._update_button_border()

    def _animate_button(self, start_position, target_position, step=0):
        try:
            if not self.winfo_exists():
                self._animation_after_id = None
                return
            progress = min(1.0, (step + 1) / self._animation_steps)
            eased_progress = 1 - (1 - progress) ** 3
            desired_position = start_position + (target_position - start_position) * eased_progress
            current_position = self._button_position()
            if current_position is not None:
                self._canvas.move("slider_parts", desired_position - current_position, 0)
            if step + 1 < self._animation_steps:
                self._animation_after_id = self.after(
                    self._animation_delay,
                    lambda: self._animate_button(start_position, target_position, step + 1),
                )
            else:
                self._animation_after_id = None
        except tk.TclError:
            self._animation_after_id = None

    def toggle(self, event=None):
        if self._state != tk.NORMAL:
            return
        if self._animation_after_id is not None:
            try:
                self.after_cancel(self._animation_after_id)
            except tk.TclError:
                pass
            self._animation_after_id = None

        start_position = self._button_position()
        self.set(not self._check_state)
        target_position = self._button_position()
        if start_position is not None and target_position is not None:
            self._canvas.move("slider_parts", start_position - target_position, 0)
            self._animate_button(start_position, target_position)

        if self._command is not None:
            self._command()

    def destroy(self):
        if self._animation_after_id is not None:
            try:
                self.after_cancel(self._animation_after_id)
            except tk.TclError:
                pass
            self._animation_after_id = None
        super().destroy()


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
            "last_run_time",
            "last_status",
        }
        self.column_labels = {
            "task_name": "작업명",
            "enabled": "예약 상태",
            "execution_time": "실행 시각",
            "next_run": "다음 실행",
            "file_path": "파일 경로",
            "last_run_time": "최근 실행",
            "last_status": "실행 결과",
        }
        self.is_manual_run_active = False
        self.selected_task_name = None
        self._last_render_key = None

        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")

        self._set_windows_app_identity()
        self.root = ctk.CTk()
        self._configure_app_icon()
        self.font_family = self._configure_typography()
        self.root.title("스케줄러 (S-cheduler) v3.0")
        self.root.geometry("1180x760")
        self.root.minsize(900, 560)
        self._setup_main_window()

    @staticmethod
    def _set_windows_app_identity():
        """Give Windows a stable application identity for taskbar grouping."""
        if os.name != "nt":
            return
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "zozindev.s_cheduler"
            )
        except (AttributeError, OSError):
            logger.debug("Windows 앱 ID를 설정하지 못했습니다.", exc_info=True)

    def _configure_app_icon(self):
        """Use the same lightweight S-cheduler mark in the title bar and taskbar."""
        # Keep the mark in code so a source checkout does not need an additional
        # binary asset. Tk uses this image for the window and taskbar icon.
        icon = tk.PhotoImage(width=32, height=32)
        icon.put("#007AFF", to=(0, 0, 32, 32))
        icon.put("#FFFFFF", to=(7, 14, 11, 18))
        icon.put("#FFFFFF", to=(9, 17, 14, 21))
        icon.put("#FFFFFF", to=(12, 19, 17, 23))
        icon.put("#FFFFFF", to=(15, 16, 21, 20))
        icon.put("#FFFFFF", to=(19, 12, 24, 17))
        icon.put("#FFFFFF", to=(22, 9, 27, 14))
        self._app_icon = icon
        self.root.iconphoto(True, self._app_icon)

    def _configure_typography(self):
        """Use Nanum Gothic for CTk defaults and native Tk menus when available."""
        available_fonts = set(tkfont.families(self.root))
        requested_families = ("나눔고딕", "NanumGothic")
        family = next((name for name in requested_families if name in available_fonts), "NanumGothic")
        ctk.ThemeManager.theme["CTkFont"]["family"] = family
        self.root.option_add("*Font", (family, 10))
        self.root.option_add("*Menu*Font", (family, 10))
        if family not in available_fonts:
            logger.warning("나눔고딕 폰트를 찾지 못해 시스템 대체 글꼴을 사용합니다: %s", family)
        return family

    def _setup_main_window(self):
        self.root.configure(fg_color="#F5F5F7")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))
        header_frame.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_frame,
            text="S-cheduler",
            text_color="#1D1D1F",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(anchor="w")
        #ctk.CTkLabel(
        #    title_frame,
        #    text="오늘 예약된 작업",
        #    text_color="#86868B",
        #    font=ctk.CTkFont(size=14),
        #).pack(anchor="w", pady=(2, 0))

        header_actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_actions.grid(row=0, column=1, sticky="e", pady=(4, 0))
        self.add_button = ctk.CTkButton(
            header_actions,
            text="+",
            width=44,
            height=44,
            corner_radius=22,
            font=ctk.CTkFont(size=26, weight="normal"),
            fg_color="#007AFF",
            hover_color="#1A84FF",
            border_width=0,
            command=self._add_task_window,
        )
        self.add_button.pack(side=ctk.LEFT, padx=(0, 10))
        self.more_button = ctk.CTkButton(
            header_actions,
            text="⋯",
            width=40,
            height=40,
            corner_radius=20,
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color="transparent",
            hover_color="#E5E5EA",
            text_color="#1D1D1F",
            command=self._show_overflow_menu,
        )
        self.more_button.pack(side=ctk.LEFT)

        self.stay_awake_var = ctk.BooleanVar(value=False)

        content_frame = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            bg="#F5F5F7",
            bd=0,
            sashwidth=8,
            sashrelief=tk.FLAT,
            sashcursor="sb_h_double_arrow",
        )
        content_frame.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
        self.content_paned_window = content_frame

        list_panel = ctk.CTkFrame(content_frame, fg_color="transparent")
        content_frame.add(list_panel, minsize=360, stretch="always")
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(1, weight=1)

        list_header = ctk.CTkFrame(list_panel, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        list_header.grid_columnconfigure(0, weight=1)
        self.task_count_label = ctk.CTkLabel(
            list_header,
            text="",
            text_color="#86868B",
            font=ctk.CTkFont(size=13),
        )
        self.task_count_label.grid(row=0, column=0, sticky="w")
        self.sort_option_map = {
            "작업명": "task_name",
            "실행 시각": "execution_time",
            "다음 실행": "next_run",
            "최근 실행": "last_run_time",
            "예약 상태": "enabled",
            "실행 결과": "last_status",
            "파일 경로": "file_path",
        }
        sort_controls = ctk.CTkFrame(list_header, fg_color="transparent")
        sort_controls.grid(row=0, column=1, sticky="e")
        self.sort_option_menu = ctk.CTkOptionMenu(
            sort_controls,
            values=list(self.sort_option_map),
            width=130,
            height=30,
            corner_radius=10,
            fg_color="#FFFFFF",
            button_color="#FFFFFF",
            button_hover_color="#E5E5EA",
            text_color="#1D1D1F",
            dropdown_fg_color="#FFFFFF",
            dropdown_hover_color="#E5E5EA",
            dropdown_text_color="#1D1D1F",
            command=self._set_sort_from_label,
        )
        self.sort_option_menu.pack(side=ctk.LEFT, padx=(0, 6))
        self.sort_direction_button = ctk.CTkButton(
            sort_controls,
            text="↑",
            width=32,
            height=30,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#E5E5EA",
            text_color="#1D1D1F",
            command=lambda: self._set_sort(self.sort_column),
        )
        self.sort_direction_button.pack(side=ctk.LEFT)

        self.task_list_frame = ctk.CTkScrollableFrame(
            list_panel,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6",
        )
        self.task_list_frame.grid(row=1, column=0, sticky="nsew")

        self.detail_panel = ctk.CTkFrame(
            content_frame,
            fg_color="#FFFFFF",
            corner_radius=20,
            border_width=1,
            border_color="#E5E5EA",
        )
        content_frame.add(self.detail_panel, minsize=300, width=370, stretch="always")
        self.detail_panel.grid_columnconfigure(0, weight=1)
        self.detail_panel.grid_rowconfigure(1, weight=1)
        self.detail_panel.bind("<Configure>", self._on_detail_panel_configure, add="+")
        self._detail_value_labels = []

        self.detail_title = ctk.CTkLabel(
            self.detail_panel,
            text="실행 상세",
            text_color="#1D1D1F",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.detail_title.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        self.detail_content = ctk.CTkScrollableFrame(
            self.detail_panel,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6",
        )
        self.detail_content.grid(row=1, column=0, sticky="nsew", padx=12)

        detail_actions = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        detail_actions.grid(row=2, column=0, sticky="ew", padx=24, pady=(12, 24))
        detail_actions.grid_columnconfigure(0, weight=1)
        self.run_now_button = ctk.CTkButton(
            detail_actions,
            text="이 스케줄 실행",
            height=40,
            corner_radius=12,
            fg_color="#007AFF",
            hover_color="#1A84FF",
            command=self._run_selected_task_now,
        )
        self.run_now_button.grid(row=0, column=0, sticky="ew")
        #ctk.CTkButton(
        #    detail_actions,
        #    text="로그 파일 열기",
        #    height=34,
        #    corner_radius=10,
        #    fg_color="transparent",
        #    hover_color="#F2F2F7",
        #    text_color="#007AFF",
        #    command=self._open_log_file,
        #).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.delete_button = ctk.CTkButton(
            detail_actions,
            text="이 스케줄 삭제",
            height=34,
            corner_radius=10,
            fg_color="#FF3B30",
            hover_color="#D70015",
            text_color="#FFFFFF",
            command=self._delete_task,
        )
        self.delete_button.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.root.bind_all("<F5>", self._on_refresh_hotkey, add="+")
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

    def _on_refresh_hotkey(self, _event=None):
        self.refresh_list()
        return "break"

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
            self.selected_task_name = new_name
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
        popup.iconphoto(True, self._app_icon)
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
        ctk.CTkButton(
            button_frame,
            text="로그 파일 열기",
            fg_color="#007AFF",
            hover_color="#1A84FF",
            corner_radius=10,
            command=self._open_log_file,
        ).pack(side=ctk.LEFT)
        ctk.CTkButton(
            button_frame,
            text="닫기",
            fg_color="#F2F2F7",
            hover_color="#E5E5EA",
            text_color="#1D1D1F",
            corner_radius=10,
            command=popup.destroy,
        ).pack(side=ctk.RIGHT)

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
        popup.iconphoto(True, self._app_icon)
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
            ctk.CTkButton(
                frame,
                text="▲",
                width=45,
                height=25,
                fg_color="#F2F2F7",
                hover_color="#E5E5EA",
                text_color="#1D1D1F",
                corner_radius=8,
                command=lambda: change_value(1),
            ).pack(pady=2)
            ctk.CTkEntry(
                frame,
                textvariable=value_var,
                width=55,
                height=35,
                justify="center",
                font=ctk.CTkFont(size=20, weight="bold"),
            ).pack(pady=2)
            ctk.CTkButton(
                frame,
                text="▼",
                width=45,
                height=25,
                fg_color="#F2F2F7",
                hover_color="#E5E5EA",
                text_color="#1D1D1F",
                corner_radius=8,
                command=lambda: change_value(-1),
            ).pack(pady=2)
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

        ctk.CTkButton(
            path_frame,
            text="찾기",
            width=80,
            fg_color="#F2F2F7",
            hover_color="#E5E5EA",
            text_color="#1D1D1F",
            corner_radius=10,
            command=browse_file,
        ).pack(side=ctk.RIGHT)

        wakeup_var = ctk.BooleanVar(value=task.wakeup_enabled if task else True)
        ctk.CTkCheckBox(container, text="하드웨어 웨이크업(Wake-up) 사용", variable=wakeup_var).grid(row=6, column=0, sticky="w", pady=(12, 5))

        ctk.CTkLabel(container, text="알림 수신 이메일 (쉼표 또는 줄바꿈으로 구분)", font=ctk.CTkFont(weight="bold")).grid(row=7, column=0, sticky="w", pady=(10, 0))
        txt_emails = ctk.CTkTextbox(container, height=80)
        txt_emails.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(5, 20))
        if task:
            txt_emails.insert("1.0", "\n".join(task.recipients))

        def save():
            name = ent_name.get().strip()
            path = ent_path.get().strip()
            hh_text, mm_text = hh_var.get().strip(), mm_var.get().strip()
            if not name or not path:
                messagebox.showerror("입력 오류", "작업 이름과 파일 경로는 필수입니다.", parent=popup)
                return
            if not (hh_text.isdigit() and mm_text.isdigit() and 0 <= int(hh_text) <= 23 and 0 <= int(mm_text) <= 59):
                messagebox.showerror("입력 오류", "실행 시각은 00:00부터 23:59 사이여야 합니다.", parent=popup)
                return

            raw_emails = txt_emails.get("1.0", ctk.END).replace(",", "\n")
            emails = [email.strip() for email in raw_emails.splitlines() if email.strip()]
            new_task = Task(
                task_name=name,
                execution_time=f"{int(hh_text):02d}:{int(mm_text):02d}",
                file_path=path,
                wakeup_enabled=wakeup_var.get(),
                recipients=emails,
                # 새 작업은 항상 활성화하고 제한 시간은 단순한 기본값으로
                # 고정합니다. 기존 작업의 중지 상태는 편집 시 유지합니다.
                enabled=task.enabled if task else True,
                timeout_minutes=30,
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
            self.selected_task_name = new_task.task_name
            self.refresh_list()
            popup.grab_release()
            popup.destroy()

        ctk.CTkButton(
            container,
            text="설정 저장하기",
            height=40,
            corner_radius=12,
            fg_color="#007AFF",
            hover_color="#1A84FF",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=save,
        ).grid(row=9, column=0, columnspan=2, pady=10, sticky="ew")
        ctk.CTkButton(
            container,
            text="취소",
            fg_color="#F2F2F7",
            hover_color="#E5E5EA",
            text_color="#1D1D1F",
            corner_radius=12,
            command=popup.destroy,
        ).grid(row=10, column=0, columnspan=2, pady=(0, 5), sticky="ew")

    def _delete_task(self):
        task = self._selected_task()
        if task is None:
            messagebox.showwarning("선택 오류", "삭제할 작업을 목록에서 선택하세요.")
            return
        if messagebox.askyesno(
            "삭제 확인",
            f"'{task.task_name}' 작업을 정말로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            icon="warning",
        ):
            if self.cm.delete_task(task.task_name):
                self.selected_task_name = None
                self.refresh_list()
            else:
                messagebox.showerror("삭제 오류", "작업을 삭제하지 못했습니다.")

    # The card-based layout keeps the main screen quiet while retaining every
    # existing action in the selected-task detail panel or overflow menu.
    def _show_overflow_menu(self):
        menu = tk.Menu(self.root, tearoff=False, font=(self.font_family, 10), activebackground="#E5E5EA")
        task = self._selected_task()
        if task is not None:
            menu.add_command(label="작업 수정", command=self._edit_task_window)
            menu.add_command(label="작업 복제", command=self._duplicate_selected_task)
            menu.add_command(label="예약 재개" if not task.enabled else "예약 중지", command=self._toggle_selected_task)
            menu.add_command(label="작업 삭제", command=self._delete_task)
            menu.add_separator()

        menu.add_command(label="설정 백업", command=self._backup_config)
        menu.add_command(label="설정 복원", command=self._restore_config)
        menu.add_command(label="새로고침", command=self.refresh_list)
        menu.add_checkbutton(
            label="프로그램 절전 방지",
            variable=self.stay_awake_var,
            command=self._toggle_stay_awake,
        )
        try:
            menu.tk_popup(self.more_button.winfo_rootx(), self.more_button.winfo_rooty() + self.more_button.winfo_height())
        finally:
            menu.grab_release()

    def _set_sort_from_label(self, label: str):
        column = self.sort_option_map.get(label)
        if not column or column == self.sort_column:
            return
        self.sort_column = column
        self.sort_reverse = False
        self._refresh_sort_headings()
        self.refresh_list()

    def _toggle_stay_awake(self):
        enabled = self.stay_awake_var.get()
        self.pm.set_sleep_prevention(enabled)
        logger.info("프로그램 절전 방지: %s", enabled)

    def _create_task_row(self, task: Task):
        selected = task.task_name == self.selected_task_name
        card = ctk.CTkFrame(
            self.task_list_frame,
            fg_color="#EEF5FF" if selected else "#FFFFFF",
            corner_radius=16,
            border_width=1,
            border_color="#007AFF" if selected else "#E5E5EA",
            height=82,
        )
        card.pack(fill=ctk.X, pady=(0, 10))
        card.pack_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=12)
        body.grid_columnconfigure(0, weight=1)
        name_label = ctk.CTkLabel(
            body,
            text=task.task_name,
            text_color="#1D1D1F",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="ew")

        meta = f"다음 실행 {self._format_next_run(self.cm.get_next_run_datetime(task))}" if task.enabled else "예약 중지"
        if task.last_run_time:
            meta += f"  ·  최근 실행 {self._format_last_run(task.last_run_time)}"
        if task.last_run_status != "Not Started":
            meta += f"  ·  결과 {self._status_label(task.last_run_status)}"
        meta_label = ctk.CTkLabel(
            body,
            text=meta,
            text_color="#86868B",
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
        )
        meta_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=(4, 14), pady=10)
        enabled_var = ctk.BooleanVar(value=task.enabled)
        SmoothSwitch(
            controls,
            text="",
            variable=enabled_var,
            width=54,
            height=28,
            switch_width=42,
            switch_height=24,
            border_width=1,
            border_color="#D1D1D6",
            progress_color="#007AFF",
            button_color="#FFFFFF",
            button_hover_color="#E5F1FF",
            command=lambda name=task.task_name, value=enabled_var: self._toggle_task_from_row(name, value.get()),
        ).pack(anchor="e")

        self.task_cards[task.task_name] = (card, selected)
        self._bind_row_widget(card, task.task_name)
        self._bind_row_widget(body, task.task_name)
        self._bind_row_widget(name_label, task.task_name)
        self._bind_row_widget(meta_label, task.task_name)
        for widget in (card, body, name_label, meta_label, controls):
            self._bind_card_hover(widget, card, task.task_name)

    @staticmethod
    def _status_label(status: str):
        return {"Success": "성공", "Fail": "실패", "Failed": "실패"}.get(status, str(status))

    def _bind_row_widget(self, widget, task_name: str):
        widget.bind("<Button-1>", lambda _event, name=task_name: self._select_task(name), add="+")
        widget.bind("<Double-Button-1>", lambda _event, name=task_name: self._edit_task_by_name(name), add="+")

    def _bind_card_hover(self, widget, card, task_name: str):
        widget.bind(
            "<Enter>",
            lambda _event: card.configure(
                fg_color="#E4F0FF" if self.selected_task_name == task_name else "#FBFBFD"
            ),
            add="+",
        )
        widget.bind(
            "<Leave>",
            lambda _event: card.configure(
                fg_color="#EEF5FF" if self.selected_task_name == task_name else "#FFFFFF"
            ),
            add="+",
        )

    def _select_task(self, task_name: str):
        if self._find_task_by_name(task_name) is None:
            return
        self.selected_task_name = task_name
        for name, (card, _selected) in getattr(self, "task_cards", {}).items():
            selected = name == task_name
            card.configure(
                fg_color="#EEF5FF" if selected else "#FFFFFF",
                border_color="#007AFF" if selected else "#E5E5EA",
            )
            self.task_cards[name] = (card, selected)
        self._update_detail_panel()

    def _edit_task_by_name(self, task_name: str):
        self.selected_task_name = task_name
        self._edit_task_window()

    def _toggle_task_from_row(self, task_name: str, enabled: bool):
        if self.cm.set_task_enabled(task_name, enabled):
            self.selected_task_name = task_name
            self.refresh_list()
            logger.info("작업 예약 상태 변경: %s -> %s", task_name, enabled)
        else:
            self.refresh_list()
            messagebox.showerror("저장 오류", "작업 예약 상태를 저장하지 못했습니다.")

    def _update_detail_panel(self):
        for child in self.detail_content.winfo_children():
            child.destroy()
        self._detail_value_labels = []

        task = self._selected_task()
        if task is None:
            self.detail_title.configure(text="실행 상세")
            ctk.CTkLabel(
                self.detail_content,
                text="작업을 선택하세요.\n선택한 작업의 상태와 실행 결과가 여기에 표시됩니다.",
                text_color="#86868B",
                font=ctk.CTkFont(size=13),
                justify="left",
                anchor="w",
            ).pack(fill=ctk.X, padx=12, pady=24)
            self.run_now_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
            return

        self.detail_title.configure(text=task.task_name)
        self.run_now_button.configure(state="normal")
        self.delete_button.configure(state="normal")
        fields = (
            ("다음 실행", self._format_next_run(self.cm.get_next_run_datetime(task)) if task.enabled else "예약 중지"),
            ("최근 실행", self._format_last_run(task.last_run_time)),
            ("실행 결과", self._status_label(task.last_run_status)),
            ("종료 코드", "-" if task.last_run_return_code is None else str(task.last_run_return_code)),
            ("실행 시간", "-" if task.last_run_duration_seconds is None else f"{task.last_run_duration_seconds:.2f}초"),
            ("예약 상태", "활성" if task.enabled else "중지"),
            ("제한 시간", f"{task.timeout_minutes}분"),
            ("절전 방지", "사용" if task.wakeup_enabled else "사용 안 함"),
            ("파일 경로", task.file_path),
        )
        for label, value in fields:
            row = ctk.CTkFrame(self.detail_content, fg_color="transparent")
            row.pack(fill=ctk.X, padx=12, pady=3)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label, text_color="#86868B", font=ctk.CTkFont(size=12), anchor="w").grid(row=0, column=0, sticky="nw", padx=(0, 12))
            value_label = ctk.CTkLabel(
                row,
                text=value,
                text_color="#1D1D1F",
                font=ctk.CTkFont(size=12),
                anchor="w",
                justify="left",
                wraplength=self._detail_value_wraplength(),
            )
            value_label.grid(row=0, column=1, sticky="ew")
            self._detail_value_labels.append(value_label)

        for label, value in (("표준 출력", task.last_run_output), ("오류 출력", task.last_run_error)):
            ctk.CTkLabel(self.detail_content, text=label, text_color="#86868B", font=ctk.CTkFont(size=12), anchor="w").pack(fill=ctk.X, padx=12, pady=(14, 4))
            text_box = ctk.CTkTextbox(self.detail_content, height=76, corner_radius=10, border_width=1, border_color="#E5E5EA")
            text_box.pack(fill=ctk.X, padx=12)
            text_box.insert("1.0", value or "출력 없음")
            text_box.configure(state="disabled")

        ctk.CTkButton(
            self.detail_content,
            text="전체 실행 상세",
            height=34,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#F2F2F7",
            text_color="#007AFF",
            command=self._show_task_details,
        ).pack(fill=ctk.X, padx=12, pady=(16, 12))

    def _detail_value_wraplength(self):
        return max(180, self.detail_panel.winfo_width() - 140)

    def _on_detail_panel_configure(self, _event=None):
        if not hasattr(self, "detail_panel"):
            return
        self.detail_title.configure(wraplength=max(240, self.detail_panel.winfo_width() - 48))
        wraplength = self._detail_value_wraplength()
        for label in getattr(self, "_detail_value_labels", []):
            label.configure(wraplength=wraplength)

    def _refresh_sort_headings(self):
        if not hasattr(self, "sort_option_menu"):
            return
        label = next(
            (
                option_label
                for option_label, column in self.sort_option_map.items()
                if column == self.sort_column
            ),
            self.column_labels[self.sort_column],
        )
        self.sort_option_menu.set(label)
        self.sort_direction_button.configure(text="↓" if self.sort_reverse else "↑")

    def _selected_task(self):
        if not self.selected_task_name:
            return None
        return self._find_task_by_name(self.selected_task_name)

    @staticmethod
    def _task_state_signature(tasks):
        """Return only values whose changes should trigger a visual redraw."""
        return tuple(
            (
                task.task_name,
                task.execution_time,
                task.file_path,
                task.wakeup_enabled,
                tuple(task.recipients),
                task.last_run_status,
                task.last_run_time,
                task.enabled,
                task.timeout_minutes,
                task.last_run_return_code,
                task.last_run_output,
                task.last_run_error,
                task.last_run_duration_seconds,
            )
            for task in tasks
        )

    @staticmethod
    def _get_scroll_position(scrollable_frame):
        try:
            return scrollable_frame._parent_canvas.yview()[0]
        except (AttributeError, tk.TclError):
            return None

    def _restore_scroll_positions(self, list_position, detail_position):
        def restore():
            try:
                if not self.root.winfo_exists():
                    return
                if list_position is not None:
                    self.task_list_frame._parent_canvas.yview_moveto(list_position)
                if detail_position is not None:
                    self.detail_content._parent_canvas.yview_moveto(detail_position)
            except (AttributeError, tk.TclError):
                return

        self.root.after_idle(restore)

    def refresh_list(self):
        """Reload tasks and redraw only when the visible state has changed."""
        self.cm.load_config()
        tasks = list(self.cm.tasks)
        render_key = (
            datetime.now().date(),
            self.sort_column,
            self.sort_reverse,
            self._task_state_signature(tasks),
        )
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key

        list_position = self._get_scroll_position(self.task_list_frame)
        detail_position = self._get_scroll_position(self.detail_content)
        task_names = {task.task_name for task in self.cm.tasks}
        if self.selected_task_name not in task_names:
            self.selected_task_name = None

        for child in self.task_list_frame.winfo_children():
            child.destroy()
        self.task_cards = {}

        display_tasks = self._sort_tasks_for_display(tasks)
        active_count = sum(1 for task in display_tasks if task.enabled)
        self.task_count_label.configure(text=f"{len(display_tasks)}개 작업 · {active_count}개 활성")
        if not display_tasks:
            ctk.CTkLabel(
                self.task_list_frame,
                text="등록된 작업이 없습니다.\n+ 버튼으로 작업을 추가하세요.",
                text_color="#86868B",
                font=ctk.CTkFont(size=14),
                justify="center",
            ).pack(fill=ctk.BOTH, expand=True, pady=80)
        else:
            for task in display_tasks:
                self._create_task_row(task)
        self._update_detail_panel()
        self._refresh_sort_headings()
        self._restore_scroll_positions(list_position, detail_position)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gui = GUIManager(ConfigManager(), PowerManager())
    gui.run()
