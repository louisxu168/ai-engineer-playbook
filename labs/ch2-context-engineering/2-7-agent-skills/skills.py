"""12 个假的 Agent Skill —— 每个分三层，模拟 Agent Skills 的「渐进式披露」结构。

    第 1 层  metadata   一行。**永远在上下文里**
    第 2 层  skill_md   十几行。需要时才加载
    第 3 层  detail     几十行。只有真正要用某个细节时才加载

★ 关键设计：任务要用到的那个具体事实（`pptx` 的 `slide_size` 参数格式），
  **只写在第 3 层里**。第 1、2 层都没有。

  这样三种模式的差别就变成了可判定的：
    - 全量加载 → 能答对，但上下文巨大
    - 只给 metadata → **答不出来**，因为信息根本不在上下文里
    - 渐进式加载 → 能答对，且上下文小
"""

# (name, metadata, skill_md, detail)
SKILLS = [
    ("pptx",
     "生成和编辑 PowerPoint 演示文稿",
     """# pptx —— 演示文稿生成

## 什么时候用
需要产出 .pptx 文件时。支持从 Markdown 大纲生成、套用模板、插入图表。

## 基本流程
1. 用 `outline_to_deck` 把大纲转成初稿
2. 用 `apply_template` 套用设计模板
3. 用 `render_preview` 生成缩略图检查
4. 需要精确控制版式时，参考 detail 文档里的 `slide_size` 说明

## 常见坑
- 中文字体需要显式指定，否则会出方框
- 图片路径必须是绝对路径""",
     """# pptx 细节文档

## slide_size 参数

`slide_size` 必须写成 **"WIDTHxHEIGHT@DPI"** 这种字符串格式，
三部分缺一不可，中间的分隔符分别是小写字母 x 和 @ 符号。

常用取值：
- 16:9 标准     "13.333x7.5@96"
- 4:3 传统      "10x7.5@96"
- A4 横向打印   "11.69x8.27@300"

⚠️ 常见错误：写成 "1920x1080"（那是像素不是英寸）、
   漏掉 @DPI、或者用大写 X 当分隔符 —— 这三种都会被拒绝。

## 模板槽位
apply_template 支持 title / content / image 三种槽位…（略）"""),

    ("xlsx", "读写 Excel 表格、生成透视表",
     "# xlsx\n\n处理 .xlsx 文件。支持读取、写入、公式、透视表。\n\n## 流程\n1. load_workbook\n2. 操作 sheet\n3. save",
     "# xlsx 细节\n\n公式写入时要用 `=` 开头的字符串…（略）"),

    ("pdf", "解析 PDF、提取文本和表格",
     "# pdf\n\n从 PDF 提取内容。支持文本层、OCR、表格识别。",
     "# pdf 细节\n\nOCR 语言包需要单独下载…（略）"),

    ("docx", "生成和编辑 Word 文档",
     "# docx\n\n生成 .docx。支持样式、目录、页眉页脚。",
     "# docx 细节\n\n样式名区分大小写…（略）"),

    ("chart", "生成统计图表并导出为图片",
     "# chart\n\n柱状图、折线图、饼图、散点图。导出 png/svg。",
     "# chart 细节\n\n配色方案可以用预设也可以自定义…（略）"),

    ("sql", "连接数据库并执行查询",
     "# sql\n\n连接常见数据库，执行查询，导出结果。",
     "# sql 细节\n\n连接串格式因数据库而异…（略）"),

    ("email", "起草和发送邮件",
     "# email\n\n起草、格式化、发送邮件。支持附件和抄送。",
     "# email 细节\n\n附件总大小不能超过 25MB…（略）"),

    ("calendar", "查询和创建日历事件",
     "# calendar\n\n读写日历。支持重复事件、提醒、时区。",
     "# calendar 细节\n\n重复规则用 RRULE 语法…（略）"),

    ("image", "图片裁剪、缩放、格式转换",
     "# image\n\n基本图像处理：裁剪、缩放、旋转、格式转换。",
     "# image 细节\n\n缩放时默认用 Lanczos 重采样…（略）"),

    ("audio", "音频剪辑和格式转换",
     "# audio\n\n剪辑、拼接、转码音频文件。",
     "# audio 细节\n\n转码时比特率单位是 kbps…（略）"),

    ("web", "抓取网页并提取结构化内容",
     "# web\n\n抓取网页，提取正文、表格、链接。",
     "# web 细节\n\n遵守 robots.txt，默认限速…（略）"),

    ("translate", "文本翻译与术语表管理",
     "# translate\n\n翻译文本，支持术语表和风格控制。",
     "# translate 细节\n\n术语表用 TSV 格式…（略）"),
]


# ★ 任务需要的那个事实，只存在于 pptx 的 detail 文档里
TARGET_SKILL = "pptx"
CORRECT_FORMAT = "13.333x7.5@96"


def metadata_list():
    """第 1 层：永远在上下文里的那份清单。"""
    lines = []
    for name, meta, _md, _detail in SKILLS:
        lines.append("- " + name + "：" + meta)
    return "\n".join(lines)


def get_skill_md(name):
    for n, _m, md, _d in SKILLS:
        if n == name:
            return md
    return None


def get_detail(name):
    for n, _m, _md, d in SKILLS:
        if n == name:
            return d
    return None


def everything():
    """第 3 种做法：把所有 skill 的所有层全塞进上下文。"""
    parts = []
    for name, meta, md, detail in SKILLS:
        parts.append("===== SKILL: " + name + " =====")
        parts.append(meta)
        parts.append(md)
        parts.append(detail)
    return "\n".join(parts)
