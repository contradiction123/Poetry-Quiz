"""
主程序入口
GUI界面和自动化流程控制
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
from datetime import datetime
from typing import Optional

from config import Config
# 延迟导入所有可能慢的模块，加快启动速度
# from screen_capture import ScreenCapture
# from ocr_engine import OCREngine
# from question_parser import QuestionParser
# from ai_client import AIClientFactory
# from click_handler import ClickHandler
from database import Database


class MainWindow:
    """主窗口类"""
    
    def __init__(self):
        """初始化主窗口"""
        self.root = tk.Tk()
        self.root.title("诗词答题自动化工具")
        # 只设置宽度，高度让窗口根据内容自适应
        self.root.geometry("900x0")
        # 设置最小尺寸，确保窗口不会太小
        self.root.minsize(900, 600)
        self.root.resizable(True, True)
        
        # 设置窗口背景色
        self.root.configure(bg='#f0f0f0')
        
        # 配置样式
        self.setup_styles()
        
        # 运行状态
        self.is_running = False
        self.stop_flag = False
        
        # 初始化配置（快速操作）
        self.config = Config()
        
        # 初始化各个模块（全部延迟初始化，加快启动速度）
        self.screen_capture = None
        self.ocr_engine = None
        self.question_parser = None
        self.ai_client = None
        self.click_handler = None
        self.database = None  # 延迟初始化数据库
        self.material_matcher = None  # 材料匹配器
        
        # 识别区域坐标 (x, y, width, height)，None表示全屏
        self.capture_region = self.config.get('capture_region', None)
        
        # OCR 初始化状态
        self.ocr_initializing = False
        
        # 游戏模式
        self.game_mode = self.config.get('game_mode', 'poetry')
        
        # 根据游戏模式设置窗口标题
        title_text = "📚 诗词答题自动化工具" if self.game_mode == "poetry" else "🔮 材料匹配自动化工具"
        self.root.title(title_text)
        
        # 创建界面（先显示窗口，给用户快速响应）
        self.create_widgets()
        
        # 创建完所有组件后，让窗口根据内容自动调整大小
        self.root.update_idletasks()
        # 获取内容所需的最小尺寸
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        # 设置窗口大小，确保所有内容都能显示
        self.root.geometry(f"{width}x{height}")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化日志
        self.log_message("程序启动")
        
        # 在后台线程中初始化数据库和检查配置（不阻塞UI）
        threading.Thread(target=self._init_background, daemon=True).start()
    
    def _init_background(self):
        """后台初始化（不阻塞UI）"""
        try:
            # 初始化数据库
            self.database = Database()
            # 检查配置
            self.root.after(0, self.check_config)
            # 更新统计信息
            self.root.after(0, self.update_statistics)
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log_message(f"后台初始化失败: {err}"))
    
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 14, 'bold'), background='#f0f0f0')
        style.configure('Status.TLabel', font=('Microsoft YaHei UI', 10), background='#f0f0f0')
        style.configure('Info.TLabel', font=('Microsoft YaHei UI', 9), background='#f0f0f0')
        
        # 按钮样式
        style.configure('Primary.TButton', font=('Microsoft YaHei UI', 10))
        style.configure('Success.TButton', font=('Microsoft YaHei UI', 10))
        style.configure('Danger.TButton', font=('Microsoft YaHei UI', 10))
        style.configure('Info.TButton', font=('Microsoft YaHei UI', 10))
    
    def create_widgets(self):
        """创建界面组件"""
        # 标题区域
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_text = "📚 诗词答题自动化工具" if self.game_mode == "poetry" else "🔮 材料匹配自动化工具"
        self.title_label = tk.Label(title_frame, text=title_text, 
                              font=('Microsoft YaHei UI', 16, 'bold'),
                              bg='#2c3e50', fg='white')
        self.title_label.pack(pady=15)
        
        # 游戏模式选择（放在最上面，横跨整个宽度）
        mode_container = tk.Frame(self.root, bg='#f0f0f0')
        mode_container.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        mode_frame = ttk.LabelFrame(mode_container, text="🎯 游戏模式", padding=15)
        mode_frame.pack(fill=tk.X)
        
        self.game_mode_var = tk.StringVar(value=self.game_mode)
        
        # 创建模式选择按钮容器，使用pack布局让按钮紧凑排列
        mode_buttons_frame = tk.Frame(mode_frame, bg='white')
        mode_buttons_frame.pack(fill=tk.X)
        
        # 定义游戏模式列表（方便后续扩展）
        game_modes = [
            ("📚 诗词答题", "poetry"),
            ("🔮 材料匹配", "material"),
        ]
        
        # 动态创建模式选择按钮，使用pack布局让它们紧凑排列
        for idx, (text, value) in enumerate(game_modes):
            radio = ttk.Radiobutton(mode_buttons_frame, text=text, 
                                   variable=self.game_mode_var, 
                                   value=value,
                                   command=self.on_game_mode_changed)
            # 使用pack布局，减少间距，让按钮紧凑排列
            radio.pack(side=tk.LEFT, padx=(10 if idx == 0 else 5), pady=5)
        
        # 主内容区域
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 10))
        
        # 左侧：状态和按钮区域
        left_frame = tk.Frame(main_frame, bg='#f0f0f0')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        # 状态显示区域
        status_frame = ttk.LabelFrame(left_frame, text="📊 运行状态", padding=15)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # API Key状态（使用网格布局）
        api_frame = tk.Frame(status_frame, bg='white')
        api_frame.pack(fill=tk.X, pady=5)
        tk.Label(api_frame, text="🔑 API Key：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.api_key_status_label = tk.Label(api_frame, text="未配置", 
                                             font=('Microsoft YaHei UI', 9, 'bold'),
                                             bg='white', fg='red')
        self.api_key_status_label.pack(side=tk.LEFT, padx=5)
        
        # 分隔线
        ttk.Separator(status_frame, orient='horizontal').pack(fill=tk.X, pady=8)
        
        # 运行状态
        status_info_frame = tk.Frame(status_frame, bg='white')
        status_info_frame.pack(fill=tk.X, pady=5)
        tk.Label(status_info_frame, text="⚡ 状态：", font=('Microsoft YaHei UI', 10), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.status_label = tk.Label(status_info_frame, text="就绪", 
                                    font=('Microsoft YaHei UI', 10, 'bold'),
                                    bg='white', fg='#27ae60')
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # 题目显示
        question_info_frame = tk.Frame(status_frame, bg='white')
        question_info_frame.pack(fill=tk.X, pady=5)
        tk.Label(question_info_frame, text="📝 题目：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.question_label = tk.Label(question_info_frame, text="等待识别...", 
                                       font=('Microsoft YaHei UI', 9),
                                       bg='white', fg='#34495e', wraplength=300, justify='left')
        self.question_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 答案显示
        answer_info_frame = tk.Frame(status_frame, bg='white')
        answer_info_frame.pack(fill=tk.X, pady=5)
        tk.Label(answer_info_frame, text="✅ 答案：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.answer_label = tk.Label(answer_info_frame, text="-", 
                                    font=('Microsoft YaHei UI', 9, 'bold'),
                                    bg='white', fg='#e74c3c')
        self.answer_label.pack(side=tk.LEFT, padx=5)
        
        # 识别区域状态
        region_info_frame = tk.Frame(status_frame, bg='white')
        region_info_frame.pack(fill=tk.X, pady=5)
        tk.Label(region_info_frame, text="📐 区域：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        region_text = "全屏"
        region_color = '#f39c12'
        if self.capture_region:
            r = self.capture_region
            region_text = f"已设置 ({r['x']},{r['y']}) {r['width']}x{r['height']}"
            region_color = '#27ae60'
        self.region_label = tk.Label(region_info_frame, text=region_text, 
                                    font=('Microsoft YaHei UI', 9, 'bold'),
                                    bg='white', fg=region_color)
        self.region_label.pack(side=tk.LEFT, padx=5)
        
        # OCR 模块状态
        ocr_status_frame = tk.Frame(status_frame, bg='white')
        ocr_status_frame.pack(fill=tk.X, pady=5)
        tk.Label(ocr_status_frame, text="🔍 OCR：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.ocr_status_label = tk.Label(ocr_status_frame, text="未就绪", 
                                       font=('Microsoft YaHei UI', 9, 'bold'),
                                       bg='white', fg='#f39c12')
        self.ocr_status_label.pack(side=tk.LEFT, padx=5)
        
        # 统计信息
        stats_info_frame = tk.Frame(status_frame, bg='white')
        stats_info_frame.pack(fill=tk.X, pady=5)
        tk.Label(stats_info_frame, text="📈 统计：", font=('Microsoft YaHei UI', 9), 
                bg='white', anchor='w').pack(side=tk.LEFT)
        self.stats_label = tk.Label(stats_info_frame, text="-", 
                                   font=('Microsoft YaHei UI', 9),
                                   bg='white', fg='#3498db')
        self.stats_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 按钮区域
        button_frame = ttk.LabelFrame(left_frame, text="🎮 控制面板", padding=15)
        button_frame.pack(fill=tk.X)
        
        # 按钮使用网格布局，更整齐
        self.start_button = ttk.Button(button_frame, text="▶ 开始运行", 
                                      command=self.start_automation,
                                      style='Success.TButton')
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        
        self.stop_button = ttk.Button(button_frame, text="⏹ 停止运行", 
                                     command=self.stop_automation, 
                                     state=tk.DISABLED,
                                     style='Danger.TButton')
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        self.config_button = ttk.Button(button_frame, text="⚙ 配置设置", 
                                       command=self.show_config_dialog,
                                       style='Info.TButton')
        self.config_button.grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        
        self.stats_button = ttk.Button(button_frame, text="📊 查看统计", 
                                     command=self.show_statistics_dialog,
                                     style='Info.TButton')
        self.stats_button.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        self.region_button = ttk.Button(button_frame, text="📐 设置区域", 
                                       command=self.start_region_selection,
                                       style='Info.TButton')
        self.region_button.grid(row=2, column=0, padx=5, pady=5, sticky='ew')
        
        self.clear_region_button = ttk.Button(button_frame, text="🔄 全屏模式", 
                                             command=self.clear_capture_region,
                                             style='Info.TButton')
        self.clear_region_button.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        
        self.init_ocr_button = ttk.Button(button_frame, text="🔍 初始化OCR", 
                                         command=self.manual_init_ocr,
                                         style='Info.TButton')
        self.init_ocr_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # 配置列权重，使按钮等宽
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        # 右侧：日志显示区域
        log_frame = ttk.LabelFrame(main_frame, text="📋 运行日志", padding=10)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 日志文本框，使用更好的字体和颜色
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD,
                                                  font=('Consolas', 9),
                                                  bg='#1e1e1e', fg='#d4d4d4',
                                                  insertbackground='white',
                                                  selectbackground='#264f78')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
    
    def log_message(self, message: str):
        """
        添加日志消息
        参数:
            message: 日志消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        
        # 插入文本
        start_pos = self.log_text.index(tk.END)
        self.log_text.insert(tk.END, log_entry)
        end_pos = self.log_text.index(tk.END)
        
        # 根据消息类型设置颜色
        if "成功" in message or "完成" in message or "已保存" in message:
            color = "#4ec9b0"
        elif "错误" in message or "失败" in message:
            color = "#f48771"
        elif "警告" in message:
            color = "#dcdcaa"
        else:
            color = "#d4d4d4"
        
        # 应用颜色标签
        tag_name = f"log_{len(self.log_text.get('1.0', tk.END))}"
        self.log_text.tag_add(tag_name, start_pos, end_pos)
        self.log_text.tag_config(tag_name, foreground=color)
        
        self.log_text.see(tk.END)
        
        # 限制日志行数
        max_lines = self.config.get('ui.log_max_lines', 100)
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > max_lines:
            self.log_text.delete("1.0", f"{len(lines) - max_lines}.0")
        
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def update_status(self, status: str, question: str = "", answer: str = ""):
        """
        更新状态显示
        参数:
            status: 状态文本
            question: 题目文本
            answer: 答案文本
        """
        # 根据状态设置颜色
        status_colors = {
            '就绪': '#27ae60',
            '运行中': '#3498db',
            '已停止': '#95a5a6',
            '配置错误': '#e74c3c'
        }
        color = status_colors.get(status, '#34495e')
        self.status_label.config(text=status, fg=color)
        
        if question:
            # 限制题目显示长度
            display_question = question[:50] + "..." if len(question) > 50 else question
            self.question_label.config(text=display_question)
        if answer:
            self.answer_label.config(text=answer, fg='#e74c3c')
        self.root.update_idletasks()
    
    def on_game_mode_changed(self):
        """游戏模式改变时的回调"""
        new_mode = self.game_mode_var.get()
        self.game_mode = new_mode
        self.config.set('game_mode', new_mode)
        self.config.save_config()
        mode_name = "诗词答题" if new_mode == "poetry" else "材料匹配"
        # 更新标题
        title_text = "📚 诗词答题自动化工具" if new_mode == "poetry" else "🔮 材料匹配自动化工具"
        self.title_label.config(text=title_text)
        self.root.title(title_text)
        self.log_message(f"游戏模式已切换为: {mode_name}")
    
    def check_config(self):
        """检查配置有效性"""
        # 更新API Key状态显示
        api_key = self.config.get('ai_providers.deepseek.api_key', '')
        if api_key and api_key.strip():
            self.api_key_status_label.config(text="✓ 已配置", fg='#27ae60')
        else:
            self.api_key_status_label.config(text="✗ 未配置", fg='#e74c3c')
        
        is_valid, error = self.config.validate()
        if not is_valid:
            self.log_message(f"配置检查失败: {error}")
            self.update_status("配置错误", "", "")
    
    def show_config_dialog(self):
        """显示配置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙ 配置设置")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg='#f0f0f0')
        
        # 先隐藏窗口，避免闪烁
        dialog.withdraw()
        
        # 设置窗口大小
        dialog_width = 550
        dialog_height = 400
        
        # 更新主窗口信息，确保获取准确的坐标
        self.root.update_idletasks()
        dialog.update_idletasks()
        
        # 获取主窗口的绝对坐标（相对于整个虚拟屏幕，支持多显示器）
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        
        # 计算中心位置（相对于主窗口）
        center_x = root_x + (root_width - dialog_width) // 2
        center_y = root_y + (root_height - dialog_height) // 2
        
        # 设置对话框位置和大小（使用绝对坐标，支持多显示器）
        dialog.geometry(f"{dialog_width}x{dialog_height}+{center_x}+{center_y}")
        
        # 显示窗口
        dialog.deiconify()
        
        # 获取当前API Key
        current_api_key = self.config.get('ai_providers.deepseek.api_key', '')
        is_configured = bool(current_api_key and current_api_key.strip())
        
        # 标题
        title_frame = tk.Frame(dialog, bg='#2c3e50', height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="⚙ 配置设置", font=('Microsoft YaHei UI', 14, 'bold'),
                bg='#2c3e50', fg='white').pack(pady=12)
        
        # 内容区域
        content_frame = tk.Frame(dialog, bg='#f0f0f0')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # API Key状态显示
        status_frame = ttk.LabelFrame(content_frame, text="🔑 API Key 状态", padding=15)
        status_frame.pack(fill=tk.X, pady=10)
        
        status_text = "✓ 已配置" if is_configured else "✗ 未配置"
        status_color = "#27ae60" if is_configured else "#e74c3c"
        tk.Label(status_frame, text=status_text, font=('Microsoft YaHei UI', 11, 'bold'),
                fg=status_color, bg='white').pack()
        
        # API Key输入区域
        input_frame = ttk.LabelFrame(content_frame, text="📝 输入 API Key", padding=15)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Label(input_frame, text="请输入或修改 DeepSeek API Key:", 
                font=('Microsoft YaHei UI', 10), bg='white').pack(anchor=tk.W, pady=5)
        
        # 输入框
        api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(input_frame, textvariable=api_key_var, 
                                  font=('Consolas', 10), show="*", width=50)
        api_key_entry.pack(pady=10, fill=tk.X, ipady=5)
        
        # 如果已配置，显示提示
        if is_configured:
            hint_label = tk.Label(input_frame, text="💡 提示：输入新的API Key可更新配置", 
                                 font=('Microsoft YaHei UI', 8),
                                 fg='#7f8c8d', bg='white')
            hint_label.pack(anchor=tk.W, pady=5)
        
        # 按钮区域
        button_frame = tk.Frame(content_frame, bg='#f0f0f0')
        button_frame.pack(pady=15)
        
        # 保存按钮
        def save_config():
            api_key = api_key_var.get().strip()
            if api_key:
                self.config.set('ai_providers.deepseek.api_key', api_key)
                self.config.save_config()
                self.log_message("API Key配置已保存")
                self.check_config()  # 更新状态显示
                dialog.destroy()
                messagebox.showinfo("✅ 成功", "API Key配置已保存")
            else:
                messagebox.showwarning("⚠ 警告", "API Key不能为空")
        
        # 清除按钮（可选）
        def clear_config():
            if messagebox.askyesno("确认", "确定要清除API Key配置吗？"):
                self.config.set('ai_providers.deepseek.api_key', '')
                self.config.save_config()
                self.log_message("API Key配置已清除")
                self.check_config()  # 更新状态显示
                dialog.destroy()
                messagebox.showinfo("✅ 成功", "API Key配置已清除")
        
        save_btn = ttk.Button(button_frame, text="💾 保存", command=save_config, 
                              style='Success.TButton', width=12)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        if is_configured:
            clear_btn = ttk.Button(button_frame, text="🗑 清除", command=clear_config,
                                   style='Danger.TButton', width=12)
            clear_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy,
                                style='Info.TButton', width=12)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # 设置焦点
        api_key_entry.focus()
    
    def start_region_selection(self):
        """启动区域框选模式"""
        self.log_message("请在屏幕上拖拽框选识别区域...")
        
        # 延迟一下再隐藏主窗口，让日志显示出来
        self.root.after(500, self._do_region_selection)
    
    def _do_region_selection(self):
        """执行区域框选"""
        # 隐藏主窗口
        self.root.withdraw()
        time.sleep(0.3)
        
        # 截取全屏作为背景
        import mss
        sct = mss.mss()
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        from PIL import Image
        bg_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        
        # 创建全屏覆盖窗口
        overlay = tk.Toplevel()
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-topmost', True)
        overlay.configure(cursor='cross')
        
        # 在画布上显示截图 + 半透明遮罩
        from PIL import ImageTk, ImageEnhance
        # 降低亮度作为遮罩效果
        dark_image = ImageEnhance.Brightness(bg_image).enhance(0.4)
        canvas_width = monitor['width']
        canvas_height = monitor['height']
        
        canvas = tk.Canvas(overlay, width=canvas_width, height=canvas_height, 
                          highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # 保存引用防止被GC
        overlay._dark_photo = ImageTk.PhotoImage(dark_image)
        overlay._bright_photo = ImageTk.PhotoImage(bg_image)
        canvas.create_image(0, 0, anchor=tk.NW, image=overlay._dark_photo)
        
        # 提示文字
        canvas.create_text(canvas_width // 2, 30, 
                          text="拖拽鼠标框选识别区域，松开确认 | ESC 取消",
                          font=('Microsoft YaHei UI', 16, 'bold'),
                          fill='white')
        
        # 框选状态
        select_state = {'start_x': 0, 'start_y': 0, 'rect': None, 'bright_region': None}
        
        def on_mouse_down(event):
            select_state['start_x'] = event.x
            select_state['start_y'] = event.y
            if select_state['rect']:
                canvas.delete(select_state['rect'])
            if select_state['bright_region']:
                canvas.delete(select_state['bright_region'])
        
        def on_mouse_drag(event):
            x1 = min(select_state['start_x'], event.x)
            y1 = min(select_state['start_y'], event.y)
            x2 = max(select_state['start_x'], event.x)
            y2 = max(select_state['start_y'], event.y)
            
            # 删除旧矩形
            if select_state['rect']:
                canvas.delete(select_state['rect'])
            if select_state['bright_region']:
                canvas.delete(select_state['bright_region'])
            
            # 在选中区域显示原始亮度的截图
            if x2 - x1 > 5 and y2 - y1 > 5:
                cropped = bg_image.crop((x1, y1, x2, y2))
                overlay._crop_photo = ImageTk.PhotoImage(cropped)
                select_state['bright_region'] = canvas.create_image(
                    x1, y1, anchor=tk.NW, image=overlay._crop_photo)
            
            # 画红色边框
            select_state['rect'] = canvas.create_rectangle(
                x1, y1, x2, y2, outline='#ff4444', width=2)
        
        def on_mouse_up(event):
            x1 = min(select_state['start_x'], event.x)
            y1 = min(select_state['start_y'], event.y)
            x2 = max(select_state['start_x'], event.x)
            y2 = max(select_state['start_y'], event.y)
            
            width = x2 - x1
            height = y2 - y1
            
            if width < 50 or height < 50:
                # 区域太小，忽略
                overlay.destroy()
                self.root.deiconify()
                self.log_message("框选区域太小，已取消")
                return
            
            # 保存区域
            self.capture_region = {
                'x': x1,
                'y': y1,
                'width': width,
                'height': height
            }
            self.config.set('capture_region', self.capture_region)
            
            # 更新UI
            self.region_label.config(
                text=f"已设置 ({x1},{y1}) {width}x{height}",
                fg='#27ae60')
            
            overlay.destroy()
            self.root.deiconify()
            self.log_message(f"识别区域已设置: ({x1},{y1}) {width}x{height}")
        
        def on_escape(event):
            overlay.destroy()
            self.root.deiconify()
            self.log_message("已取消区域框选")
        
        canvas.bind('<ButtonPress-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        overlay.bind('<Escape>', on_escape)
        overlay.focus_force()
    
    def clear_capture_region(self):
        """清除识别区域，恢复全屏模式"""
        self.capture_region = None
        self.config.set('capture_region', None)
        self.region_label.config(text="全屏", fg='#f39c12')
        self.log_message("已恢复全屏截图模式")
    
    def update_statistics(self):
        """更新统计信息显示"""
        if self.database is None:
            # 数据库还未初始化，显示默认值
            self.stats_label.config(text="统计: 总计 0 题, 正确 0 题, 准确率 0.0%")
            return
        """更新统计信息显示"""
        try:
            stats = self.database.get_statistics()
            stats_text = f"统计：总计 {stats['total_questions']} 题，正确 {stats['correct_answers']} 题，准确率 {stats['accuracy_rate']}%"
            self.stats_label.config(text=stats_text)
        except Exception as e:
            self.stats_label.config(text="统计：获取失败")
    
    def show_statistics_dialog(self):
        """显示统计信息对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("📊 答题统计")
        dialog.transient(self.root)
        dialog.configure(bg='#f0f0f0')
        
        # 先隐藏窗口，避免闪烁
        dialog.withdraw()
        
        # 设置窗口大小
        dialog_width = 700
        dialog_height = 600
        
        # 更新主窗口信息，确保获取准确的坐标
        self.root.update_idletasks()
        dialog.update_idletasks()
        
        # 获取主窗口的绝对坐标（相对于整个虚拟屏幕，支持多显示器）
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        
        # 计算中心位置（相对于主窗口）
        center_x = root_x + (root_width - dialog_width) // 2
        center_y = root_y + (root_height - dialog_height) // 2
        
        # 设置对话框位置和大小（使用绝对坐标，支持多显示器）
        dialog.geometry(f"{dialog_width}x{dialog_height}+{center_x}+{center_y}")
        
        # 显示窗口
        dialog.deiconify()
        
        if self.database is None:
            messagebox.showwarning("提示", "数据库尚未初始化，请稍候再试")
            dialog.destroy()
            return
        
        try:
            stats = self.database.get_statistics()
            history = self.database.get_recent_history(20)
            
            # 标题
            title_frame = tk.Frame(dialog, bg='#2c3e50', height=50)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text="📊 答题统计", font=('Microsoft YaHei UI', 14, 'bold'),
                    bg='#2c3e50', fg='white').pack(pady=12)
            
            # 内容区域
            content_frame = tk.Frame(dialog, bg='#f0f0f0')
            content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
            
            # 统计信息区域
            stats_frame = ttk.LabelFrame(content_frame, text="📈 统计信息", padding=15)
            stats_frame.pack(fill=tk.X, pady=10)
            
            # 使用网格布局显示统计
            stats_grid = tk.Frame(stats_frame, bg='white')
            stats_grid.pack(fill=tk.X, padx=10, pady=10)
            
            # 总答题数
            tk.Label(stats_grid, text="总答题数：", font=('Microsoft YaHei UI', 10),
                    bg='white', anchor='w').grid(row=0, column=0, sticky='w', padx=10, pady=5)
            tk.Label(stats_grid, text=str(stats['total_questions']), 
                    font=('Microsoft YaHei UI', 10, 'bold'), bg='white',
                    fg='#3498db').grid(row=0, column=1, sticky='w', padx=10, pady=5)
            
            # 正确答案
            tk.Label(stats_grid, text="正确答案：", font=('Microsoft YaHei UI', 10),
                    bg='white', anchor='w').grid(row=1, column=0, sticky='w', padx=10, pady=5)
            tk.Label(stats_grid, text=str(stats['correct_answers']), 
                    font=('Microsoft YaHei UI', 10, 'bold'), bg='white',
                    fg='#27ae60').grid(row=1, column=1, sticky='w', padx=10, pady=5)
            
            # 错误答案
            tk.Label(stats_grid, text="错误答案：", font=('Microsoft YaHei UI', 10),
                    bg='white', anchor='w').grid(row=2, column=0, sticky='w', padx=10, pady=5)
            tk.Label(stats_grid, text=str(stats['wrong_answers']), 
                    font=('Microsoft YaHei UI', 10, 'bold'), bg='white',
                    fg='#e74c3c').grid(row=2, column=1, sticky='w', padx=10, pady=5)
            
            # 准确率
            tk.Label(stats_grid, text="准确率：", font=('Microsoft YaHei UI', 10),
                    bg='white', anchor='w').grid(row=3, column=0, sticky='w', padx=10, pady=5)
            accuracy_color = '#27ae60' if stats['accuracy_rate'] >= 80 else '#e74c3c' if stats['accuracy_rate'] < 50 else '#f39c12'
            tk.Label(stats_grid, text=f"{stats['accuracy_rate']}%", 
                    font=('Microsoft YaHei UI', 12, 'bold'), bg='white',
                    fg=accuracy_color).grid(row=3, column=1, sticky='w', padx=10, pady=5)
            
            # 历史记录区域
            history_frame = ttk.LabelFrame(content_frame, text="📋 最近答题历史", padding=10)
            history_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            
            # 创建滚动文本框（使用深色主题）
            history_text = scrolledtext.ScrolledText(history_frame, height=12, wrap=tk.WORD,
                                                    font=('Consolas', 9),
                                                    bg='#1e1e1e', fg='#d4d4d4',
                                                    insertbackground='white',
                                                    selectbackground='#264f78')
            history_text.pack(fill=tk.BOTH, expand=True)
            
            if history:
                for record in history:
                    status = "✅" if record['is_correct'] else "❌"
                    status_color = "#4ec9b0" if record['is_correct'] else "#f48771"
                    
                    history_text.insert(tk.END, f"{status} ", "status")
                    history_text.insert(tk.END, f"[{record['created_at']}]\n", "time")
                    history_text.insert(tk.END, f"题目: {record['question']}\n", "question")
                    history_text.insert(tk.END, f"AI答案: {record['ai_answer']}\n", "answer")
                    if record['correct_answer']:
                        history_text.insert(tk.END, f"正确答案: {record['correct_answer']}\n", "correct")
                    history_text.insert(tk.END, "─" * 60 + "\n\n", "separator")
                
                # 配置标签颜色
                history_text.tag_config("status", foreground=status_color)
                history_text.tag_config("time", foreground="#858585")
                history_text.tag_config("question", foreground="#4ec9b0")
                history_text.tag_config("answer", foreground="#569cd6")
                history_text.tag_config("correct", foreground="#4ec9b0")
                history_text.tag_config("separator", foreground="#858585")
            else:
                history_text.insert(tk.END, "暂无答题历史", "empty")
                history_text.tag_config("empty", foreground="#858585")
            
            history_text.config(state=tk.DISABLED)
            
            # 按钮区域
            button_frame = tk.Frame(content_frame, bg='#f0f0f0')
            button_frame.pack(pady=15)
            
            def clear_history():
                if messagebox.askyesno("确认", "确定要清空所有答题历史吗？"):
                    self.database.clear_history()
                    self.update_statistics()
                    dialog.destroy()
                    messagebox.showinfo("✅ 成功", "答题历史已清空")
            
            ttk.Button(button_frame, text="🗑 清空历史", command=clear_history,
                      style='Danger.TButton', width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="❌ 关闭", command=dialog.destroy,
                      style='Info.TButton', width=12).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"获取统计信息失败: {e}")
            dialog.destroy()
    
    def initialize_modules(self):
        """初始化各个模块"""
        try:
            self.log_message("正在初始化模块...")
            
            # 延迟导入并初始化截图模块
            if self.screen_capture is None:
                from screen_capture import ScreenCapture
                self.screen_capture = ScreenCapture()
                self.log_message("截图模块初始化完成")
            
            # OCR模块已经在start_automation中初始化，这里不需要重复初始化
            if self.ocr_engine is None:
                # 如果还没有初始化，说明初始化失败
                self.log_message("警告：OCR模块未初始化")
            
            # 延迟导入并初始化题目解析模块
            if self.question_parser is None:
                from question_parser import QuestionParser
                self.question_parser = QuestionParser(self.config)
                self.log_message("题目解析模块初始化完成")
            
            # 延迟导入并初始化AI客户端
            if self.ai_client is None:
                from ai_client import AIClientFactory
                ai_provider = self.config.get('ai_provider', 'deepseek')
                ai_config = self.config.get(f'ai_providers.{ai_provider}', {})
                self.ai_client = AIClientFactory.create_client(ai_provider, ai_config)
                self.log_message(f"AI客户端初始化完成 ({ai_provider})")
            
            # 延迟导入并初始化点击控制模块
            if self.click_handler is None:
                from click_handler import ClickHandler
                self.click_handler = ClickHandler(self.config)
                self.log_message("点击控制模块初始化完成")
            
            return True
        except Exception as e:
            self.log_message(f"模块初始化失败: {e}")
            return False
    
    def manual_init_ocr(self):
        """手动初始化OCR"""
        if self.ocr_engine is not None or self.ocr_initializing:
            return
        
        self.log_message("手动触发OCR模块初始化...")
        threading.Thread(target=self._init_ocr_engine, daemon=True).start()

    def _init_ocr_engine(self):
        """后台初始化OCR引擎"""
        if self.ocr_initializing:
            return
            
        self.ocr_initializing = True
        self.root.after(0, lambda: self.ocr_status_label.config(text="初始化中...", fg='#f1c40f'))
        self.root.after(0, lambda: self.init_ocr_button.config(state=tk.DISABLED))
        
        try:
            from ocr_engine import OCREngine
            ocr_config = self.config.get('ocr', {})
            # PaddleOCR 3.4.0（PaddleX Pipeline）支持 common args：device/enable_mkldnn/cpu_threads 等
            self.ocr_engine = OCREngine(
                language=ocr_config.get('language', 'ch'),
                use_angle_cls=ocr_config.get('use_angle_cls', True),  # 保留参数用于兼容，但不会被使用
                use_gpu=ocr_config.get('use_gpu', False),  # 兼容字段：实际以 device 为准
                device=ocr_config.get('device', 'cpu'),
                ocr_version=ocr_config.get('ocr_version', None),
                fast_rec=ocr_config.get('fast_rec', None),
                enable_mkldnn=ocr_config.get('enable_mkldnn', None),
                mkldnn_cache_capacity=ocr_config.get('mkldnn_cache_capacity', 10),
                cpu_threads=ocr_config.get('cpu_threads', None),
                enable_hpi=ocr_config.get('enable_hpi', None),
                text_det_limit_side_len=ocr_config.get('text_det_limit_side_len', None),
                text_det_limit_type=ocr_config.get('text_det_limit_type', None),
                input_max_side=ocr_config.get('input_max_side', None),
                input_scale=ocr_config.get('input_scale', None),
                debug_timing=ocr_config.get('debug_timing', False),
            )
            self.root.after(0, lambda: self.log_message("OCR模块初始化完成"))
            self.root.after(0, lambda: self.ocr_status_label.config(text="已就绪", fg='#27ae60'))
            self.root.after(0, lambda: self.init_ocr_button.config(text="🔍 OCR已就绪"))
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log_message(f"OCR模块初始化失败: {err}"))
            self.root.after(0, lambda: self.ocr_status_label.config(text="初始化失败", fg='#e74c3c'))
            self.root.after(0, lambda: self.init_ocr_button.config(state=tk.NORMAL))
            self.ocr_engine = None
        finally:
            self.ocr_initializing = False
    
    def start_automation(self):
        """启动自动化流程"""
        # 获取当前游戏模式
        current_mode = self.game_mode_var.get() if hasattr(self, 'game_mode_var') else self.game_mode
        
        # 诗词答题模式需要检查API Key配置
        if current_mode == "poetry":
            is_valid, error = self.config.validate()
            if not is_valid:
                messagebox.showerror("错误", f"配置无效: {error}\n请先配置API Key")
                return
            
            # 如果OCR引擎未初始化，在后台线程中初始化
            if self.ocr_engine is None:
                if self.ocr_initializing:
                    self.log_message("OCR正在初始化中，请稍候...")
                    return
                self.log_message("开始运行，正在初始化OCR模块...")
                self.update_status("初始化中...", "", "")
                # 在后台线程中初始化OCR（不阻塞UI）
                init_thread = threading.Thread(target=self._init_ocr_engine, daemon=True)
                init_thread.start()
        
        if self.is_running:
            return
        
        self.is_running = True
        self.stop_flag = False
        
        # 更新按钮状态
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 在新线程中运行自动化流程
        thread = threading.Thread(target=self.automation_loop, daemon=True)
        thread.start()
        
        self.log_message("自动化流程已启动")
        self.update_status("运行中", "", "")
    
    def stop_automation(self):
        """停止自动化流程"""
        if not self.is_running:
            return
        
        self.stop_flag = True
        self.is_running = False
        
        # 更新按钮状态
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_message("正在停止自动化流程...")
        self.update_status("已停止", "", "")
    
    def automation_loop(self):
        """自动化循环（在工作线程中运行）"""
        # 根据游戏模式选择不同的处理逻辑
        current_mode = self.game_mode_var.get() if hasattr(self, 'game_mode_var') else self.game_mode
        
        if current_mode == "material":
            # 材料匹配游戏模式
            self.material_match_loop()
        else:
            # 诗词答题模式（原有逻辑）
            self.poetry_quiz_loop()
    
    def poetry_quiz_loop(self):
        """诗词答题自动化循环"""
        # 等待OCR引擎初始化完成（如果正在初始化）
        if self.ocr_engine is None:
            self.root.after(0, lambda: self.log_message("等待OCR模块初始化..."))
            timeout = 60  # 最多等待60秒
            elapsed = 0
            while self.ocr_engine is None and elapsed < timeout:
                time.sleep(0.5)
                elapsed += 0.5
            if self.ocr_engine is None:
                self.root.after(0, lambda: self.log_message("OCR模块初始化超时"))
                self.root.after(0, lambda: self.stop_automation())
                return
        
        # 初始化其他模块
        if not self.initialize_modules():
            self.root.after(0, lambda: self.stop_automation())
            return
        
        capture_interval = self.config.get('screen.capture_interval', 2.0)
        max_retry = self.config.get('automation.max_retry', 3)
        retry_delay = self.config.get('automation.retry_delay', 1.0)
        
        retry_count = 0
        
        while self.is_running and not self.stop_flag:
            try:
                # 用 perf_counter 做更精确的性能分段统计
                step_perf_start = time.perf_counter()
                perf = {
                    "capture": 0.0,
                    "save_screenshot": 0.0,
                    "ocr": 0.0,
                    "parse": 0.0,
                    "ai": 0.0,
                    "db": 0.0,
                    "click": 0.0,
                }
                
                # 截图
                t0 = time.time()
                if self.capture_region:
                    r = self.capture_region
                    self.root.after(0, lambda: self.log_message(f"开始区域截图 ({r['x']},{r['y']}) {r['width']}x{r['height']}..."))
                    image = self.screen_capture.capture_region(r['x'], r['y'], r['width'], r['height'])
                else:
                    self.root.after(0, lambda: self.log_message("开始全屏截图..."))
                    image = self.screen_capture.capture_full_screen()
                t1_cap = time.time()
                perf["capture"] = t1_cap - t0

                # 保存截图用于调试（跟随配置开关，避免不必要 IO）
                save_screenshots = self.config.get('screen.save_screenshots', False)
                if save_screenshots:
                    save_t0 = time.perf_counter()
                    base_dir = self.config.get('screen.screenshot_path', "./screenshots")
                    try:
                        os.makedirs(base_dir, exist_ok=True)
                    except Exception:
                        pass
                    debug_path = os.path.join(base_dir, "debug_screenshot.png")
                    image.save(debug_path)
                    perf["save_screenshot"] = time.perf_counter() - save_t0
                t1 = time.time()
                self.root.after(0, lambda dt=f"{t1-t0:.2f}": self.log_message(f"截图完成 (耗时 {dt}s)"))
                if save_screenshots:
                    self.root.after(
                        0,
                        lambda p=perf["save_screenshot"]: self.log_message(
                            f"保存截图完成 (耗时 {p:.2f}s)"
                        ),
                    )
                
                if self.stop_flag: break
                
                # OCR识别
                t0 = time.time()
                self.root.after(0, lambda: self.log_message("开始OCR识别..."))
                ocr_perf0 = time.perf_counter()

                # 优先尝试 fast_rec（方案C：固定ROI + rec-only）
                fast_question_data = None
                fast_used = False
                try:
                    ocr_cfg = self.config.get("ocr", {}) or {}
                    fast_cfg = ocr_cfg.get("fast_rec", {}) if isinstance(ocr_cfg, dict) else {}
                    if isinstance(fast_cfg, dict) and fast_cfg.get("enabled", False):
                        fast = getattr(self.ocr_engine, "recognize_fast_rec", None)
                        if callable(fast):
                            fast_res = fast(image)
                            if fast_res and isinstance(fast_res, dict) and fast_res.get("question") and fast_res.get("options"):
                                fast_question_data = {
                                    "question": fast_res["question"],
                                    "options": fast_res["options"],
                                }
                                # 仍保留 ocr_results 供日志打印
                                ocr_results = fast_res.get("ocr_results") or []
                                fast_used = True
                                # 打印 fast_rec 详情日志
                                last = fast_res.get("fast_rec_last") or getattr(self.ocr_engine, "fast_rec_last", {}) or {}
                                timing = last.get("timing") or fast_res.get("timing") or {}
                                model_name = last.get("model_name", "")
                                dev_used = last.get("device_used", "")
                                self.root.after(
                                    0,
                                    lambda m=model_name, d=dev_used, t=timing: self.log_message(
                                        f"fast_rec启用: model={m}, device={d}, total={t.get('total', 0):.3f}s, rec={t.get('rec_only', 0):.3f}s, crop={t.get('crop_to_np', 0):.3f}s"
                                    ),
                                )
                                texts = last.get("texts", {})
                                scores = last.get("scores", {})
                                # 固定顺序输出，便于肉眼对齐
                                for key in ["title", "question", "A", "B", "C", "D"]:
                                    if key in texts:
                                        self.root.after(
                                            0,
                                            lambda k=key, tx=texts.get(key, ""), sc=scores.get(key, 0.0): self.log_message(
                                                f"  fast_rec[{k}]: {tx} (score={sc:.3f})"
                                            ),
                                        )
                            else:
                                # fast_rec 返回 None 或低分回退
                                last = getattr(self.ocr_engine, "fast_rec_last", {}) or {}
                                reason = last.get("reason", "unknown")
                                self.root.after(0, lambda r=reason: self.log_message(f"fast_rec回退: {r}"))
                                # 回退时也打印ROI文本与分数，方便调参/调ROI
                                texts = last.get("texts", {}) if isinstance(last, dict) else {}
                                scores = last.get("scores", {}) if isinstance(last, dict) else {}
                                min_score = last.get("min_score", None) if isinstance(last, dict) else None
                                if min_score is not None:
                                    self.root.after(0, lambda ms=min_score: self.log_message(f"fast_rec阈值: min_score={ms}"))
                                for key in ["title", "question", "A", "B", "C", "D"]:
                                    if key in texts:
                                        self.root.after(
                                            0,
                                            lambda k=key, tx=texts.get(key, ""), sc=scores.get(key, 0.0): self.log_message(
                                                f"  fast_rec[{k}]: {tx} (score={sc:.3f})"
                                            ),
                                        )
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_message(f"fast_rec异常，已回退全流程OCR: {err}"))

                if not fast_used:
                    ocr_results = self.ocr_engine.recognize(image)
                else:
                    # fast_rec模式下，先检查fast_rec返回的文本
                    ocr_results = []
                
                perf["ocr"] = time.perf_counter() - ocr_perf0
                t1 = time.time()
                n = len(ocr_results)
                self.root.after(0, lambda n=n, dt=f"{t1-t0:.2f}": self.log_message(f"OCR识别完成，识别到 {n} 个文本区域 (耗时 {dt}s)"))
                
                if self.stop_flag: break
                
                # 检查是否识别到"答对题目数"（游戏结束标识）
                game_completed = False
                
                # 检查fast_rec返回的文本
                if fast_used:
                    last = getattr(self.ocr_engine, "fast_rec_last", {}) or {}
                    texts = last.get("texts", {}) if isinstance(last, dict) else {}
                    for key, text in texts.items():
                        if text and "答对题目数" in text:
                            game_completed = True
                            self.root.after(0, lambda: self.log_message("检测到游戏完成标识：答对题目数"))
                            break
                    
                    # fast_rec模式下，如果没检测到游戏结束标识，进行全流程OCR检测
                    if not game_completed:
                        self.root.after(0, lambda: self.log_message("fast_rec模式下，进行全流程OCR检测游戏结束标识..."))
                        full_ocr_results = self.ocr_engine.recognize(image)
                        for text, bbox in full_ocr_results:
                            if "答对题目数" in text:
                                game_completed = True
                                self.root.after(0, lambda: self.log_message("检测到游戏完成标识：答对题目数"))
                                break
                
                # 检查全流程OCR结果（非fast_rec模式）
                if not game_completed and not fast_used:
                    for text, bbox in ocr_results:
                        if "答对题目数" in text:
                            game_completed = True
                            self.root.after(0, lambda: self.log_message("检测到游戏完成标识：答对题目数"))
                            break
                
                if game_completed:
                    self.root.after(0, lambda: self.log_message("游戏已完成，停止自动化"))
                    self.root.after(0, lambda: self.stop_automation())
                    break
                
                # 打印OCR识别到的前10条文本，方便调试
                for i, (text, bbox) in enumerate(ocr_results[:10]):
                    self.root.after(0, lambda i=i, t=text: self.log_message(f"  OCR[{i}]: {t}"))
                if len(ocr_results) > 10:
                    self.root.after(0, lambda n=n: self.log_message(f"  ... 还有 {n-10} 条文本"))
                
                # 解析题目（fast_rec 成功时直接使用其结构化结果，跳过解析）
                t0 = time.time()
                self.root.after(0, lambda: self.log_message("开始解析题目..."))
                parse_perf0 = time.perf_counter()
                if fast_question_data:
                    question_data = fast_question_data
                else:
                    question_data = self.question_parser.parse(ocr_results)
                perf["parse"] = time.perf_counter() - parse_perf0
                t1 = time.time()
                if not question_data:
                    self.root.after(0, lambda dt=f"{t1-t0:.2f}": self.log_message(f"解析题目失败 (耗时 {dt}s)，等待重试..."))
                    # 可中断的等待
                    for _ in range(int(retry_delay / 0.2)):
                        if self.stop_flag: break
                        time.sleep(0.2)
                    retry_count += 1
                    if retry_count >= max_retry:
                        self.root.after(0, lambda: self.log_message("解析失败次数过多，停止运行"))
                        self.root.after(0, lambda: self.stop_automation())
                    continue
                
                if self.stop_flag: break
                
                retry_count = 0  # 重置重试计数
                
                question = question_data['question']
                options = question_data['options']
                self.root.after(0, lambda dt=f"{t1-t0:.2f}": self.log_message(f"题目解析完成 (耗时 {dt}s)"))
                
                self.root.after(0, lambda q=question: self.update_status("运行中", q, ""))
                self.root.after(0, lambda q=question: self.log_message(f"题目: {q}"))
                for k, v in options.items():
                    self.root.after(0, lambda k=k, t=v['text']: self.log_message(f"  选项 {k}: {t}"))
                
                if self.stop_flag: break
                
                # 调用AI获取答案
                t0 = time.time()
                opts_text = {k: v['text'] for k, v in options.items()}
                self.root.after(0, lambda: self.log_message("正在调用AI获取答案..."))
                ai_perf0 = time.perf_counter()
                answer = self.ai_client.get_answer(question, opts_text)
                perf["ai"] = time.perf_counter() - ai_perf0
                t1 = time.time()
                self.root.after(0, lambda a=answer, dt=f"{t1-t0:.2f}": self.log_message(f"AI返回答案: {a} (耗时 {dt}s)"))
                
                if self.stop_flag: break
                
                # 记录到数据库
                if self.database is not None:
                    try:
                        db_perf0 = time.perf_counter()
                        self.database.add_answer_record(
                            question=question,
                            options=opts_text,
                            ai_answer=answer
                        )
                        perf["db"] = time.perf_counter() - db_perf0
                        self.root.after(0, lambda: self.update_statistics())
                    except Exception as e:
                        try:
                            perf["db"] = time.perf_counter() - db_perf0
                        except Exception:
                            pass
                        self.root.after(0, lambda err=str(e): self.log_message(f"记录答题历史失败: {err}"))
                        if perf["db"] > 0:
                            self.root.after(
                                0,
                                lambda p=perf["db"]: self.log_message(f"记录答题历史耗时: {p:.2f}s"),
                            )
                
                # 点击选项
                if answer in options:
                    option_center = options[answer]['center']
                    # fast_rec 路径下 center 默认是 ROI 中心点，这里统一做向下偏移（保持与旧逻辑一致）
                    try:
                        if fast_question_data:
                            option_center = (option_center[0], option_center[1] + self.config.get("click.offset_y", 20))
                    except Exception:
                        pass
                    # 区域截图模式下，OCR坐标是相对于截取区域的，需要加上区域偏移
                    if self.capture_region:
                        offset_x = self.capture_region['x']
                        offset_y = self.capture_region['y']
                        option_center = (option_center[0] + offset_x, option_center[1] + offset_y)
                    self.root.after(0, lambda a=answer, c=option_center: self.log_message(f"准备点击选项 {a}，屏幕坐标: {c}"))
                    self.root.after(0, lambda a=answer: self.update_status("运行中", question, a))
                    
                    click_perf0 = time.perf_counter()
                    self.click_handler.click_option(option_center)
                    perf["click"] = time.perf_counter() - click_perf0
                    self.root.after(0, lambda a=answer: self.log_message(f"已点击选项 {a}"))
                else:
                    self.root.after(0, lambda a=answer: self.log_message(f"警告：答案 {a} 不在选项中"))
                
                total_time = time.perf_counter() - step_perf_start
                self.root.after(0, lambda dt=f"{total_time:.2f}": self.log_message(f"本轮总耗时: {dt}s"))

                # 输出更细的分段耗时汇总，定位到底哪里慢
                known = (
                    perf["capture"]
                    + perf["save_screenshot"]
                    + perf["ocr"]
                    + perf["parse"]
                    + perf["ai"]
                    + perf["db"]
                    + perf["click"]
                )
                other = max(0.0, total_time - known)
                self.root.after(
                    0,
                    lambda p=perf, other=other, total=total_time: self.log_message(
                        "耗时拆分: "
                        f"截图 {p['capture']:.2f}s, "
                        f"保存截图 {p['save_screenshot']:.2f}s, "
                        f"OCR {p['ocr']:.2f}s, "
                        f"解析 {p['parse']:.2f}s, "
                        f"AI {p['ai']:.2f}s, "
                        f"DB {p['db']:.2f}s, "
                        f"点击 {p['click']:.2f}s, "
                        f"其它 {other:.2f}s, "
                        f"总计 {total:.2f}s"
                    ),
                )
                
                # 可中断的等待下一题
                self.root.after(0, lambda: self.log_message(f"等待 {capture_interval} 秒后继续..."))
                for _ in range(int(capture_interval / 0.2)):
                    if self.stop_flag: break
                    time.sleep(0.2)
                
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_message(f"发生错误: {err}"))
                for _ in range(int(retry_delay / 0.2)):
                    if self.stop_flag: break
                    time.sleep(0.2)
                retry_count += 1
                if retry_count >= max_retry:
                    self.root.after(0, lambda: self.log_message("错误次数过多，停止运行"))
                    self.root.after(0, lambda: self.stop_automation())
                    break
        
        self.root.after(0, lambda: self.log_message("自动化流程已停止"))
    
    def material_match_loop(self):
        """材料匹配游戏自动化循环"""
        # 初始化材料匹配器
        if self.material_matcher is None:
            from material_matcher import MaterialMatcher
            material_config = self.config.get('material_match', {})
            self.material_matcher = MaterialMatcher(self.config)
            self.material_matcher.set_config(material_config)
            self.root.after(0, lambda: self.log_message("材料匹配器初始化完成"))
        
        # 初始化截图和点击模块
        if self.screen_capture is None:
            from screen_capture import ScreenCapture
            self.screen_capture = ScreenCapture()
        
        if self.click_handler is None:
            from click_handler import ClickHandler
            self.click_handler = ClickHandler(self.config)
        
        capture_interval = self.config.get('screen.capture_interval', 1.0)
        click_delay = self.config.get('material_match.click_delay', 0.3)
        
        self.root.after(0, lambda: self.log_message("材料匹配游戏自动化已启动"))
        
        while self.is_running and not self.stop_flag:
            try:
                # 截图
                if self.capture_region:
                    r = self.capture_region
                    image = self.screen_capture.capture_region(r['x'], r['y'], r['width'], r['height'])
                else:
                    image = self.screen_capture.capture_full_screen()
                
                if self.stop_flag:
                    break
                
                # 获取游戏状态
                game_state = self.material_matcher.get_game_state(image)
                
                # 检查游戏是否结束
                if game_state.get("is_game_over", False):
                    self.root.after(0, lambda: self.log_message("游戏已结束"))
                    break
                
                # 识别材料
                materials = game_state.get("materials")
                if materials is None or len(materials) == 0:
                    self.root.after(0, lambda: self.log_message("未识别到材料，等待..."))
                    time.sleep(capture_interval)
                    continue
                
                # 找到最佳匹配对
                best_pair = self.material_matcher.find_best_match(materials)
                
                if best_pair is None:
                    self.root.after(0, lambda: self.log_message("未找到匹配的材料对"))
                    time.sleep(capture_interval)
                    continue
                
                # 获取点击位置
                pos1, pos2 = self.material_matcher.get_click_positions(best_pair, image)
                
                # 点击第一个材料
                self.root.after(0, lambda p=pos1: self.log_message(f"点击材料1: {p}"))
                self.click_handler.click(pos1[0], pos1[1])
                time.sleep(click_delay)
                
                if self.stop_flag:
                    break
                
                # 点击第二个材料
                self.root.after(0, lambda p=pos2: self.log_message(f"点击材料2: {p}"))
                self.click_handler.click(pos2[0], pos2[1])
                
                # 等待匹配完成
                time.sleep(click_delay * 2)
                
                # 等待下一轮
                for _ in range(int(capture_interval / 0.2)):
                    if self.stop_flag:
                        break
                    time.sleep(0.2)
                
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_message(f"材料匹配发生错误: {err}"))
                time.sleep(1.0)
        
        self.root.after(0, lambda: self.log_message("材料匹配自动化流程已停止"))
    
    def on_closing(self):
        """窗口关闭事件处理"""
        if self.is_running:
            if messagebox.askokcancel("退出", "程序正在运行，确定要退出吗？"):
                self.stop_automation()
                time.sleep(0.5)  # 等待线程结束
                self.root.destroy()
        else:
            self.root.destroy()
    
    def run(self):
        """运行主循环"""
        self.root.mainloop()


def main():
    """主函数"""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
