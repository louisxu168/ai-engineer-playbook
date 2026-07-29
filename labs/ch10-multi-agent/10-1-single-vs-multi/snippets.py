"""实验 10-1 的素材：24 段待审查的代码片段。

其中**恰好 8 段有安全问题**，分布在 4 个类别里，每类 2 段：

    SQLI    SQL 注入
    SECRET  硬编码密钥
    PATH    路径穿越
    INPUT   未校验的外部输入

每一类里都有**一段明显、一段隐蔽**——这是故意的。
只找得到明显的那 4 段，和 8 段全找到，是完全不同的能力。

★ 因为标准答案是我定的，这个实验能**机械判分**：
  召回率 = 找到的 / 8，误报 = 报了但其实没问题的。
  不需要模型判分，不需要关键词匹配。
"""

# (id, 代码, 有没有问题, 类别, 难度)
SNIPPETS = [
    ("S01",
     'def get_user(uid):\n'
     '    return db.query("SELECT * FROM users WHERE id = " + uid)',
     True, "SQLI", "明显"),

    ("S02",
     'def list_orders(user_id):\n'
     '    return db.query("SELECT * FROM orders WHERE user_id = %s", (user_id,))',
     False, None, None),

    ("S03",
     'API_KEY = "sk-live-3f9a2b7c8d1e4f6a"\n'
     'client = PaymentClient(API_KEY)',
     True, "SECRET", "明显"),

    ("S04",
     'API_KEY = os.environ["PAYMENT_API_KEY"]\n'
     'client = PaymentClient(API_KEY)',
     False, None, None),

    ("S05",
     'def read_file(name):\n'
     '    return open("/var/data/" + name).read()',
     True, "PATH", "明显"),

    ("S06",
     'def read_file(name):\n'
     '    safe = os.path.basename(name)\n'
     '    return open(os.path.join("/var/data", safe)).read()',
     False, None, None),

    ("S07",
     'age = int(request.args["age"])\n'
     'if age > 18:\n'
     '    grant_access()',
     True, "INPUT", "明显"),

    ("S08",
     'raw = request.args.get("age", "")\n'
     'if raw.isdigit() and int(raw) > 18:\n'
     '    grant_access()',
     False, None, None),

    ("S09",
     'def search(term):\n'
     '    sql = f"SELECT * FROM items WHERE name LIKE \'%{term}%\'"\n'
     '    return db.query(sql)',
     True, "SQLI", "隐蔽"),

    ("S10",
     'def search(term):\n'
     '    return db.query("SELECT * FROM items WHERE name LIKE %s", ("%" + term + "%",))',
     False, None, None),

    ("S11",
     '# 测试环境用的，上线前记得删\n'
     'DEFAULT_ADMIN_TOKEN = "admin-8f2e1d9c"\n'
     'def auth(token=DEFAULT_ADMIN_TOKEN):\n'
     '    return verify(token)',
     True, "SECRET", "隐蔽"),

    ("S12",
     'def auth(token=None):\n'
     '    if token is None:\n'
     '        raise ValueError("token required")\n'
     '    return verify(token)',
     False, None, None),

    ("S13",
     'def export(path):\n'
     '    target = os.path.realpath(os.path.join(EXPORT_DIR, path))\n'
     '    if os.path.commonpath([target, EXPORT_DIR]) != EXPORT_DIR:\n'
     '        raise ValueError("bad path")\n'
     '    return open(target, "w")',
     False, None, None),

    ("S14",
     'def download(name):\n'
     '    target = os.path.normpath(os.path.join(BASE, name))\n'
     '    return send_file(target)',
     True, "PATH", "隐蔽"),

    ("S15",
     'payload = json.loads(request.data)\n'
     'db.update(payload["table"], payload["values"])',
     True, "INPUT", "隐蔽"),

    ("S16",
     'payload = json.loads(request.data)\n'
     'if payload.get("table") not in ALLOWED_TABLES:\n'
     '    abort(400)\n'
     'db.update(payload["table"], payload["values"])',
     False, None, None),

    ("S17",
     'def total(items):\n'
     '    return sum(one.price * one.qty for one in items)',
     False, None, None),

    ("S18",
     'logger.info("user %s logged in", user.id)',
     False, None, None),

    ("S19",
     'def retry(fn, times=3):\n'
     '    for _ in range(times):\n'
     '        try:\n'
     '            return fn()\n'
     '        except TransientError:\n'
     '            continue\n'
     '    raise',
     False, None, None),

    ("S20",
     'cache = {}\n'
     'def get_config(key):\n'
     '    if key not in cache:\n'
     '        cache[key] = load_config(key)\n'
     '    return cache[key]',
     False, None, None),

    ("S21",
     'def slugify(title):\n'
     '    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")',
     False, None, None),

    ("S22",
     'def send_report(to):\n'
     '    body = render_template("report.html", data=fetch())\n'
     '    mailer.send(to, body)',
     False, None, None),

    ("S23",
     'def parse_dates(rows):\n'
     '    return [datetime.strptime(r["d"], "%Y-%m-%d") for r in rows]',
     False, None, None),

    ("S24",
     'def healthcheck():\n'
     '    return {"status": "ok", "version": VERSION}',
     False, None, None),
]


# 标准答案：有问题的那 8 段
GROUND_TRUTH = [s[0] for s in SNIPPETS if s[2]]

# 按类别分组（specialists 模式要用）
CATEGORIES = {
    "SQLI": "SQL 注入：把外部输入拼进 SQL 字符串，而不是用参数化查询",
    "SECRET": "硬编码密钥：把 API key、token、密码直接写在代码里",
    "PATH": "路径穿越：用外部输入拼文件路径，没有限制在允许的目录内",
    "INPUT": "未校验输入：直接使用外部传入的值，没有校验类型/范围/白名单",
}

CATEGORIES_EN = {
    "SQLI": "SQL injection: external input concatenated into SQL instead of using parameters",
    "SECRET": "Hardcoded secret: an API key, token or password written directly in the source",
    "PATH": "Path traversal: a file path built from external input without confining it to an allowed directory",
    "INPUT": "Unvalidated input: an externally supplied value used directly, with no type/range/allowlist check",
}


def render_snippets(subset=None):
    """把片段渲染成给模型看的文本。subset 是要包含的 id 列表，None 表示全部。"""
    lines = []
    for snippet_id, code, _bad, _cat, _diff in SNIPPETS:
        if subset is not None and snippet_id not in subset:
            continue
        lines.append("--- " + snippet_id + " ---")
        lines.append(code)
        lines.append("")
    return "\n".join(lines)


def all_ids():
    return [s[0] for s in SNIPPETS]
