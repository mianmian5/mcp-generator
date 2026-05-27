# MCP Generator

> 输入 OpenAPI spec 或数据库连接 → 自动生成可直接运行的 MCP Server。将数百行重复代码压缩为一行命令。

---

## 第一部分：为什么需要 MCP

### 1.1 大语言模型的边界

大语言模型（LLM）本质上是纯计算引擎——它们接收文本，预测下一个 token。这种设计意味着它们无法主动感知或影响外部世界：

- 无法查询实时数据（数据库、API、文件系统）
- 无法执行操作（发送请求、写入文件、调用服务）
- 无法获取训练截止日期之后的信息

**要让 LLM 从"聊天机器人"变成"能干活的生产力工具"，必须为其提供与外部系统交互的能力。**

### 1.2 工具调用（Tool Use）的演进

业界解决这个问题的路径经历了两个阶段。

**第一阶段：各厂商的 Function Calling**

OpenAI、Anthropic、Google 等平台各自定义了函数调用格式。工作流程如下：

```
用户输入 → LLM 判断需要调用哪个函数 → 返回函数名和参数 →
应用程序执行函数 → 将结果回传 LLM → LLM 生成最终回复
```

这个方案的问题在于**厂商锁定**——为 OpenAI 格式编写的工具定义无法在 Anthropic 的平台使用，反之亦然。开发者不得不为一个工具维护多套接口定义，生态碎片化严重。

**第二阶段：MCP（Model Context Protocol）**

MCP 是 2024 年底提出的**开放协议标准**，类比为工具调用领域的 HTTP 或 USB-C：

| 对比维度 | Function Calling | MCP |
|---------|------------------|-----|
| 协议性质 | 各厂商私有格式 | 开放标准，与厂商无关 |
| 工具复用性 | 一个平台一套定义 | 一次编写，所有 MCP 客户端通用 |
| 生态 | 割裂 | 统一的工具市场、共享的 server 实现 |
| 传输层 | 耦合在 API 请求中 | 独立进程，stdio / HTTP 通信 |

MCP 定义了三个核心概念：
- **Tool**：可调用的函数，包含名称、描述、JSON Schema 参数定义
- **Resource**：暴露给 LLM 的只读数据（文件、数据库记录等）
- **Transport**：通信方式——stdio（子进程标准输入输出）或 HTTP（Streamable HTTP）

```
┌──────────────────┐                        ┌──────────────────┐
│   MCP 客户端      │   ── MCP 协议 ──→      │   MCP Server      │
│ (AI 应用/IDE/终端) │   ←── stdio/HTTP ──   │ (工具提供方)       │
└──────────────────┘                        └────────┬─────────┘
                                                     │
                                            ┌────────┴─────────┐
                                            │ 你的 API / 数据库  │
                                            └──────────────────┘
```

MCP Server 是一个独立运行的进程，负责将后端服务的能力翻译为 MCP 标准格式的 Tool 定义。任何支持 MCP 的客户端都可以直接连接它，无需关心后端是什么。

### 1.3 现状：写 MCP Server 是纯体力活

MCP 解决了协议标准化的问题，但**没有解决实现成本的问题**。

给一个 REST API 编写 MCP Server，本质上是一个机械翻译过程：

```
OpenAPI 端点                          MCP Tool 函数
─────────────────────────────────     ───────────────────────────
GET  /pets?limit={n}                  async def listpets(limit: int)
POST /pets          {body}            async def createpet(body: dict)
GET  /pets/{id}                       async def getpet(id: str)
DELETE /pets/{id}                     async def deletepet(id: str)
POST /pets/search   {body}            async def searchpets(body: dict)
```

每个端点的处理逻辑完全一致：
1. `@server.tool()` 装饰器注册
2. 从 OpenAPI parameters 定义映射为 Python 函数签名（类型 + 默认值）
3. 拼接 URL：`f"{BASE_URL}/pets/{petId}"`
4. 组装 query params（过滤空值）
5. 组装 request body（JSON）
6. 注入认证 header（Bearer token / API key）
7. 发送 HTTP 请求 → 解析 JSON → 封装为 MCP `TextContent` 返回

**50 个端点 = 50 段仅变量名不同的相同代码。** 这是典型的、应该被自动化消灭的重复劳动。

给数据库写 MCP Server 同理——每张表都需要 `describe_*`、`sample_*` 等函数，结构完全模板化。

**这就是 MCP Generator 解决的问题。**

---

## 第二部分：MCP Generator 是什么

### 2.1 核心定位

MCP Generator 是一个**代码生成工具**，读取已有的接口描述文件或数据库 schema，自动生成一个功能完整、可直接运行的 MCP Server。

```
输入                           处理                          输出
────                        ──────                         ────
OpenAPI 3.x / Swagger 2.0   parse_openapi()   →   独立的 .py 文件
(JSON / YAML)                    ↓                  (MCP Server)
                             结构化 Tool 列表
SQLite / PostgreSQL / MySQL  parse_database()  →   独立的 .py 文件
连接字符串                        ↓                  (MCP Server)
                             结构化 Table 列表
```

### 2.2 两种生成模式

**模式一：API → MCP Server**

| 能力 | 说明 |
|------|------|
| 输入格式 | OpenAPI 3.x / Swagger 2.0（JSON + YAML） |
| HTTP 方法 | GET、POST、PUT、DELETE、PATCH、OPTIONS、HEAD |
| 参数处理 | Path params（路径变量）、Query params（查询字符串）、Request body（JSON） |
| 认证 | 自动生成 Bearer token 认证（通过环境变量注入） |
| Schema 解析 | `$ref` 引用自动展开，嵌套 schema 正确映射 |
| 类型映射 | `string→str`, `integer→int`, `number→float`, `boolean→bool`, `array→list`, `object→dict` |

生成的 server 为一个 .py 文件，运行时依赖仅 `mcp` + `httpx`，不依赖本项目。

每个 API 端点生成的 Tool 函数示例（自动化产出，无需手写）：

```python
@server.tool()
async def getpet(petId: str) -> list[TextContent]:
    """Get a pet by ID"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/pets/{petId}",
            headers=_headers()
        )
        response.raise_for_status()
        data = response.json()
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
```

**模式二：数据库 → MCP Server**

| 能力 | 说明 |
|------|------|
| 数据库支持 | SQLite、PostgreSQL、MySQL |
| 自动扫描 | 遍历所有用户表，提取列名、类型、是否可空、主键、行数 |
| 表级工具 | 每张表自动生成 `describe_<table>()` 和 `sample_<table>(n)` |
| 通用工具 | `list_tables()` 列出全部表及行数；`run_query(sql)` 执行自定义 SQL |
| 安全策略 | run_query 内置白名单校验，仅允许 SELECT / EXPLAIN / PRAGMA / SHOW / DESCRIBE |

生成的 server 运行时依赖仅 `mcp` + 对应数据库驱动（`sqlite3` 内置 / `psycopg2` / `pymysql`），不依赖本项目。

```text
list_tables()         → 所有表名及行数概览
describe_users()      → users 表的列定义（名称、类型、约束）
sample_users(n)       → users 表 n 条样本数据（上限 100）
describe_orders()     → orders 表的列定义
sample_orders(n)      → orders 表样本数据
run_query(sql)        → 执行只读 SQL 查询
```

### 2.3 生成的代码如何使用

生成的 .py 文件是一个标准的 MCP stdio server。在任何 MCP 客户端中配置即可连接。以常用客户端的 `.mcp.json` 配置为例：

```json
{
  "mcpServers": {
    "petstore": {
      "command": "python",
      "args": ["petstore_mcp_server.py"],
      "env": {
        "PETSTORE_API_BASE_URL": "https://api.petstore.example.com/v1",
        "PETSTORE_API_API_KEY": "your-api-key"
      }
    }
  }
}
```

配置完成后，在支持 MCP 的 AI 应用中直接对话即可——AI 会自动识别并调用已注册的 tools。

---

## 第三部分：使用

### 安装

```bash
pip install mcp-generator
```

### API → MCP

```bash
mcp-gen generate petstore.yaml -o petstore_mcp.py

# 输出：
# Parsing OpenAPI spec: petstore.yaml
# Found 5 API endpoints
#   GET    /pets          -> listpets()
#   POST   /pets          -> createpet()
#   GET    /pets/{petId}  -> getpet()
#   DELETE /pets/{petId}  -> deletepet()
#   POST   /pets/search   -> searchpets()
# Generated MCP server: petstore_mcp.py
```

### 数据库 → MCP

```bash
mcp-gen from-db sqlite:///app.db -o db_mcp.py

# 输出：
# Connecting to database: sqlite:///app.db
# Found 3 tables:
#   users (1024 rows) [id, name, email]
#   orders (5812 rows) [id, user_id, amount, status]
#   products (256 rows) [id, name, price, stock]
# Generated MCP server: db_mcp.py
```

### CLI 参考

```bash
mcp-gen generate <spec>        # 从 OpenAPI 文件生成
mcp-gen generate <spec> -o O   # 指定输出路径
mcp-gen generate <spec> -n N   # 自定义 server 名称
mcp-gen from-db <url>          # 从数据库生成
mcp-gen from-db <url> -o O     # 指定输出路径
```

支持的数据库连接格式：
```
sqlite:///path/to/file.db
postgresql://user:pass@localhost:5432/dbname
mysql://user:pass@localhost:3306/dbname
```

---

## 第四部分：技术架构

### 项目结构

```
mcp-generator/
│
├── src/
│   ├── parser/
│   │   ├── openapi_parser.py    # OpenAPI spec → 结构化 Tool 列表
│   │   │                       #   $ref 展开、参数/body/response 提取
│   │   └── db_parser.py         # 数据库 schema → 结构化 Table 列表
│   │                           #   SQLite / PostgreSQL / MySQL 适配
│   │
│   ├── generator/
│   │   └── mcp_generator.py     # 结构化数据 + Jinja2 模板 → .py 代码
│   │                           #   类型映射、签名构建、参数拼接预计算
│   │
│   └── cli/
│       └── main.py             # Click CLI 入口
│
├── templates/                   # Jinja2 模板
│   ├── mcp_server_python.py.j2      # API 模式模板
│   └── mcp_server_db_python.py.j2   # 数据库模式模板
│
├── examples/
│   └── petstore_mcp_server.py   # 示例输出
│
├── tests/
│   ├── fixtures/petstore.yaml
│   ├── test_openapi_parser.py
│   ├── test_db_parser.py
│   └── test_mcp_generator.py
│
└── pyproject.toml
```

### 数据流

```
输入: OpenAPI Spec (petstore.yaml)
    │
    ▼
┌──────────────────────────┐
│ parse_openapi(path)      │  ← prance 解析 + JSON $ref 展开
│                          │  ← 遍历 /paths 下所有 HTTP method
│ 返回: dict               │  ← 提取 parameters / requestBody / responses
│   .title   = "Petstore"  │
│   .base_url = "..."      │
│   .tools   = [           │
│     {name, method, path, │
│      params, body, ...}  │
│   ]                      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ generate_from_openapi(d) │  ← _prepare_openapi_tool() 逐 tool 预计算
│                          │     - openapi type → Python type
│  Jinja2 模板渲染         │     - 生成默认值
│                          │     - 构建 URL / params / body 行
│ 返回: str (Python 源码)  │
└──────────┬───────────────┘
           │
           ▼
   输出: *_mcp_server.py    ← 可直接 python 执行
                             仅依赖 mcp + httpx（或 db driver）
                             不依赖本项目
```

数据库路径流程相同： `parse_database(url) → generate_from_database(dict) → .py`

### 设计原则

1. **Parser / Generator 分离** — Parser 产出纯数据 dict，Generator 消费 dict + 模板。二者无耦合，可独立测试、独立演进
2. **模板化** — 用 Jinja2 而非字符串拼接，模板即文档，代码结构一目了然
3. **输出零依赖本项目** — 生成的文件仅依赖业界标准包（`mcp`、`httpx`、数据库驱动），可独立分发
4. **CLI 优先** — 单命令完成，无 GUI 依赖，适合 CI/CD 流水线集成
5. **生成代码可读** — 不混淆、不压缩、保留合理空行和注释，生成即最终形态

---

## 第五部分：开发

```bash
git clone <repo-url>
cd mcp-generator
pip install -e .
pip install pytest
python -m pytest tests/ -v
```
