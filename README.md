# Wquick

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![GitHub release](https://img.shields.io/github/release/Baicai2026/Wquick)

**一门简洁、易上手的编程语言，学生自主研发。**

- 🎯 **简洁语法** – 贴近自然语言，学习成本低  
- ⚡ **本地执行** – 编译为原生 .exe，无需运行时  
- 📦 **内置工具** – 自带 g++ 编译器，开箱即用  
- 🕙 **time 标准库** – 1.5 新增 sleep / getTime / time()  

[🚀 快速开始](#快速开始) · [📖 语言速览](#语言速览) · [💾 下载 1.5.0](https://github.com/Baicai2026/Wquick/releases)


# Wquick 1.5

**Wquick** 是一门简洁、易上手的编程语言，语法设计贴近自然语言，编译后生成本地可执行程序。

---

## 快速开始

### 环境要求

- Windows 64位
- Python 3.x（运行 IDE）

### 启动 IDE

双击 `wqide.py`，或在终端运行：

```
python wqide.py
```

IDE 会自动查找编译器（`wqc.exe`）和内置 g++，无需手动配置。

### 第一个程序

新建文件，写入以下内容，按 **F6** 编译运行：

```wquick
import:0;
`start
    output:"Hello, Wquick!\n";
`/
```

**输出：**
```
Hello, Wquick!
```

---

## 语言速览

### 变量

```wquick
let x = 10;
let name = "Wquick";
x = 20;
```

### 输入 / 输出

```wquick
output:"结果是：", x, "\n";   // 输出
input:"请输入：", x;           // 输入到变量 x
```

### 数据类型

| 类型 | 说明 | 示例 |
|---|---|---|
| `string` | 文本 | `"hello"` |
| `int` | 整数 | `42` |
| `float` | 浮点数 | `3.14` |
| `char` | 单字符 | `'A'` |
| `bool` | 布尔值 | `true` / `false` |

类型转换：`int(x)`、`float(x)`、`char(x)`

### 运算符

```
+  -  *  /         算术
==  !=  >  <       比较
&&  ||  !          逻辑
+=  -=  *=  /=     复合赋值
```

### 判断

```wquick
if (x > 0)
{
    output:"正数\n";
}
elif (x == 0)
{
    output:"零\n";
}
else
{
    output:"负数\n";
}
```

### 循环

```wquick
// for 循环
for (let i = 0, i < 5, i += 1)
{
    output:i, " ";
}

// while 循环
while (x > 0)
{
    x -= 1;
}

// break / continue
for (let i = 0, i < 10, i += 1)
{
    if (i == 5) { break; }
    output:i, " ";
}
```

### 函数

```wquick
`def add, a, b
    return: a + b;
`def/

`start
    let result = add(3, 4);
    output:result, "\n";   // 7
`/
```

### 数组

```wquick
let <int> arr = [1, 2, 3, 4, 5];
output:arr[0];      // 1
arr[2] = 99;
```

### 常量

```wquick
let <const> MAX = 100;
```

### 命名空间

```wquick
`namespace math
    `def square, x
        return: x * x;
    `def/
`namespace/

`start
    output:math.square(5);   // 25
`/
```

### 类与对象

```wquick
`class Animal
    let <string> name;

    `constructor, n
        this.name = n;
    `constructor/

    `method speak,
        output:this.name, " says hello!\n";
    `method/
`class/

`start
    let a = Animal("Cat");
    a.speak();   // Cat says hello!
`/
```

---

## 标准库

### IOplus — 流式 IO

```wquick
import:IOplus;

ipluscfg.prompt = "输入：";
iplus -> a -> b -> c;          // 连续输入

oplus <- "结果：" <- a;        // 连续输出
```

### time — 时间库（1.5 新增）

```wquick
import:time;

`start
    output:getTime(), "\n";   // 当前日期时间，如 2026-03-18 12:00:00
    output:time(), "\n";      // 时间戳（浮点秒）
    sleep(2);                 // 等待 2 秒
`/
```

| 函数 | 说明 |
|---|---|
| `sleep(t)` | 等待 `t` 秒 |
| `getTime()` | 返回 `"YYYY-MM-DD hh:mm:ss"` 格式字符串 |
| `time()` | 返回当前 Unix 时间戳（浮点数） |

---

## 版本历史

| 版本 | 主要变化 |
|---|---|
| 1.5 | 新增 `time` 标准库（`sleep` / `getTime` / `time()`） |
| 1.4.1 | 词法作用域重构、新增 `break` / `continue` |
| 1.4 | 命名空间、类与对象、集合 |
| 1.3 | 文件操作 |
| 1.2 | 数组、IOplus |

---

## 文件说明

```
wqide.py        图形化 IDE（推荐使用）
wqi.py          命令行解释器
wqc.exe         编译器（源码 → 可执行文件）
TDM-GCC-64/     内置 g++ 编译器（无需另装）
```
