#!/usr/bin/env python3
"""
Wquick 1.4 解释器（Python实现）
可直接运行 .wq 文件，不需要 C++ 编译器
用法：python wqi.py <source.wq>
"""
import sys
import re
import os

# =================== 词法分析 ===================
import enum

class TT(enum.Enum):
    INT=1; FLOAT=2; STR=3; CHAR=4; BOOL=5
    IDENT=6; KW=7
    PLUS=8; MINUS=9; STAR=10; SLASH=11; MOD=38
    ASSIGN=12; EQ=13; NEQ=14; LT=15; GT=16; LE=17; GE=18
    AND=19; OR=20; NOT=21
    PLUS_EQ=22; MINUS_EQ=23; STAR_EQ=24; SLASH_EQ=25
    ARROW_R=26; ARROW_L=27; DOT=28
    SEMI=29; COLON=30; COMMA=31
    LPAR=32; RPAR=33; LBRACE=34; RBRACE=35; LBRAK=36; RBRAK=37
    LABEL=39; EOF=99

KEYWORDS = {
    'let','if','elif','else','for','while','return','import',
    'break','continue',
    'int','float','char','string','bool','const',
    'this','super','extends','true','false'
}

class Token:
    def __init__(self, tt, val, line=0):
        self.tt = tt; self.val = val; self.line = line
    def __repr__(self): return f"Token({self.tt},{self.val!r})"

def tokenize(src):
    tokens = []; i = 0; line = 1
    n = len(src)
    def peek(o=0):
        return src[i+o] if i+o < n else '\0'

    while i < n:
        # 跳过空白
        if src[i] in ' \t\r\n':
            if src[i] == '\n': line += 1
            i += 1; continue
        # 注释
        if src[i] == '/' and peek(1) == '/':
            while i < n and src[i] != '\n': i += 1
            continue
        if src[i] == '/' and peek(1) == '*':
            i += 2
            while i < n and not (src[i] == '*' and peek(1) == '/'):
                if src[i] == '\n': line += 1
                i += 1
            i += 2; continue
        # 字符串
        if src[i] == '"':
            i += 1; s = ""
            while i < n and src[i] != '"':
                if src[i] == '\\':
                    i += 1
                    ec = src[i] if i < n else ''
                    s += {'n':'\n','t':'\t','"':'"','\\':'\\','0':'\0'}.get(ec, ec)
                else: s += src[i]
                i += 1
            i += 1
            tokens.append(Token(TT.STR, s, line)); continue
        # 字符
        if src[i] == "'":
            i += 1; s = ""
            if i < n and src[i] == '\\':
                i += 1; ec = src[i] if i < n else ''
                s = {'n':'\n','t':'\t',"'":'\'','\\':'\\','0':'\0'}.get(ec, ec)
                i += 1
            elif i < n:
                s = src[i]; i += 1
            if i < n and src[i] == "'": i += 1
            tokens.append(Token(TT.CHAR, s, line)); continue
        # 数字
        if src[i].isdigit():
            s = ""; is_float = False
            while i < n and (src[i].isdigit() or src[i] == '.'):
                if src[i] == '.': is_float = True
                s += src[i]; i += 1
            tokens.append(Token(TT.FLOAT if is_float else TT.INT, s, line)); continue
        # 标签 (backtick)
        if src[i] == '`':
            i += 1; s = ""
            while i < n and (src[i].isalnum() or src[i] in '_/'):
                s += src[i]; i += 1
            tokens.append(Token(TT.LABEL, s, line)); continue
        # 标识符/关键字
        if src[i].isalpha() or src[i] == '_':
            s = ""
            while i < n and (src[i].isalnum() or src[i] == '_'):
                s += src[i]; i += 1
            if s in KEYWORDS:
                tokens.append(Token(TT.KW, s, line))
            else:
                tokens.append(Token(TT.IDENT, s, line))
            continue
        # 多字符运算符
        two = src[i:i+2]
        ops2 = {
            '->': TT.ARROW_R, '<-': TT.ARROW_L,
            '==': TT.EQ, '!=': TT.NEQ, '<=': TT.LE, '>=': TT.GE,
            '&&': TT.AND, '||': TT.OR,
            '+=': TT.PLUS_EQ, '-=': TT.MINUS_EQ,
            '*=': TT.STAR_EQ, '/=': TT.SLASH_EQ
        }
        if two in ops2:
            tokens.append(Token(ops2[two], two, line)); i += 2; continue
        # 单字符
        ops1 = {
            '+':TT.PLUS,'-':TT.MINUS,'*':TT.STAR,'/':TT.SLASH,'%':TT.MOD,
            '=':TT.ASSIGN,'<':TT.LT,'>':TT.GT,'!':TT.NOT,'.':TT.DOT,
            ';':TT.SEMI,':':TT.COLON,',':TT.COMMA,
            '(':TT.LPAR,')':TT.RPAR,'{':TT.LBRACE,'}':TT.RBRACE,
            '[':TT.LBRAK,']':TT.RBRAK
        }
        if src[i] in ops1:
            tokens.append(Token(ops1[src[i]], src[i], line)); i += 1; continue
        i += 1  # 跳过未知字符（如 < > 在类型中已经被解析）

    tokens.append(Token(TT.EOF, '', line))
    return tokens

# =================== 解释器 ===================

class ReturnException(Exception):
    def __init__(self, val): self.val = val

class BreakException(Exception): pass
class ContinueException(Exception): pass

class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name)
        raise NameError(f"Undefined variable: {name!r}")

    def set(self, name, val):
        if name in self.vars:
            self.vars[name] = val; return
        if self.parent and self.parent.has(name):
            self.parent.set(name, val); return
        self.vars[name] = val

    def define(self, name, val):
        self.vars[name] = val

    def has(self, name):
        if name in self.vars: return True
        if self.parent: return self.parent.has(name)
        return False

class Function:
    def __init__(self, name, params, body, closure):
        self.name = name; self.params = params
        self.body = body; self.closure = closure

class WqInstance:
    def __init__(self, cls): self.cls = cls; self.fields = {}

    def get(self, name):
        if name in self.fields: return self.fields[name]
        if name in self.cls.methods: return ('method', self.cls.methods[name], self)
        raise AttributeError(f"No attribute {name!r}")

    def set(self, name, val): self.fields[name] = val

class WqClass:
    def __init__(self, name, parent, fields, methods):
        self.name = name; self.parent = parent
        self.fields = fields; self.methods = methods

class Interpreter:
    def __init__(self):
        self.global_env = Environment()
        self.ioplus_prompt = ""
        self.templates = {}  # template名 -> list of (type, name)
        self.classes = {}    # class名 -> WqClass

    def run(self, tokens):
        self.tokens = tokens
        self.pos = 0
        # 两遍：先收集全局定义（def/template/class/namespace），再执行start
        self.collect_globals()
        self.execute_start()

    def peek(self, o=0):
        p = self.pos + o
        if p >= len(self.tokens): return self.tokens[-1]
        return self.tokens[p]

    def advance(self):
        t = self.tokens[self.pos]
        if self.pos + 1 < len(self.tokens): self.pos += 1
        return t

    def check(self, tt, val=None):
        t = self.peek()
        if t.tt != tt: return False
        if val is not None and t.val != val: return False
        return True

    def match(self, tt, val=None):
        if self.check(tt, val): self.advance(); return True
        return False

    def expect(self, tt, val=None, msg=""):
        t = self.peek()
        if t.tt != tt or (val and t.val != val):
            raise SyntaxError(f"[Line {t.line}] Expected {msg or val or tt}, got {t.val!r}")
        return self.advance()

    # ======= 两遍扫描 =======
    def collect_globals(self):
        """扫描所有顶层定义，注册到全局环境"""
        save = self.pos
        while not self.check(TT.EOF):
            if self.check(TT.KW, 'import'):
                self.parse_import()
            elif self.check(TT.KW, 'let'):
                # 顶层全局变量声明
                self.exec_let(self.global_env)
            elif self.check(TT.LABEL, 'def'):
                self.parse_def(self.global_env)
            elif self.check(TT.LABEL, 'template'):
                self.parse_template()
            elif self.check(TT.LABEL, 'namespace'):
                self.parse_namespace(self.global_env)
            elif self.check(TT.LABEL, 'class'):
                self.parse_class()
            elif self.check(TT.LABEL, 'start'):
                # 跳过start块，留给execute_start
                self.advance()
                self.skip_until_label('/')
                self.match(TT.LABEL, '/')
            else:
                self.advance()

    def skip_until_label(self, lbl):
        depth = 0
        while not self.check(TT.EOF):
            if self.check(TT.LABEL):
                name = self.peek().val
                if name in ('def','namespace','class','start','loop','switch','file','template'):
                    depth += 1
                elif name.endswith('/') or name == '/':
                    if depth == 0: return
                    depth -= 1
            self.advance()

    def execute_start(self):
        self.pos = 0
        while not self.check(TT.EOF):
            if self.check(TT.LABEL, 'start'):
                self.advance()  # consume `start
                env = Environment(self.global_env)
                try:
                    self.exec_block_until(env, TT.LABEL, '/')
                except ReturnException:
                    pass
                self.match(TT.LABEL, '/')
                return
            elif self.check(TT.KW, 'import'):
                self.parse_import()
            elif self.check(TT.LABEL):
                # 跳过已经处理过的全局定义
                lbl = self.peek().val
                self.advance()
                end = lbl + '/'
                self.skip_until_label(end if lbl != 'def' else 'def/')
                self.match(TT.LABEL)
            else:
                self.advance()

    def exec_block_until(self, env, stop_tt, stop_val=None):
        while not self.check(TT.EOF):
            if self.check(stop_tt, stop_val): return
            self.exec_stmt(env)

    def exec_stmt(self, env):
        t = self.peek()
        if t.tt == TT.KW:
            if t.val == 'let': self.exec_let(env); return
            if t.val == 'if':  self.exec_if(env); return
            if t.val == 'for': self.exec_for(env); return
            if t.val == 'while': self.exec_while(env); return
            if t.val == 'return': self.exec_return(env); return
            if t.val == 'import': self.parse_import(); return
            if t.val == 'break':
                self.advance(); self.match(TT.SEMI); raise BreakException()
            if t.val == 'continue':
                self.advance(); self.match(TT.SEMI); raise ContinueException()
        if t.tt == TT.IDENT:
            if t.val == 'output': self.exec_output(env); return
            if t.val == 'input':  self.exec_input(env); return
        if t.tt == TT.LABEL:
            lbl = t.val
            if lbl == 'loop':   self.exec_loop(env); return
            if lbl == 'switch': self.exec_switch(env); return
            if lbl == 'def':    self.parse_def(env); return
            if lbl == 'file':   self.exec_file(env); return
            if lbl == 'template': self.parse_template(); return
            if lbl == 'namespace': self.parse_namespace(env); return
            if lbl == 'class': self.parse_class(); return
            # 跳过结束标签
            if lbl.endswith('/') or lbl == '/': return
            self.advance(); return
        # 表达式语句（赋值/调用/ioplus）
        expr = self.parse_expr(env)
        # ioplus流式
        if self.check(TT.ARROW_R):
            targets = []
            while self.match(TT.ARROW_R):
                targets.append(self.parse_expr(env))
            self.match(TT.SEMI)
            if self.ioplus_prompt and self.ioplus_prompt != '0':
                print(self.ioplus_prompt, end='')
            for target in targets:
                val = input()
                self.assign_target(target, self.auto_cast(val), env)
            return
        if self.check(TT.ARROW_L):
            vals = []
            while self.match(TT.ARROW_L):
                vals.append(self.eval_expr(self.parse_expr(env), env))
            self.match(TT.SEMI)
            print(*[str(v) for v in vals], sep='', end='')
            return
        # 求值表达式（重要：执行赋值/调用等副作用）
        self.eval_expr(expr, env)
        self.match(TT.SEMI)

    def auto_cast(self, s):
        try: return int(s)
        except: pass
        try: return float(s)
        except: pass
        return s

    def assign_target(self, target, val, env):
        """对解析出的表达式目标进行赋值（ioplus）"""
        if isinstance(target, str):
            env.set(target, val)
        elif isinstance(target, tuple):
            op, obj, key = target
            if op == 'index': obj[key] = val
            elif op == 'attr': obj.set(key, val)

    def exec_let(self, env):
        self.advance()  # let
        type_name = None
        is_const = False
        # 解析 <type>
        if self.check(TT.LT):
            self.advance()
            tn = self.peek().val; self.advance()
            if tn == 'const': is_const = True
            else: type_name = tn
            self.expect(TT.GT, msg='>')
        name = self.expect(TT.IDENT).val
        # 数组声明 arr[size]
        if self.match(TT.LBRAK):
            size = self.eval_expr(self.parse_expr(env), env)
            self.expect(TT.RBRAK, msg=']')
            self.match(TT.SEMI)
            env.define(name, [None] * int(size))
            return
        val = None
        if self.match(TT.ASSIGN):
            # 数组字面量
            if self.check(TT.LBRAK):
                self.advance()
                elems = []
                if not self.check(TT.RBRAK):
                    elems.append(self.eval_expr(self.parse_expr(env), env))
                    while self.match(TT.COMMA):
                        elems.append(self.eval_expr(self.parse_expr(env), env))
                self.expect(TT.RBRAK, msg=']')
                self.match(TT.SEMI)
                env.define(name, elems)
                return
            val = self.eval_expr(self.parse_expr(env), env)
        self.match(TT.SEMI)
        env.define(name, val)

    def exec_if(self, env):
        # 收集所有分支的(cond_start, cond_end, body_start, body_end)
        branches = []  # (cond_start, cond_end, body_start, body_end, is_else)

        # if
        self.advance()  # if
        self.expect(TT.LPAR, msg='(')
        cond_start = self.pos
        self.parse_expr(env)  # 仅推进pos
        cond_end = self.pos
        self.expect(TT.RPAR, msg=')')
        self.expect(TT.LBRACE, msg='{')
        body_start = self.pos
        depth = 1
        while not self.check(TT.EOF):
            if self.check(TT.LBRACE): depth += 1
            elif self.check(TT.RBRACE):
                depth -= 1
                if depth == 0: break
            self.advance()
        body_end = self.pos
        self.expect(TT.RBRACE, msg='}')
        branches.append((cond_start, cond_end, body_start, body_end, False))

        # elif*
        while self.check(TT.KW, 'elif'):
            self.advance()
            self.expect(TT.LPAR, msg='(')
            cs = self.pos
            self.parse_expr(env)
            ce = self.pos
            self.expect(TT.RPAR, msg=')')
            self.expect(TT.LBRACE, msg='{')
            bs = self.pos
            depth = 1
            while not self.check(TT.EOF):
                if self.check(TT.LBRACE): depth += 1
                elif self.check(TT.RBRACE):
                    depth -= 1
                    if depth == 0: break
                self.advance()
            be = self.pos
            self.expect(TT.RBRACE, msg='}')
            branches.append((cs, ce, bs, be, False))

        # else?
        if self.check(TT.KW, 'else'):
            self.advance()
            self.expect(TT.LBRACE, msg='{')
            bs = self.pos
            depth = 1
            while not self.check(TT.EOF):
                if self.check(TT.LBRACE): depth += 1
                elif self.check(TT.RBRACE):
                    depth -= 1
                    if depth == 0: break
                self.advance()
            be = self.pos
            self.expect(TT.RBRACE, msg='}')
            branches.append((0, 0, bs, be, True))

        after = self.pos

        for (cs, ce, bs, be, is_else) in branches:
            if is_else:
                self.pos = bs
                inner_env = Environment(env)
                while self.pos < be:
                    self.exec_stmt(inner_env)
                self.pos = after
                return
            else:
                self.pos = cs
                cond_expr = self.parse_expr(env)
                cond_val = self.eval_expr(cond_expr, env)
                if cond_val:
                    self.pos = bs
                    inner_env = Environment(env)
                    while self.pos < be:
                        self.exec_stmt(inner_env)
                    self.pos = after
                    return
        self.pos = after

    def exec_for(self, env):
        self.advance()  # for
        self.expect(TT.LPAR, msg='(')
        loop_env = Environment(env)
        # init: 支持 let 或普通表达式，后面是逗号（不是分号）
        if self.check(TT.KW, 'let'):
            self.advance()  # let
            # 跳过可选的 <type>
            if self.check(TT.LT):
                self.advance()
                while not self.check(TT.GT) and not self.check(TT.EOF): self.advance()
                self.advance()
            var_name = self.expect(TT.IDENT).val
            val = None
            if self.match(TT.ASSIGN):
                val = self.eval_expr(self.parse_expr(loop_env), loop_env)
            loop_env.define(var_name, val)
            self.expect(TT.COMMA, msg=',')
        else:
            self.eval_expr(self.parse_expr(loop_env), loop_env)
            self.match(TT.COMMA)
        # cond
        cond_expr = self.parse_expr(loop_env)
        self.expect(TT.COMMA, msg=',')
        step_expr = self.parse_expr(loop_env)
        self.expect(TT.RPAR, msg=')')
        self.expect(TT.LBRACE, msg='{')
        body_start = self.pos
        depth = 1
        while not self.check(TT.EOF):
            if self.check(TT.LBRACE): depth += 1
            elif self.check(TT.RBRACE):
                depth -= 1
                if depth == 0: break
            self.advance()
        body_end = self.pos
        self.expect(TT.RBRACE, msg='}')
        after = self.pos

        while self.eval_expr(cond_expr, loop_env):
            self.pos = body_start
            inner_env = Environment(loop_env)
            try:
                while self.pos < body_end:
                    self.exec_stmt(inner_env)
            except BreakException:
                break
            except ContinueException:
                pass
            self.eval_expr(step_expr, loop_env)
        self.pos = after

    def exec_while(self, env):
        self.advance()  # while
        self.expect(TT.LPAR, msg='(')
        cond_start = self.pos
        cond_expr = self.parse_expr(env)
        self.expect(TT.RPAR, msg=')')
        self.expect(TT.LBRACE, msg='{')
        body_start = self.pos
        depth = 1
        while not self.check(TT.EOF):
            if self.check(TT.LBRACE): depth += 1
            elif self.check(TT.RBRACE):
                depth -= 1
                if depth == 0: break
            self.advance()
        body_end = self.pos
        self.expect(TT.RBRACE, msg='}')
        after = self.pos

        while True:
            # 每次重新解析并求cond
            self.pos = cond_start
            cond_expr = self.parse_expr(env)
            if not self.eval_expr(cond_expr, env):
                break
            self.pos = body_start
            inner = Environment(env)
            try:
                while self.pos < body_end:
                    self.exec_stmt(inner)
            except BreakException:
                break
            except ContinueException:
                pass
        self.pos = after

    def exec_loop(self, env):
        self.advance()  # `loop
        count = int(self.eval_expr(self.parse_expr(env), env))
        body_start = self.pos
        # 找到 `loop/
        depth = 0
        while not self.check(TT.EOF):
            if self.check(TT.LABEL, 'loop'): depth += 1
            elif self.check(TT.LABEL, 'loop/'):
                if depth == 0: break
                depth -= 1
            self.advance()
        body_end = self.pos
        self.expect(TT.LABEL, 'loop/')
        after = self.pos
        for _ in range(count):
            self.pos = body_start
            inner = Environment(env)
            while self.pos < body_end:
                self.exec_stmt(inner)
        self.pos = after

    def exec_switch(self, env):
        self.advance()  # `switch
        subject = self.eval_expr(self.parse_expr(env), env)
        # 收集 cases
        cases = []
        while not self.check(TT.LABEL, 'switch/') and not self.check(TT.EOF):
            if self.check(TT.KW, 'if'):
                self.advance()
                self.expect(TT.LPAR, msg='(')
                val = self.eval_expr(self.parse_expr(env), env)
                self.expect(TT.RPAR, msg=')')
                self.expect(TT.COLON, msg=':')
                bs = self.pos
                while (not self.check(TT.KW,'if') and not self.check(TT.KW,'else') and
                       not self.check(TT.LABEL,'switch/') and not self.check(TT.EOF)):
                    self.advance()  # skip for now (collect pos)
                cases.append(('case', val, bs, self.pos))
            elif self.check(TT.KW, 'else'):
                self.advance()
                self.expect(TT.COLON, msg=':')
                bs = self.pos
                while not self.check(TT.LABEL,'switch/') and not self.check(TT.EOF):
                    self.advance()
                cases.append(('default', None, bs, self.pos))
            else:
                self.advance()
        self.expect(TT.LABEL, 'switch/')
        after = self.pos

        for (kind, val, bs, be) in cases:
            if kind == 'case' and subject == val:
                self.pos = bs
                inner = Environment(env)
                while self.pos < be: self.exec_stmt(inner)
                self.pos = after; return
            elif kind == 'default':
                self.pos = bs
                inner = Environment(env)
                while self.pos < be: self.exec_stmt(inner)
                self.pos = after; return
        self.pos = after

    def exec_return(self, env):
        self.advance()  # return
        self.expect(TT.COLON, msg=':')
        val = None
        if not self.check(TT.SEMI):
            val = self.eval_expr(self.parse_expr(env), env)
        self.match(TT.SEMI)
        raise ReturnException(val)

    def exec_output(self, env):
        self.advance()  # output
        self.expect(TT.COLON, msg=':')
        parts = [self.eval_expr(self.parse_expr(env), env)]
        while self.match(TT.COMMA):
            parts.append(self.eval_expr(self.parse_expr(env), env))
        self.match(TT.SEMI)
        print(*[str(p) for p in parts], sep='', end='')

    def exec_input(self, env):
        self.advance()  # input
        self.expect(TT.COLON, msg=':')
        prompt = None; target = None
        if not self.check(TT.COMMA):
            prompt = self.eval_expr(self.parse_expr(env), env)
        self.expect(TT.COMMA, msg=',')
        if not self.check(TT.SEMI):
            target_expr = self.parse_expr(env)
            target = target_expr
        self.match(TT.SEMI)
        if prompt: print(str(prompt), end='')
        val = self.auto_cast(input())
        if target is not None:
            self.assign_target(target, val, env)

    def parse_import(self):
        self.advance()  # import
        self.match(TT.COLON)
        # 读取模块名（可能是0，数字，或标识符）
        t = self.peek()
        if t.tt in (TT.INT, TT.IDENT, TT.KW):
            self.advance()
        self.match(TT.SEMI)

    def exec_file(self, env):
        self.advance()  # `file
        while not self.check(TT.LABEL, 'file/') and not self.check(TT.EOF):
            if self.check(TT.IDENT):
                op = self.advance().val
                self.expect(TT.COLON, msg=':')
                args = [self.eval_expr(self.parse_expr(env), env)]
                while self.match(TT.COMMA):
                    args.append(self.eval_expr(self.parse_expr(env), env))
                self.match(TT.SEMI)
                if op == 'read' and len(args) >= 3:
                    try:
                        enc = args[1] if isinstance(args[1], str) else 'utf-8'
                        with open(args[0], 'r', encoding=enc) as f:
                            content = f.read()
                        env.set(str(args[2]), content)
                    except: pass
                elif op == 'write' and len(args) >= 3:
                    enc = args[1] if isinstance(args[1], str) else 'utf-8'
                    with open(args[0], 'w', encoding=enc) as f:
                        f.write(str(args[2]))
                elif op == 'a' and len(args) >= 3:
                    enc = args[1] if isinstance(args[1], str) else 'utf-8'
                    with open(args[0], 'a', encoding=enc) as f:
                        f.write(str(args[2]))
            else:
                self.advance()
        self.match(TT.LABEL, 'file/')

    def parse_def(self, env):
        self.advance()  # `def
        name = self.expect(TT.IDENT).val
        params = []
        # 支持两种格式：
        # 1. `def name, param1, param2  (旧格式，逗号分隔)
        # 2. `def name(param:type, ...) -> rettype  (新格式，括号+类型注解)
        if self.match(TT.LPAR):
            # 新格式：括号包裹
            while not self.check(TT.RPAR) and not self.check(TT.EOF):
                if self.check(TT.IDENT):
                    params.append(self.advance().val)
                    # 跳过 :type
                    if self.match(TT.COLON):
                        while not self.check(TT.COMMA) and not self.check(TT.RPAR) and not self.check(TT.EOF):
                            self.advance()
                if not self.match(TT.COMMA): break
            self.match(TT.RPAR)
            # 跳过 -> rettype（只跳过一个类型标识符）
            if self.match(TT.ARROW_R):
                if self.peek().tt in (TT.KW, TT.IDENT):
                    self.advance()  # 跳过返回类型名
        elif self.match(TT.COMMA):
            # 旧格式
            while self.check(TT.IDENT):
                params.append(self.advance().val)
                if not self.match(TT.COMMA): break
        body_start = self.pos
        # 找到 `def/
        depth = 0
        while not self.check(TT.EOF):
            if self.check(TT.LABEL, 'def'): depth += 1
            elif self.check(TT.LABEL, 'def/'):
                if depth == 0: break
                depth -= 1
            self.advance()
        body_end = self.pos
        self.match(TT.LABEL, 'def/')
        func = Function(name, params, (body_start, body_end), env)
        env.define(name, func)

    def parse_template(self):
        self.advance()  # `template
        name = self.expect(TT.IDENT).val
        fields = []
        while not self.check(TT.LABEL, 'template/') and not self.check(TT.EOF):
            if self.check(TT.KW, 'let'):
                self.advance()
                tn = None
                if self.check(TT.LT):
                    self.advance()
                    tn = self.peek().val; self.advance()
                    self.match(TT.GT)
                fn = self.expect(TT.IDENT).val
                self.match(TT.SEMI)
                fields.append((tn, fn))
            else:
                self.advance()
        self.match(TT.LABEL, 'template/')
        self.templates[name] = fields

    def parse_namespace(self, parent_env):
        self.advance()  # `namespace
        name = self.expect(TT.IDENT).val
        ns_env = Environment(parent_env)
        while not self.check(TT.LABEL, 'namespace/') and not self.check(TT.EOF):
            if self.check(TT.KW, 'let'):
                self.exec_let(ns_env)
            elif self.check(TT.LABEL, 'def'):
                self.parse_def(ns_env)
            elif self.check(TT.LABEL, 'namespace'):
                self.parse_namespace(ns_env)
            else:
                self.advance()
        self.match(TT.LABEL, 'namespace/')
        parent_env.define(name, ns_env)

    def parse_class(self):
        self.advance()  # `class
        name = self.expect(TT.IDENT).val
        parent = None
        if self.check(TT.KW, 'extends'):
            self.advance()
            parent = self.expect(TT.IDENT).val
        fields = {}
        methods = {}
        while not self.check(TT.LABEL, 'class/') and not self.check(TT.EOF):
            if self.check(TT.KW, 'let'):
                self.advance()
                tn = None
                if self.check(TT.LT):
                    self.advance(); self.advance(); self.match(TT.GT)
                fn = self.expect(TT.IDENT).val
                init = None
                if self.match(TT.ASSIGN):
                    init = self.parse_expr(self.global_env)
                self.match(TT.SEMI)
                fields[fn] = init
            elif self.check(TT.LABEL, 'constructor'):
                self.advance()
                self.match(TT.COMMA)
                params = []
                while self.check(TT.IDENT):
                    params.append(self.advance().val)
                    if not self.match(TT.COMMA): break
                bs = self.pos
                while not self.check(TT.LABEL, 'constructor/') and not self.check(TT.EOF):
                    self.advance()
                be = self.pos
                self.match(TT.LABEL, 'constructor/')
                methods['__init__'] = Function('__init__', params, (bs, be), self.global_env)
            elif self.check(TT.LABEL, 'method'):
                self.advance()
                mname = self.expect(TT.IDENT).val
                self.match(TT.COMMA)
                params = []
                while self.check(TT.IDENT):
                    params.append(self.advance().val)
                    if not self.match(TT.COMMA): break
                bs = self.pos
                while not self.check(TT.LABEL, 'method/') and not self.check(TT.EOF):
                    self.advance()
                be = self.pos
                self.match(TT.LABEL, 'method/')
                methods[mname] = Function(mname, params, (bs, be), self.global_env)
            else:
                self.advance()
        self.match(TT.LABEL, 'class/')
        cls = WqClass(name, parent, fields, methods)
        self.classes[name] = cls
        self.global_env.define(name, cls)

    def call_function(self, func, args, env):
        if isinstance(func, Function):
            call_env = Environment(func.closure)
            for p, a in zip(func.params, args):
                call_env.define(p, a)
            save = self.pos
            bs, be = func.body
            self.pos = bs
            try:
                while self.pos < be:
                    self.exec_stmt(call_env)
            except ReturnException as r:
                self.pos = save
                return r.val
            self.pos = save
            return None
        elif isinstance(func, WqClass):
            # 实例化
            inst = WqInstance(func)
            # 初始化字段
            for fname, finit in func.fields.items():
                if finit is not None:
                    inst.fields[fname] = self.eval_expr(finit, env)
                else:
                    inst.fields[fname] = None
            # 调用构造函数
            if '__init__' in func.methods:
                ctor = func.methods['__init__']
                call_env = Environment(self.global_env)
                call_env.define('this', inst)
                for p, a in zip(ctor.params, args):
                    call_env.define(p, a)
                save = self.pos
                bs, be = ctor.body
                self.pos = bs
                try:
                    while self.pos < be:
                        self.exec_stmt(call_env)
                except ReturnException:
                    pass
                self.pos = save
            return inst
        elif func == 'int':   return int(args[0]) if args else 0
        elif func == 'float': return float(args[0]) if args else 0.0
        elif func == 'char':  return chr(int(args[0])) if args else '\0'
        elif func == 'string':return str(args[0]) if args else ''
        raise TypeError(f"Not callable: {func!r}")

    # ======= 表达式解析 =======
    def parse_expr(self, env):
        """返回AST节点（lazy），通过eval_expr求值"""
        return self.parse_assign_expr(env)

    def parse_assign_expr(self, env):
        left = self.parse_or_expr(env)
        if self.check(TT.ASSIGN):
            self.advance()
            right = self.parse_assign_expr(env)
            return ('assign', left, right)
        for op_tt, op in [(TT.PLUS_EQ,'+='), (TT.MINUS_EQ,'-='),
                          (TT.STAR_EQ,'*='), (TT.SLASH_EQ,'/=')]:
            if self.check(op_tt):
                self.advance()
                right = self.parse_assign_expr(env)
                return ('compound_assign', op, left, right)
        return left

    def parse_or_expr(self, env):
        left = self.parse_and_expr(env)
        while self.check(TT.OR):
            self.advance()
            right = self.parse_and_expr(env)
            left = ('binop', '||', left, right)
        return left

    def parse_and_expr(self, env):
        left = self.parse_eq_expr(env)
        while self.check(TT.AND):
            self.advance()
            right = self.parse_eq_expr(env)
            left = ('binop', '&&', left, right)
        return left

    def parse_eq_expr(self, env):
        left = self.parse_rel_expr(env)
        while self.check(TT.EQ) or self.check(TT.NEQ):
            op = self.advance().val
            right = self.parse_rel_expr(env)
            left = ('binop', op, left, right)
        return left

    def parse_rel_expr(self, env):
        left = self.parse_add_expr(env)
        while self.peek().tt in (TT.LT, TT.GT, TT.LE, TT.GE):
            op = self.advance().val
            right = self.parse_add_expr(env)
            left = ('binop', op, left, right)
        return left

    def parse_add_expr(self, env):
        left = self.parse_mul_expr(env)
        while self.check(TT.PLUS) or self.check(TT.MINUS):
            op = self.advance().val
            right = self.parse_mul_expr(env)
            left = ('binop', op, left, right)
        return left

    def parse_mul_expr(self, env):
        left = self.parse_unary_expr(env)
        while self.check(TT.STAR) or self.check(TT.SLASH) or self.check(TT.MOD):
            op = self.advance().val
            right = self.parse_unary_expr(env)
            left = ('binop', op, left, right)
        return left

    def parse_unary_expr(self, env):
        if self.check(TT.NOT):
            self.advance()
            return ('unary', '!', self.parse_unary_expr(env))
        if self.check(TT.MINUS):
            self.advance()
            return ('unary', '-', self.parse_unary_expr(env))
        return self.parse_postfix_expr(env)

    def parse_postfix_expr(self, env):
        e = self.parse_primary_expr(env)
        while True:
            if self.check(TT.DOT):
                self.advance()
                member = self.expect(TT.IDENT).val
                e = ('member', e, member)
            elif self.check(TT.LBRAK):
                self.advance()
                idx = self.parse_expr(env)
                self.expect(TT.RBRAK, msg=']')
                e = ('index', e, idx)
            elif self.check(TT.LPAR):
                self.advance()
                args = []
                if not self.check(TT.RPAR):
                    args.append(self.parse_expr(env))
                    while self.match(TT.COMMA):
                        args.append(self.parse_expr(env))
                self.expect(TT.RPAR, msg=')')
                e = ('call', e, args)
            else:
                break
        return e

    def parse_primary_expr(self, env):
        t = self.peek()
        if t.tt == TT.INT:
            self.advance(); return ('lit', int(t.val))
        if t.tt == TT.FLOAT:
            self.advance(); return ('lit', float(t.val))
        if t.tt == TT.STR:
            self.advance(); return ('lit', t.val)
        if t.tt == TT.CHAR:
            self.advance(); return ('lit', t.val[0] if t.val else '\0')
        if t.tt == TT.KW and t.val == 'true':
            self.advance(); return ('lit', True)
        if t.tt == TT.KW and t.val == 'false':
            self.advance(); return ('lit', False)
        if t.tt == TT.KW and t.val == 'this':
            self.advance(); return ('this',)
        if t.tt == TT.KW and t.val == 'super':
            self.advance()
            self.expect(TT.LPAR, msg='(')
            args = []
            if not self.check(TT.RPAR):
                args.append(self.parse_expr(env))
                while self.match(TT.COMMA):
                    args.append(self.parse_expr(env))
            self.expect(TT.RPAR, msg=')')
            return ('super_call', args)
        if t.tt == TT.LPAR:
            self.advance()
            e = self.parse_expr(env)
            self.expect(TT.RPAR, msg=')')
            return e
        # 类型转换
        if t.tt == TT.KW and t.val in ('int','float','char','string'):
            tp = self.advance().val
            self.expect(TT.LPAR, msg='(')
            arg = self.parse_expr(env)
            self.expect(TT.RPAR, msg=')')
            return ('cast', tp, arg)
        if t.tt == TT.IDENT:
            self.advance()
            return ('var', t.val)
        self.advance()
        return ('lit', None)

    def eval_expr(self, node, env):
        if node is None: return None
        if not isinstance(node, tuple): return node

        kind = node[0]
        if kind == 'lit': return node[1]
        if kind == 'var':
            name = node[1]
            # 内置类型转换函数
            if name in ('int','float','char','string'): return name
            # ioplus
            if name == 'iplus': return 'iplus'
            if name == 'oplus': return 'oplus'
            if name == 'ipluscfg': return env.get('ipluscfg') if env.has('ipluscfg') else self
            try: return env.get(name)
            except NameError:
                # 尝试查找类
                if name in self.classes: return self.classes[name]
                raise
        if kind == 'this':
            return env.get('this')
        if kind == 'super_call':
            # 简化实现
            return None
        if kind == 'cast':
            tp, arg = node[1], node[2]
            val = self.eval_expr(arg, env)
            if tp == 'int': return int(val)
            if tp == 'float': return float(val)
            if tp == 'char': return chr(int(val)) if isinstance(val, (int,float)) else val[0]
            if tp == 'string': return str(val)
        if kind == 'binop':
            _, op, l, r = node
            lv = self.eval_expr(l, env)
            rv = self.eval_expr(r, env)
            if op == '+':
                if isinstance(lv, str) or isinstance(rv, str): return str(lv) + str(rv)
                return lv + rv
            if op == '-': return lv - rv
            if op == '*': return lv * rv
            if op == '/': return round(lv / rv, 8)
            if op == '%': return lv % rv
            if op == '==': return lv == rv
            if op == '!=': return lv != rv
            if op == '<':  return lv < rv
            if op == '>':  return lv > rv
            if op == '<=': return lv <= rv
            if op == '>=': return lv >= rv
            if op == '&&': return bool(lv) and bool(rv)
            if op == '||': return bool(lv) or bool(rv)
        if kind == 'unary':
            _, op, e = node
            v = self.eval_expr(e, env)
            if op == '!': return not v
            if op == '-': return -v
        if kind == 'assign':
            _, target, val_node = node
            val = self.eval_expr(val_node, env)
            self._do_assign(target, val, env)
            return val
        if kind == 'compound_assign':
            _, op, target, val_node = node
            current = self.eval_expr(target, env)
            rhs = self.eval_expr(val_node, env)
            if op == '+=': result = current + rhs
            elif op == '-=': result = current - rhs
            elif op == '*=': result = current * rhs
            elif op == '/=': result = round(current / rhs, 8)
            else: result = rhs
            self._do_assign(target, result, env)
            return result
        if kind == 'member':
            _, obj_node, member = node
            obj = self.eval_expr(obj_node, env)
            if isinstance(obj, WqInstance):
                r = obj.get(member)
                if isinstance(r, tuple) and r[0] == 'method':
                    return r  # 方法引用
                return r
            elif isinstance(obj, Environment):
                return obj.get(member)
            elif obj is self:  # ipluscfg
                if member == 'prompt': return self.ioplus_prompt
            raise AttributeError(f"Cannot access .{member} on {obj!r}")
        if kind == 'index':
            _, arr_node, idx_node = node
            arr = self.eval_expr(arr_node, env)
            idx = int(self.eval_expr(idx_node, env))
            return arr[idx]
        if kind == 'call':
            _, callee_node, arg_nodes = node
            callee = self.eval_expr(callee_node, env)
            args = [self.eval_expr(a, env) for a in arg_nodes]
            # 处理方法调用
            if isinstance(callee, tuple) and len(callee) == 3 and callee[0] == 'method':
                _, method_func, inst = callee
                call_env = Environment(method_func.closure)
                call_env.define('this', inst)
                for p, a in zip(method_func.params, args):
                    call_env.define(p, a)
                save = self.pos
                bs, be = method_func.body
                self.pos = bs
                try:
                    while self.pos < be:
                        self.exec_stmt(call_env)
                except ReturnException as r:
                    self.pos = save
                    return r.val
                self.pos = save
                return None
            # ipluscfg.prompt = 赋值通过assign处理
            return self.call_function(callee, args, env)
        return None

    def _do_assign(self, target, val, env):
        if not isinstance(target, tuple): return
        k = target[0]
        if k == 'var':
            name = target[1]
            if env.has(name):
                env.set(name, val)
            else:
                env.define(name, val)
        elif k == 'index':
            _, arr_node, idx_node = target
            arr = self.eval_expr(arr_node, env)
            idx = int(self.eval_expr(idx_node, env))
            arr[idx] = val
        elif k == 'member':
            _, obj_node, member = target
            obj = self.eval_expr(obj_node, env)
            if isinstance(obj, WqInstance):
                obj.set(member, val)
            elif isinstance(obj, Environment):
                obj.define(member, val)
            elif obj is self:  # ipluscfg
                if member == 'prompt': self.ioplus_prompt = str(val)


def main():
    if len(sys.argv) < 2:
        print("Wquick Interpreter (Python)")
        print("Usage: python wqi.py <source.wq>")
        return 1
    path = sys.argv[1]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        return 1

    try:
        tokens = tokenize(src)
        interp = Interpreter()
        interp.run(tokens)
    except SyntaxError as e:
        print(f"[Syntax Error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[Runtime Error] {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
