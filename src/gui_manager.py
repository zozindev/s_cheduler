import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.utils.config_manager import ConfigManager
from src.models.task import Task
import os

class GUIManager:
    """슼케줄러의 GUI를 관리하는 클래스 (tkinter 기반)"""

    def __init__(self, config_manager: ConfigManager, power_manager: None):
        self.cm = config_manager
        self.pm = power_manager  # PowerManager 인스턴스 저장
        self.root = tk.Tk()
        self.root.title("슼케줄러 (S-cheduler) - v2.0")
        self.root.geometry("800x450") # 조금 더 넓게 조정
        
        self._setup_main_window()

    def _setup_main_window(self):
        """메인 스케줄 리스트 화면 구성"""
        # 리스트 표시용 Treeview
        columns = ("task_name", "execution_time", "file_path", "wakeup", "last_status")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        
        # (생략: 기존 treeview 설정 로직 ...)
        self.tree.heading("task_name", text="작업명")
        self.tree.heading("execution_time", text="실행 시각")
        self.tree.heading("file_path", text="파일 경로")
        self.tree.heading("wakeup", text="절전 해제")
        self.tree.heading("last_status", text="최근 상태")

        self.tree.column("task_name", width=100)
        self.tree.column("execution_time", width=80)
        self.tree.column("file_path", width=300)
        self.tree.column("wakeup", width=80)
        self.tree.column("last_status", width=100)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 시스템 전원 제어용 프레임 (Stay-Awake 토글)
        power_frame = tk.LabelFrame(self.root, text="시스템 전원 제어")
        power_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.stay_awake_var = tk.BooleanVar(value=False)
        def on_toggle_stay_awake():
            if self.pm:
                self.pm.set_sleep_prevention(self.stay_awake_var.get())
        
        tk.Checkbutton(
            power_frame, 
            text="프로그램 실행 중 시스템이 자동으로 절전 모드에 진입하지 않도록 방지 (관리자 권한 불필요)", 
            variable=self.stay_awake_var,
            command=on_toggle_stay_awake
        ).pack(side=tk.LEFT, padx=10, pady=5)

        # 하단 버튼부
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(btn_frame, text="스케줄 추가", command=self._add_task_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="스케줄 수정", command=self._edit_task_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="스케줄 삭제", command=self._delete_task).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="새로고침", command=self.refresh_list).pack(side=tk.RIGHT, padx=5)

        self.refresh_list()

    def refresh_list(self):
        """작업 목록 새로고침"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.cm.load_config()
        for task in self.cm.tasks:
            self.tree.insert("", tk.END, values=(
                task.task_name,
                task.execution_time,
                task.file_path,
                "사용" if task.wakeup_enabled else "미사용",
                task.last_run_status
            ))

    def _add_task_window(self):
        """작업 추가 팝업"""
        self._task_popup("작업 추가")

    def _edit_task_window(self):
        """작업 수정 팝업"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("경고", "수정할 작업을 선택하세요.")
            return
        
        task_name = self.tree.item(selected[0])['values'][0]
        task = next((t for t in self.cm.tasks if t.task_name == task_name), None)
        if task:
            self._task_popup("작업 수정", task)

    def _task_popup(self, title, task: Task = None):
        """작업 추가/수정을 위한 통합 팝업"""
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("500x350")

        # 입력 필드들
        tk.Label(popup, text="작업 이름 (Unique):").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ent_name = tk.Entry(popup)
        ent_name.grid(row=0, column=1, fill=tk.X, padx=10, pady=5)
        if task:
            ent_name.insert(0, task.task_name)
            ent_name.config(state="disabled" if task else "normal")

        tk.Label(popup, text="실행 시각 (HH:MM):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        ent_time = tk.Entry(popup)
        ent_time.grid(row=1, column=1, fill=tk.X, padx=10, pady=5)
        if task: ent_time.insert(0, task.execution_time)

        tk.Label(popup, text="파일 절대 경로:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        path_frame = tk.Frame(popup)
        path_frame.grid(row=2, column=1, fill=tk.X, padx=10, pady=5)
        ent_path = tk.Entry(path_frame)
        ent_path.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if task: ent_path.insert(0, task.file_path)
        
        def browse_file():
            filename = filedialog.askopenfilename()
            if filename:
                ent_path.delete(0, tk.END)
                ent_path.insert(0, os.path.normpath(filename))
        
        tk.Button(path_frame, text="찾기", command=browse_file).pack(side=tk.RIGHT)

        # 웨이크업 체크박스
        wakeup_var = tk.BooleanVar(value=task.wakeup_enabled if task else True)
        tk.Checkbutton(popup, text="절전 모드 해제(Wake-up) 기능 사용", variable=wakeup_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)

        # 이메일 리스트
        tk.Label(popup, text="수신 이메일 (쉼표로 구분):").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        ent_emails = tk.Entry(popup)
        ent_emails.grid(row=4, column=1, fill=tk.X, padx=10, pady=5)
        if task: ent_emails.insert(0, ", ".join(task.recipients))

        def save():
            name = ent_name.get()
            time_val = ent_time.get()
            path = ent_path.get()
            emails = [e.strip() for e in ent_emails.get().split(",") if e.strip()]
            
            # 간단한 유효성 검사
            if not name or not time_val or not path:
                messagebox.showerror("오류", "모든 필드를 입력하세요.")
                return
            
            new_task = Task(
                task_name=name,
                execution_time=time_val,
                file_path=path,
                wakeup_enabled=wakeup_var.get(),
                recipients=emails
            )

            if task: # 수정 모드
                self.cm.tasks = [new_task if t.task_name == name else t for t in self.cm.tasks]
                self.cm.save_config()
            else: # 추가 모드
                self.cm.add_task(new_task)
            
            self.refresh_list()
            popup.destroy()

        tk.Button(popup, text="저장", command=save, width=15, bg="skyblue").grid(row=5, column=0, columnspan=2, pady=20)

    def _delete_task(self):
        """작업 삭제"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("경고", "삭제할 작업을 선택하세요.")
            return
        
        task_name = self.tree.item(selected[0])['values'][0]
        if messagebox.askyesno("확인", f"'{task_name}' 작업을 삭제하시겠습니까?"):
            self.cm.tasks = [t for t in self.cm.tasks if t.task_name != task_name]
            self.cm.save_config()
            self.refresh_list()

    def run(self):
        """GUI 실행 루프"""
        self.root.mainloop()

if __name__ == "__main__":
    from src.utils.config_manager import ConfigManager
    cm = ConfigManager()
    gui = GUIManager(cm)
    gui.run()
