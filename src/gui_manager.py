import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import os
import logging
from src.utils.config_manager import ConfigManager
from src.core.power_manager import PowerManager
from src.models.task import Task

# 로그 설정
logger = logging.getLogger(__name__)

# 기본 테마 설정 (Blue, Dark/Light 자동)
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class GUIManager:
    """슼케줄러의 GUI를 관리하는 클래스 (CustomTkinter 기반)"""

    def __init__(self, config_manager: ConfigManager, power_manager: PowerManager):
        self.cm = config_manager
        self.pm = power_manager
        
        # 메인 윈도우 설정
        self.root = ctk.CTk()
        self.root.title("슼케줄러 (S-cheduler) v2.2 - Modern UI")
        self.root.geometry("900x550")
        
        # 레이아웃 구성
        self._setup_main_window()

    def _setup_main_window(self):
        """메인 스케줄 리스트 화면 구성"""
        # 1. 상단 제목 및 설명
        header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        header_frame.pack(fill=ctk.X, padx=20, pady=(20, 10))
        
        title_label = ctk.CTkLabel(
            header_frame, 
            text="📅 작업 스케줄 관리", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side=ctk.LEFT)

        # 2. 시스템 전원 제어 (Stay-Awake) - 상단 우측 배치
        power_frame = ctk.CTkFrame(self.root)
        power_frame.pack(fill=ctk.X, padx=20, pady=10)
        
        self.stay_awake_var = ctk.BooleanVar(value=False)
        def on_toggle_stay_awake():
            if self.pm:
                self.pm.set_sleep_prevention(self.stay_awake_var.get())
                status = "활성화" if self.stay_awake_var.get() else "비활성화"
                logger.info(f"시스템 절전 방지 모드: {status}")

        awake_switch = ctk.CTkSwitch(
            power_frame, 
            text="프로그램 실행 중 자동 절전 모드 진입 방지 (Stay-Awake)", 
            variable=self.stay_awake_var,
            command=on_toggle_stay_awake,
            font=ctk.CTkFont(size=12)
        )
        awake_switch.pack(side=ctk.LEFT, padx=15, pady=10)

        # 3. 리스트 표시용 Treeview (표준 ttk 사용하되 스타일 조정)
        list_frame = ctk.CTkFrame(self.root)
        list_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=10)

        # Treeview 스타일 설정
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2a2d2e", 
                        foreground="white", 
                        rowheight=30, 
                        fieldbackground="#343638",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map("Treeview", background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat",
                        font=('Arial', 10, 'bold'))

        columns = ("task_name", "execution_time", "file_path", "wakeup", "last_status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", style="Treeview")
        
        # 더블 클릭 이벤트 바인딩
        self.tree.bind("<Double-1>", lambda event: self._edit_task_window())
        
        self.tree.heading("task_name", text="작업명")
        self.tree.heading("execution_time", text="실행 시각")
        self.tree.heading("file_path", text="파일 경로")
        self.tree.heading("wakeup", text="절전 해제")
        self.tree.heading("last_status", text="최근 상태")

        self.tree.column("task_name", width=120, anchor="center")
        self.tree.column("execution_time", width=100, anchor="center")
        self.tree.column("file_path", width=350)
        self.tree.column("wakeup", width=100, anchor="center")
        self.tree.column("last_status", width=120, anchor="center")

        # 스크롤바 추가
        scrollbar = ctk.CTkScrollbar(list_frame, orientation="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)
        scrollbar.pack(side=ctk.RIGHT, fill=ctk.Y)

        # 4. 하단 버튼부
        btn_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        btn_frame.pack(fill=ctk.X, padx=20, pady=(10, 20))

        # 주요 동작 버튼 (왼쪽)
        ctk.CTkButton(
            btn_frame, text="✚ 스케줄 추가", width=120, 
            command=self._add_task_window
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            btn_frame, text="✎ 수정", width=100, fg_color="gray30", hover_color="gray40",
            command=self._edit_task_window
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            btn_frame, text="🗑 삭제", width=100, fg_color="#d32f2f", hover_color="#b71c1c",
            command=self._delete_task
        ).pack(side=ctk.LEFT, padx=5)

        # 유틸리티 버튼 (오른쪽) - 초록색 강조 버튼으로 변경
        ctk.CTkButton(
            btn_frame, text="🔄 새로고침", width=120, fg_color="#2e7d32", hover_color="#1b5e20",
            command=self.refresh_list
        ).pack(side=ctk.RIGHT, padx=5)

        self.refresh_list()

    def refresh_list(self):
        """작업 목록 새로고침"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.cm.load_config()
        for task in self.cm.tasks:
            self.tree.insert("", ctk.END, values=(
                task.task_name,
                task.execution_time,
                task.file_path,
                "✅ 사용" if task.wakeup_enabled else "❌ 미사용",
                task.last_run_status
            ))

    def _add_task_window(self):
        self._task_popup("새 작업 추가")

    def _edit_task_window(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "수정할 작업을 목록에서 선택하세요.")
            return
        
        task_name = self.tree.item(selected[0])['values'][0]
        task = next((t for t in self.cm.tasks if t.task_name == task_name), None)
        if task:
            self._task_popup("작업 정보 수정", task)

    def _task_popup(self, title, task: Task = None):
        """작업 추가/수정용 모던 팝업"""
        popup = ctk.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("600x530") # 크기 확대 (잘림 방지)
        popup.after(100, popup.lift) # 팝업을 맨 위로

        # 중앙 정렬을 위한 컨테이너 (반응형 설정)
        container = ctk.CTkFrame(popup, fg_color="transparent")
        container.pack(fill=ctk.BOTH, expand=True, padx=30, pady=20)
        container.columnconfigure(0, weight=1) # 가로 확장 가능하게 설정

        # 입력 필드들
        def create_entry(label_text, row, initial_value="", is_disabled=False):
            ctk.CTkLabel(container, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, sticky="w", pady=(10, 0))
            entry = ctk.CTkEntry(container, placeholder_text=label_text)
            entry.grid(row=row+1, column=0, columnspan=2, sticky="ew", pady=(5, 10))
            if initial_value:
                entry.insert(0, initial_value)
            if is_disabled:
                entry.configure(state="disabled", fg_color="gray25")
            return entry

        # 작업 이름
        ent_name = create_entry("작업 이름 (고유 식별값)", 0, task.task_name if task else "")
        
        # 실행 시각 설정 UI (HH:MM Spinner)
        ctk.CTkLabel(container, text="실행 시각 설정 (HH:MM)", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=(10, 0))
        time_frame = ctk.CTkFrame(container, fg_color="transparent")
        time_frame.grid(row=3, column=0, sticky="w", pady=(5, 10))

        initial_hh, initial_mm = ("00", "00")
        if task and ":" in task.execution_time:
            initial_hh, initial_mm = task.execution_time.split(":")

        def create_spinner(parent, initial_val, max_val):
            val_var = ctk.StringVar(value=initial_val)
            
            def change_val(delta):
                try:
                    current = int(val_var.get())
                    new_val = (current + delta) % (max_val + 1)
                    val_var.set(f"{new_val:02d}")
                except ValueError:
                    val_var.set("00")

            frame = ctk.CTkFrame(parent, fg_color="gray30")
            frame.pack(side=ctk.LEFT, padx=2)
            
            ctk.CTkButton(frame, text="▲", width=35, height=25, fg_color="transparent", hover_color="gray40", command=lambda: change_val(1)).pack()
            ctk.CTkLabel(frame, textvariable=val_var, font=ctk.CTkFont(size=18, weight="bold")).pack(pady=2)
            ctk.CTkButton(frame, text="▼", width=35, height=25, fg_color="transparent", hover_color="gray40", command=lambda: change_val(-1)).pack()
            return val_var

        hh_var = create_spinner(time_frame, initial_hh, 23)
        ctk.CTkLabel(time_frame, text=":", font=ctk.CTkFont(size=24, weight="bold")).pack(side=ctk.LEFT, padx=10)
        mm_var = create_spinner(time_frame, initial_mm, 59)

        ctk.CTkLabel(container, text="파일 경로", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, sticky="w", pady=(10, 0))
        path_frame = ctk.CTkFrame(container, fg_color="transparent")
        path_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 10))
        path_frame.columnconfigure(0, weight=1) # 파일 경로창 확장성 부여
        
        ent_path = ctk.CTkEntry(path_frame, placeholder_text="선택된 파일 경로...")
        ent_path.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 10))
        if task: ent_path.insert(0, task.file_path)
        
        def browse_file():
            filename = filedialog.askopenfilename(title="실행할 파일을 선택하세요")
            if filename:
                ent_path.delete(0, ctk.END)
                ent_path.insert(0, os.path.normpath(filename))
        
        ctk.CTkButton(path_frame, text="찾기", width=80, command=browse_file).pack(side=ctk.RIGHT)

        wakeup_var = ctk.BooleanVar(value=task.wakeup_enabled if task else True)
        ctk.CTkCheckBox(container, text="하드웨어 웨이크업(Wake-up) 사용", variable=wakeup_var).grid(row=6, column=0, sticky="w", pady=15)

        # 이메일 수신자 (Textbox로 변경하여 줄바꿈 지원)
        ctk.CTkLabel(container, text="알림 수신 이메일 (쉼표 또는 줄바꿈으로 구분)", font=ctk.CTkFont(weight="bold")).grid(row=7, column=0, sticky="w", pady=(10, 0))
        txt_emails = ctk.CTkTextbox(container, height=80)
        txt_emails.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(5, 25))
        if task:
            txt_emails.insert("1.0", "\n".join(task.recipients))

        def save():
            name = ent_name.get().strip()
            time_val = f"{hh_var.get()}:{mm_var.get()}"
            path = ent_path.get().strip()
            
            # 이메일 처리 (쉼표와 줄바꿈 모두 대응)
            raw_email_text = txt_emails.get("1.0", ctk.END).replace(",", "\n")
            emails = [e.strip() for e in raw_email_text.split("\n") if e.strip()]
            
            if not all([name, path]):
                messagebox.showerror("입력 오류", "모든 필수 항목을 입력해주세요.")
                return
            
            # 중복 검사 로직
            existing_names = [t.task_name for t in self.cm.tasks]
            
            if task: # 수정 모드
                if name != task.task_name and name in existing_names:
                    messagebox.showerror("중복 오류", f"'{name}' 이름은 이미 사용 중입니다.")
                    return
            else: # 추가 모드
                if name in existing_names:
                    messagebox.showerror("중복 오류", f"'{name}' 이름은 이미 사용 중입니다.")
                    return

            new_task = Task(name, time_val, path, wakeup_var.get(), emails)

            try:
                if task: # 수정
                    # 기존 이름을 가진 요소를 찾아 새 작업 정보로 교체
                    self.cm.tasks = [new_task if t.task_name == task.task_name else t for t in self.cm.tasks]
                    self.cm.save_config()
                else: # 추가
                    self.cm.add_task(new_task)
                
                self.refresh_list()
                popup.destroy()
            except Exception as e:
                messagebox.showerror("저장 오류", f"설정을 저장하는 중 오류가 발생했습니다: {e}")

        # 저장 버튼 (강조색)
        ctk.CTkButton(container, text="💾 설정 저장하기", height=40, font=ctk.CTkFont(size=14, weight="bold"), command=save).grid(row=9, column=0, columnspan=2, pady=10, sticky="ew")

    def _delete_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "삭제할 작업을 목록에서 선택하세요.")
            return
        
        task_name = self.tree.item(selected[0])['values'][0]
        if messagebox.askyesno("삭제 확인", f"'{task_name}' 작업을 정말로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            self.cm.tasks = [t for t in self.cm.tasks if t.task_name != task_name]
            self.cm.save_config()
            self.refresh_list()

    def run(self):
        """GUI 실행 루프"""
        self.root.mainloop()

if __name__ == "__main__":
    # 독립 실행 테스트용
    logging.basicConfig(level=logging.INFO)
    cm = ConfigManager()
    pm = PowerManager()
    gui = GUIManager(cm, pm)
    gui.run()
