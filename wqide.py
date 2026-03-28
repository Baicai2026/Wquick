#!/usr/bin/env python3
"""
Wquick IDE — 轻量图形化编辑器
类似 Python IDLE，支持语法高亮、运行、输出面板
依赖：Python 3 自带的 tkinter，无需额外安装
"""

# ── Windows 高 DPI 修复（必须在 tkinter 导入前调用）──────────────
import sys, os
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import subprocess
import threading
import re
import shutil
import tempfile
from typing import Optional

# ─────────────────────────────────────────────
#  自动发现工具路径
# ─────────────────────────────────────────────
def _find_tool(filename: str) -> Optional[str]:
    """从 wqide.py 所在目录向上最多 3 级查找指定文件"""
    start = os.path.dirname(os.path.abspath(__file__))
    search_roots = [start]
    cur = start
    for _ in range(3):
        cur = os.path.dirname(cur)
        search_roots.append(cur)
        search_roots.append(os.path.join(cur, 'compiler'))
    for root in search_roots:
        candidate = os.path.join(root, filename)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _find_gpp() -> Optional[str]:
    """
    自动发现 g++，搜索顺序：
    1. 环境变量 WQ_GCC
    2. 与 wqide.py 同目录下的 TDM-GCC-64/bin/g++.exe（内置 gcc）
    3. 系统 PATH（shutil.which）
    4. 常见 Windows 安装路径（Dev-Cpp / MinGW / msys2 等）
    """
    # 1. 已有环境变量
    from_env = os.environ.get('WQ_GCC', '')
    if from_env and os.path.isfile(from_env):
        return from_env

    # 2. 内置 gcc（与 wqide.py 同目录下的 TDM-GCC-64）
    _self_dir = os.path.dirname(os.path.abspath(__file__))
    _builtin = os.path.join(_self_dir, 'TDM-GCC-64', 'bin', 'g++.exe')
    if os.path.isfile(_builtin):
        return _builtin

    # 3. PATH
    in_path = shutil.which('g++')
    if in_path:
        return in_path

    # 4. 常见安装位置（支持多盘符）
    drives = ['C:', 'D:', 'E:', 'F:']
    suffixes = [
        r'Dev-Cpp\TDM-GCC-64\bin\g++.exe',
        r'Dev-Cpp\MinGW64\bin\g++.exe',
        r'MinGW\bin\g++.exe',
        r'MinGW64\bin\g++.exe',
        r'mingw-w64\bin\g++.exe',
        r'msys64\mingw64\bin\g++.exe',
        r'msys64\ucrt64\bin\g++.exe',
        r'msys2\mingw64\bin\g++.exe',
    ]
    prog_dirs = [
        r'Program Files',
        r'Program Files (x86)',
        r'',   # 盘根目录
    ]
    for drive in drives:
        for prog in prog_dirs:
            for suf in suffixes:
                p = os.path.join(drive + '\\', prog, suf) if prog else os.path.join(drive + '\\', suf)
                if os.path.isfile(p):
                    return p
    return None


# 启动时一次性解析
WQI_PATH: Optional[str] = _find_tool('wqi.py')
WQC_PATH: Optional[str] = _find_tool('wqc.exe')
GPP_PATH: Optional[str] = _find_gpp()



# ─────────────────────────────────────────────
#  语法高亮配置
# ─────────────────────────────────────────────
KEYWORDS = [
    'let', 'if', 'elif', 'else', 'for', 'while', 'return', 'import',
    'break', 'continue', 'int', 'float', 'char', 'string', 'bool',
    'const', 'this', 'super', 'extends', 'true', 'false','input', 'output',
    'def', 'class', 'namespace', 'template',
]

COLOR = {
    'bg':          '#1e1e2e',
    'fg':          '#cdd6f4',
    'lineno_bg':   '#181825',
    'lineno_fg':   '#585b70',
    'cursor':      '#f38ba8',
    'select_bg':   '#313244',
    'keyword':     '#cba6f7',
    'label':       '#89b4fa',
    'string':      '#a6e3a1',
    'number':      '#fab387',
    'comment':     '#6c7086',
    'operator':    '#89dceb',
    'type':        '#f9e2af',
    'console_bg':  '#11111b',
    'console_fg':  '#cdd6f4',
    'error_fg':    '#f38ba8',
    'ok_fg':       '#a6e3a1',
    'prompt_fg':   '#89b4fa',
    'menubar_bg':  '#181825',
    'menubar_fg':  '#cdd6f4',
    'status_bg':   '#181825',
    'status_fg':   '#585b70',
}

TYPES = ['int', 'float', 'char', 'string', 'bool']

# ─────────────────────────────────────────────
#  行号 Canvas
# ─────────────────────────────────────────────
class LineNumbers(tk.Canvas):
    def __init__(self, master, text_widget, **kw):
        super().__init__(master, **kw)
        self.text_widget = text_widget
        self._font = None

    def redraw(self, *_):
        self.delete('all')
        tw = self.text_widget
        i = tw.index('@0,0')
        while True:
            dline = tw.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = int(str(i).split('.')[0])
            self.create_text(
                self.winfo_width() - 4, y,
                anchor='ne', text=str(linenum),
                fill=COLOR['lineno_fg'], font=self._font
            )
            i = tw.index(f'{i}+1line')
            if i == tw.index(f'{i}+1line'):
                break

# ─────────────────────────────────────────────
#  主 IDE 窗口
# ─────────────────────────────────────────────
class WquickIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Wquick IDE')
        self.geometry('1000x680')
        self.configure(bg=COLOR['bg'])
        self.current_file: Optional[str] = None
        self.modified = False
        self._running = False   # 防止重复运行

        self._setup_font()
        self._build_menu()
        self._build_editor()
        self._build_console()
        self._build_statusbar()
        self._bind_events()
        self._new_file()

        # 初始高亮 + 启动后显示工具路径状态
        self.after(100, self._highlight_all)
        self.after(200, self._show_tool_status)

    # ── 字体 ────────────────────────────────
    def _setup_font(self):
        # 优先使用等宽字体
        for name in ('Consolas', 'Cascadia Code', 'Courier New', 'Monospace'):
            try:
                f = font.Font(family=name, size=12)
                if f.actual('family').lower().replace(' ', '') != 'courier':
                    self.code_font = f
                    break
            except Exception:
                pass
        else:
            self.code_font = font.Font(family='Courier New', size=12)
        self.code_font_bold = font.Font(
            family=self.code_font.actual('family'), size=12, weight='bold')

    # ── 菜单 ────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self, bg=COLOR['menubar_bg'], fg=COLOR['menubar_fg'],
                     activebackground=COLOR['select_bg'],
                     activeforeground=COLOR['fg'],
                     relief='flat', bd=0)
        self.config(menu=mb)

        # 文件
        fm = tk.Menu(mb, tearoff=0, bg=COLOR['menubar_bg'], fg=COLOR['menubar_fg'],
                     activebackground=COLOR['select_bg'], activeforeground=COLOR['fg'])
        mb.add_cascade(label='文件', menu=fm)
        fm.add_command(label='新建        Ctrl+N', command=self._new_file)
        fm.add_command(label='打开...     Ctrl+O', command=self._open_file)
        fm.add_separator()
        fm.add_command(label='保存        Ctrl+S', command=self._save_file)
        fm.add_command(label='另存为... Ctrl+Shift+S', command=self._save_as)
        fm.add_separator()
        fm.add_command(label='退出', command=self._quit)

        # 运行
        rm = tk.Menu(mb, tearoff=0, bg=COLOR['menubar_bg'], fg=COLOR['menubar_fg'],
                     activebackground=COLOR['select_bg'], activeforeground=COLOR['fg'])
        mb.add_cascade(label='运行', menu=rm)
        rm.add_command(label='运行（解释器）  F5', command=self._run_interp)
        rm.add_command(label='运行（编译器）  F6', command=self._run_compiler)
        rm.add_separator()
        rm.add_command(label='配置路径...', command=self._path_settings)
        rm.add_separator()
        rm.add_command(label='清空输出', command=self._clear_console)

        # 编辑
        em = tk.Menu(mb, tearoff=0, bg=COLOR['menubar_bg'], fg=COLOR['menubar_fg'],
                     activebackground=COLOR['select_bg'], activeforeground=COLOR['fg'])
        mb.add_cascade(label='编辑', menu=em)
        em.add_command(label='撤销  Ctrl+Z', command=lambda: self.editor.event_generate('<<Undo>>'))
        em.add_command(label='重做  Ctrl+Y', command=lambda: self.editor.event_generate('<<Redo>>'))
        em.add_separator()
        em.add_command(label='查找  Ctrl+F', command=self._find_dialog)

    # ── 编辑区 ──────────────────────────────
    def _build_editor(self):
        # 顶部工具栏
        toolbar = tk.Frame(self, bg=COLOR['menubar_bg'], pady=2)
        toolbar.pack(side='top', fill='x')

        def tb_btn(text, cmd, tooltip=''):
            b = tk.Button(toolbar, text=text, command=cmd,
                          bg=COLOR['menubar_bg'], fg=COLOR['fg'],
                          activebackground=COLOR['select_bg'],
                          activeforeground=COLOR['fg'],
                          relief='flat', padx=10, pady=2,
                          font=('Segoe UI', 9), cursor='hand2')
            b.pack(side='left', padx=2)
            return b

        tb_btn('▶ 运行', self._run_interp)
        tb_btn('⚙ 编译运行', self._run_compiler)
        tb_btn('✕ 清空输出', self._clear_console)

        sep = tk.Frame(self, bg='#313244', height=1)
        sep.pack(fill='x')

        # 编辑器主体
        editor_frame = tk.Frame(self, bg=COLOR['bg'])
        editor_frame.pack(side='top', fill='both', expand=True)

        # 行号
        self.line_numbers = LineNumbers(
            editor_frame, None,
            width=45, bg=COLOR['lineno_bg'], highlightthickness=0)
        self.line_numbers.pack(side='left', fill='y')

        # 滚动条
        vscroll = tk.Scrollbar(editor_frame, orient='vertical',
                               bg=COLOR['bg'], troughcolor=COLOR['lineno_bg'],
                               width=10)
        vscroll.pack(side='right', fill='y')

        # 编辑器文本框
        self.editor = tk.Text(
            editor_frame,
            bg=COLOR['bg'], fg=COLOR['fg'],
            insertbackground=COLOR['cursor'],
            selectbackground=COLOR['select_bg'],
            selectforeground=COLOR['fg'],
            font=self.code_font,
            undo=True, maxundo=-1,
            wrap='none',
            relief='flat', bd=0,
            padx=8, pady=4,
            yscrollcommand=self._on_editor_scroll,
            tabs=('1c',),
        )
        self.editor.pack(side='left', fill='both', expand=True)
        vscroll.config(command=self.editor.yview)
        self.line_numbers.text_widget = self.editor

        # 注册高亮 tag
        self._setup_tags()

    def _setup_tags(self):
        e = self.editor
        e.tag_configure('keyword',  foreground=COLOR['keyword'],  font=self.code_font_bold)
        e.tag_configure('label',    foreground=COLOR['label'],    font=self.code_font_bold)
        e.tag_configure('string',   foreground=COLOR['string'])
        e.tag_configure('number',   foreground=COLOR['number'])
        e.tag_configure('comment',  foreground=COLOR['comment'],  font=font.Font(family=self.code_font.actual('family'), size=12, slant='italic'))
        e.tag_configure('operator', foreground=COLOR['operator'])
        e.tag_configure('type',     foreground=COLOR['type'],     font=self.code_font_bold)

    # ── 控制台 ──────────────────────────────
    def _build_console(self):
        # 分割线
        sep = tk.Frame(self, bg='#313244', height=2, cursor='sb_v_double_arrow')
        sep.pack(fill='x')
        sep.bind('<B1-Motion>', self._resize_console)
        self._sep = sep

        console_frame = tk.Frame(self, bg=COLOR['console_bg'], height=180)
        console_frame.pack(side='bottom', fill='x')
        console_frame.pack_propagate(False)
        self._console_frame = console_frame

        # 标题栏
        header = tk.Frame(console_frame, bg=COLOR['lineno_bg'], pady=3)
        header.pack(fill='x')
        tk.Label(header, text=' ▼ 输出', bg=COLOR['lineno_bg'],
                 fg=COLOR['status_fg'], font=('Segoe UI', 9)).pack(side='left')

        # 控制台文本
        cvscroll = tk.Scrollbar(console_frame, orient='vertical',
                                bg=COLOR['console_bg'], troughcolor=COLOR['lineno_bg'],
                                width=10)
        cvscroll.pack(side='right', fill='y')

        self.console = tk.Text(
            console_frame,
            bg=COLOR['console_bg'], fg=COLOR['console_fg'],
            font=self.code_font,
            state='disabled',
            relief='flat', bd=0, padx=8, pady=4,
            wrap='word',
            yscrollcommand=cvscroll.set,
        )
        self.console.pack(fill='both', expand=True)
        cvscroll.config(command=self.console.yview)

        # console 颜色 tag
        self.console.tag_configure('ok',     foreground=COLOR['ok_fg'])
        self.console.tag_configure('error',  foreground=COLOR['error_fg'])
        self.console.tag_configure('prompt', foreground=COLOR['prompt_fg'])
        self.console.tag_configure('normal', foreground=COLOR['console_fg'])

    def _resize_console(self, event):
        delta = self._sep.winfo_rooty() - event.y_root
        new_h = self._console_frame.winfo_height() + delta
        new_h = max(60, min(new_h, self.winfo_height() - 200))
        self._console_frame.config(height=new_h)

    # ── 状态栏 ──────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=COLOR['status_bg'], pady=2)
        bar.pack(side='bottom', fill='x')
        self.status_left  = tk.Label(bar, text='就绪', bg=COLOR['status_bg'],
                                     fg=COLOR['status_fg'], font=('Segoe UI', 9))
        self.status_left.pack(side='left', padx=8)
        self.status_right = tk.Label(bar, text='行 1  列 1', bg=COLOR['status_bg'],
                                     fg=COLOR['status_fg'], font=('Segoe UI', 9))
        self.status_right.pack(side='right', padx=8)

    # ── 事件绑定 ────────────────────────────
    def _bind_events(self):
        self.bind('<Control-n>', lambda e: self._new_file())
        self.bind('<Control-o>', lambda e: self._open_file())
        self.bind('<Control-s>', lambda e: self._save_file())
        self.bind('<Control-S>', lambda e: self._save_as())
        self.bind('<F5>',        lambda e: self._run_interp())
        self.bind('<F6>',        lambda e: self._run_compiler())
        self.bind('<Control-f>', lambda e: self._find_dialog())
        self.editor.bind('<KeyRelease>',   self._on_key)
        self.editor.bind('<ButtonRelease>',self._update_cursor_pos)
        self.editor.bind('<<Modified>>',   self._on_modified)
        self.protocol('WM_DELETE_WINDOW',  self._quit)

    def _on_editor_scroll(self, *args):
        self.editor.yview(*args) if len(args) > 1 else None
        # 同步行号
        self.line_numbers.redraw()
        # 也要处理 Text 自己的 yscrollcommand 参数
        # tkinter 会把 args 传给 scrollbar，这里不需要额外处理
        # 直接让 editor 的 yscrollcommand 指向滚动条
        pass

    def _on_editor_scroll(self, first, last):
        # 更新行号
        self.line_numbers.redraw()

    def _on_key(self, event=None):
        self._highlight_visible()
        self._update_cursor_pos()
        self.line_numbers.redraw()

    def _on_modified(self, event=None):
        if self.editor.edit_modified():
            self.modified = True
            self._update_title()
            self.editor.edit_modified(False)

    def _update_cursor_pos(self, event=None):
        idx = self.editor.index('insert')
        row, col = idx.split('.')
        self.status_right.config(text=f'行 {row}  列 {int(col)+1}')

    def _update_title(self):
        name = os.path.basename(self.current_file) if self.current_file else '新文件'
        mark = ' •' if self.modified else ''
        self.title(f'{name}{mark} — Wquick IDE')

    # ── 文件操作 ────────────────────────────
    def _new_file(self):
        if not self._check_save():
            return
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', '// 新建 Wquick 文件\nimport:0;\n\n`start\n    output:"Hello World!\\n";\n`/\n')
        self.current_file = None
        self.modified = False
        self._update_title()
        self._highlight_all()
        self.line_numbers.redraw()

    def _open_file(self):
        if not self._check_save():
            return
        path = filedialog.askopenfilename(
            filetypes=[('Wquick 源文件', '*.wq'), ('所有文件', '*.*')],
            title='打开文件')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', content)
            self.current_file = path
            self.modified = False
            self._update_title()
            self._highlight_all()
            self.line_numbers.redraw()
        except Exception as ex:
            messagebox.showerror('打开失败', str(ex))

    def _save_file(self):
        if self.current_file:
            self._write_file(self.current_file)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.wq',
            filetypes=[('Wquick 源文件', '*.wq'), ('所有文件', '*.*')],
            title='另存为')
        if path:
            self._write_file(path)
            self.current_file = path
            self._update_title()

    def _write_file(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.editor.get('1.0', 'end-1c'))
            self.modified = False
            self._update_title()
            self.status_left.config(text=f'已保存 {os.path.basename(path)}')
        except Exception as ex:
            messagebox.showerror('保存失败', str(ex))

    def _check_save(self) -> bool:
        """若有未保存修改，询问是否保存；返回 False 表示取消操作"""
        if not self.modified:
            return True
        r = messagebox.askyesnocancel('保存修改', '文件已修改，是否保存？')
        if r is None:
            return False
        if r:
            self._save_file()
        return True

    def _quit(self):
        if self._check_save():
            self.destroy()

    # ── 运行 ────────────────────────────────
    def _get_script_dir(self):
        return os.path.dirname(os.path.abspath(__file__))

    def _show_tool_status(self):
        """启动后在控制台打印工具发现结果"""
        lines = ['── Wquick IDE 已启动 ──\n']
        if WQI_PATH:
            lines.append(f'[✓] 解释器  {WQI_PATH}\n')
        else:
            lines.append('[✗] 未找到 wqi.py（F5 不可用）\n')
        if WQC_PATH:
            lines.append(f'[✓] 编译器  {WQC_PATH}\n')
        else:
            lines.append('[✗] 未找到 wqc.exe（F6 不可用）\n')
        if GPP_PATH:
            lines.append(f'[✓] g++     {GPP_PATH}\n')
        else:
            lines.append('[✗] 未找到 g++（编译器运行不可用，可在"运行→配置路径"手动指定）\n')
        lines.append('\n')
        for line in lines:
            tag = 'ok' if line.startswith('[✓]') else ('error' if line.startswith('[✗]') else 'prompt')
            self._console_write(line, tag)

    def _run_interp(self):
        """用 wqi.py 解释执行"""
        if self._running:
            return
        if not WQI_PATH:
            self._console_write('[错误] 找不到 wqi.py，无法使用解释器运行\n', 'error')
            return
        src = self._get_source()
        if src is None:
            return
        self._console_write(f'▶ 运行（解释器）: {os.path.basename(src)}\n', 'prompt')
        self._run_cmd([sys.executable, WQI_PATH, src], src)


    def _run_compiler(self):
        """用 wqc.exe 编译，然后 IDE 自己运行生成的 exe"""
        if self._running:
            return
        if not WQC_PATH:
            self._console_write('[错误] 找不到 wqc.exe，无法使用编译器运行\n', 'error')
            return
        gpp = self._resolve_gpp()
        if not gpp:
            self._console_write(
                '[错误] 找不到 g++，编译无法进行。\n'
                '       请在 运行 → 配置路径 中手动指定 g++.exe 路径。\n', 'error')
            return
        src = self._get_source()
        if src is None:
            return

        # 把输出 exe 放到临时目录，避免源文件目录旧 exe 文件锁
        tmp_dir = tempfile.mkdtemp(prefix='wqide_')
        out_exe = os.path.join(tmp_dir, os.path.basename(src).replace('.wq', '') + '.exe')

        env = dict(os.environ)
        env['WQ_GCC'] = gpp
        env['WQ_OUT'] = out_exe
        # 告诉 wqc 只编译，不要自己运行（通过 WQ_NORUN 标志）
        env['WQ_NORUN'] = '1'

        self._console_write(f'▶ 编译: {os.path.basename(src)}\n', 'prompt')
        self._console_write(f'   g++ = {gpp}\n', 'prompt')

        self._running = True
        self.status_left.config(text='编译中…')

        def compile_then_run():
            try:
                proc = subprocess.Popen(
                    [WQC_PATH, src],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=os.path.dirname(src) or '.',
                    env=env,
                    text=True, encoding='utf-8', errors='replace')
                stdout, stderr = proc.communicate(timeout=30)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr, rc = '', '编译超时（>30s）', -1
            except Exception as ex:
                stdout, stderr, rc = '', str(ex), -1

            # 写编译 log
            self._ide_log([WQC_PATH, src], src, stdout, stderr, rc)

            if rc != 0 or not os.path.isfile(out_exe):
                # 编译失败
                self.after(0, lambda: self._console_write(
                    stdout + ('\n' if stdout else ''), 'normal'))
                self.after(0, lambda: self._console_write(
                    stderr + ('\n' if stderr else ''), 'error'))
                self.after(0, lambda: self._console_write(
                    f'[编译失败，返回码 {rc}]\n', 'error'))
                self.after(0, lambda: self.status_left.config(text=f'编译失败'))
                self.after(0, lambda: setattr(self, '_running', False))
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass
                return

            # 编译成功，显示编译输出
            if stdout.strip():
                self.after(0, lambda: self._console_write(stdout, 'normal'))
            if stderr.strip():
                self.after(0, lambda: self._console_write(stderr, 'error'))
            self.after(0, lambda: self._console_write(
                f'[编译成功] → {os.path.basename(out_exe)}\n▶ 运行中…\n', 'ok'))
            self.after(0, lambda: self.status_left.config(text='运行中…'))

            # 运行 exe
            try:
                proc2 = subprocess.Popen(
                    [out_exe],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=tmp_dir,
                    text=True, encoding='utf-8', errors='replace')
                stdout2, stderr2 = proc2.communicate(timeout=60)
                rc2 = proc2.returncode
            except subprocess.TimeoutExpired:
                proc2.kill()
                stdout2, stderr2, rc2 = '', '', -1
                self.after(0, lambda: self._console_write(
                    '[超时] 程序运行超过 60 秒\n', 'error'))
            except Exception as ex:
                stdout2, stderr2, rc2 = '', str(ex), -1

            self._ide_log([out_exe], src, stdout2, stderr2, rc2)

            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

            self.after(0, lambda: self._show_result(stdout2, stderr2, rc2))
            self.after(0, lambda: setattr(self, '_running', False))

        t = threading.Thread(target=compile_then_run, daemon=True)
        t.start()

    def _resolve_gpp(self) -> Optional[str]:
        """返回当前有效的 g++ 路径（优先用户手动配置，其次自动发现）"""
        manual = getattr(self, '_manual_gpp', None)
        if manual and os.path.isfile(manual):
            return manual
        return GPP_PATH



    def _get_source(self) -> Optional[str]:
        """确保当前内容已保存到文件，返回文件路径"""
        if self.modified or self.current_file is None:
            if self.current_file is None:
                # 未命名，先让用户另存为
                path = filedialog.asksaveasfilename(
                    defaultextension='.wq',
                    filetypes=[('Wquick 源文件', '*.wq'), ('所有文件', '*.*')],
                    title='保存后运行')
                if not path:
                    return None
                self.current_file = path
                self._update_title()
            self._write_file(self.current_file)
        return self.current_file

    def _run_cmd(self, cmd, src_path, env=None, cleanup_dir=None):
        """在后台线程里跑命令，输出刷到控制台，完成后清理临时目录"""
        self._running = True
        self.status_left.config(text='运行中…')

        def worker():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=os.path.dirname(src_path) or '.',
                    env=env,
                    text=True, encoding='utf-8', errors='replace')
                stdout, stderr = proc.communicate(timeout=60)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr, rc = '', '', -1
                self.after(0, lambda: self._console_write('[超时] 程序运行超过 60 秒\n', 'error'))
            except Exception as ex:
                stdout, stderr, rc = '', str(ex), -1
            finally:
                if cleanup_dir:
                    try:
                        shutil.rmtree(cleanup_dir, ignore_errors=True)
                    except Exception:
                        pass

            # 写 IDE log
            self._ide_log(cmd, src_path, stdout, stderr, rc)
            self.after(0, lambda: self._show_result(stdout, stderr, rc))
            self.after(0, lambda: setattr(self, '_running', False))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _show_result(self, stdout, stderr, rc):
        if stdout:
            self._console_write(stdout, 'normal')
        if stderr:
            self._console_write(stderr, 'error')
        tag = 'ok' if rc == 0 else 'error'
        self._console_write(f'\n[进程退出，返回码 {rc}]\n', tag)
        self.status_left.config(text=f'运行完成，返回码 {rc}')

    def _console_write(self, text, tag='normal'):
        self.console.config(state='normal')
        self.console.insert('end', text, tag)
        self.console.see('end')
        self.console.config(state='disabled')

    def _clear_console(self):
        self.console.config(state='normal')
        self.console.delete('1.0', 'end')
        self.console.config(state='disabled')

    def _ide_log(self, cmd, src_path, stdout, stderr, rc):
        """把运行结果追加写到 wqide.log（与 wqc.exe 同目录）"""
        try:
            import datetime
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wqide.log')
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f'\n[{ts}] ── IDE RUN ──\n')
                f.write(f'  cmd : {" ".join(str(c) for c in cmd)}\n')
                f.write(f'  src : {src_path}\n')
                f.write(f'  rc  : {rc}\n')
                if stdout.strip():
                    f.write(f'  stdout:\n')
                    for line in stdout.splitlines():
                        f.write(f'    {line}\n')
                if stderr.strip():
                    f.write(f'  stderr:\n')
                    for line in stderr.splitlines():
                        f.write(f'    {line}\n')
        except Exception:
            pass  # log 写失败不影响主流程



    # ── 路径配置对话框 ───────────────────────
    def _path_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title('配置工具路径')
        dlg.geometry('560x220')
        dlg.resizable(False, False)
        dlg.configure(bg=COLOR['bg'])
        dlg.transient(self)
        dlg.grab_set()

        def row(label_text, default_val, r):
            tk.Label(dlg, text=label_text, bg=COLOR['bg'], fg=COLOR['fg'],
                     font=('Segoe UI', 9), anchor='w', width=10
                     ).grid(row=r, column=0, padx=(12,4), pady=8, sticky='w')
            var = tk.StringVar(value=default_val or '')
            entry = tk.Entry(dlg, textvariable=var,
                             bg=COLOR['select_bg'], fg=COLOR['fg'],
                             insertbackground=COLOR['cursor'],
                             font=self.code_font, relief='flat', bd=4)
            entry.grid(row=r, column=1, padx=4, pady=8, sticky='ew')
            def browse(v=var):
                p = filedialog.askopenfilename(
                    filetypes=[('可执行文件', '*.exe *.py'), ('所有文件', '*.*')])
                if p:
                    v.set(p)
            tk.Button(dlg, text='浏览', command=browse,
                      bg=COLOR['menubar_bg'], fg=COLOR['fg'],
                      relief='flat', padx=8, font=('Segoe UI', 9)
                      ).grid(row=r, column=2, padx=(4,12), pady=8)
            return var

        dlg.columnconfigure(1, weight=1)

        var_wqi = row('wqi.py', WQI_PATH,  0)
        var_wqc = row('wqc.exe', WQC_PATH, 1)
        var_gpp = row('g++.exe', GPP_PATH if not getattr(self,'_manual_gpp',None) else self._manual_gpp, 2)

        def apply():
            global WQI_PATH, WQC_PATH, GPP_PATH
            p = var_wqi.get().strip()
            if p and os.path.isfile(p): WQI_PATH = p
            p = var_wqc.get().strip()
            if p and os.path.isfile(p): WQC_PATH = p
            p = var_gpp.get().strip()
            if p and os.path.isfile(p):
                GPP_PATH = p
                self._manual_gpp = p
            self._clear_console()
            self._show_tool_status()
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=COLOR['bg'])
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(0,12))
        tk.Button(btn_frame, text='应用', command=apply,
                  bg=COLOR['label'], fg=COLOR['bg'],
                  relief='flat', padx=16, font=('Segoe UI', 9)
                  ).pack(side='left', padx=6)
        tk.Button(btn_frame, text='取消', command=dlg.destroy,
                  bg=COLOR['menubar_bg'], fg=COLOR['fg'],
                  relief='flat', padx=16, font=('Segoe UI', 9)
                  ).pack(side='left', padx=6)

    # ── 查找 ────────────────────────────────
    def _find_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title('查找')
        dlg.geometry('360x80')
        dlg.resizable(False, False)
        dlg.configure(bg=COLOR['bg'])
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text='查找：', bg=COLOR['bg'], fg=COLOR['fg'],
                 font=('Segoe UI', 10)).grid(row=0, column=0, padx=8, pady=10)
        entry = tk.Entry(dlg, bg=COLOR['select_bg'], fg=COLOR['fg'],
                         insertbackground=COLOR['cursor'],
                         font=self.code_font, relief='flat', bd=4)
        entry.grid(row=0, column=1, padx=4, pady=10, sticky='ew')
        dlg.columnconfigure(1, weight=1)
        entry.focus_set()

        def do_find():
            kw = entry.get()
            if not kw:
                return
            self.editor.tag_remove('sel', '1.0', 'end')
            start = '1.0'
            found_any = False
            while True:
                pos = self.editor.search(kw, start, stopindex='end')
                if not pos:
                    break
                end = f'{pos}+{len(kw)}c'
                self.editor.tag_add('sel', pos, end)
                if not found_any:
                    self.editor.see(pos)
                    found_any = True
                start = end
            if not found_any:
                self._console_write(f'未找到：{kw!r}\n', 'error')
            dlg.destroy()

        tk.Button(dlg, text='查找', command=do_find,
                  bg=COLOR['label'], fg=COLOR['bg'],
                  relief='flat', padx=10,
                  font=('Segoe UI', 9)).grid(row=0, column=2, padx=8)
        entry.bind('<Return>', lambda e: do_find())

    # ── 语法高亮 ────────────────────────────
    def _clear_tags(self, start='1.0', end='end'):
        for tag in ('keyword','label','string','number','comment','operator','type'):
            self.editor.tag_remove(tag, start, end)

    def _highlight_all(self):
        self._do_highlight('1.0', 'end')

    def _highlight_visible(self):
        # 只高亮可见区域附近，提升性能
        top = self.editor.index('@0,0')
        bot = self.editor.index(f'@0,{self.editor.winfo_height()}')
        # 扩展几十行缓冲
        top_line = max(1, int(top.split('.')[0]) - 10)
        bot_line = int(bot.split('.')[0]) + 10
        self._do_highlight(f'{top_line}.0', f'{bot_line}.end')

    def _do_highlight(self, start, end):
        text = self.editor.get(start, end)
        self._clear_tags(start, end)
        self._apply_regex_highlight(text, start)

    def _pos(self, base_index, text, char_offset):
        """把 char_offset 转成 text widget index（相对于 base_index）"""
        lines_before = text[:char_offset].count('\n')
        if lines_before == 0:
            base_line, base_col = map(int, base_index.split('.'))
            col = base_col + char_offset
            return f'{base_line}.{col}'
        else:
            base_line = int(base_index.split('.')[0])
            last_nl = text[:char_offset].rfind('\n')
            col = char_offset - last_nl - 1
            return f'{base_line + lines_before}.{col}'

    def _apply_regex_highlight(self, text, base):
        e = self.editor
        patterns = [
            # 单行注释
            ('comment',  r'//[^\n]*'),
            # 块注释
            ('comment',  r'/\*.*?\*/'),
            # 字符串
            ('string',   r'"(?:[^"\\]|\\.)*"'),
            # 字符
            ('string',   r"'(?:[^'\\]|\\.)'"),
            # 标签（反引号语法）
            ('label',    r'`[a-zA-Z_/][a-zA-Z0-9_/]*'),
            # 数字
            ('number',   r'\b\d+(?:\.\d+)?\b'),
            # 关键字（全字匹配）
            ('keyword',  r'\b(?:' + '|'.join(re.escape(k) for k in KEYWORDS) + r')\b'),
            # 类型
            ('type',     r'\b(?:int|float|char|string|bool)\b'),
            # 运算符
            ('operator', r'->|<-|==|!=|<=|>=|\+=|-=|\*=|/=|&&|\|\|'),
        ]
        for tag, pat in patterns:
            flags = re.DOTALL if '\\*' in pat else 0
            for m in re.finditer(pat, text, flags):
                s = self._pos(base, text, m.start())
                en = self._pos(base, text, m.end())
                e.tag_add(tag, s, en)


# ─────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────
def main():
    app = WquickIDE()
    app.line_numbers._font = app.code_font
    app.mainloop()


if __name__ == '__main__':
    main()
