# OfferForge

OfferForge 是一个本地优先的 Web 应用，用于把 Python、SQL、API/pytest、UI 自动化、项目与面试输出等高频能力做成长期可调用的复习与训练工具。产品范围来自 `offerforge_scope.md`，但不会设计成固定按 Day 1、Day 2 推进的课程表。

## 当前完成范围

- Python 3.11+ 项目基础结构。
- FastAPI 最小应用骨架。
- `/api/v1/health` 健康检查接口。
- SQLAlchemy 2.x SQLite 连接、SessionLocal、`get_db` 依赖、外键开启和初始化函数。
- KnowledgeCard / PracticeAttempt 数据模型。
- KnowledgeCard Pydantic Schema、Repository、Service。
- KnowledgeCard REST CRUD API，可通过 Swagger / OpenAPI 创建、查询、筛选、修改和删除知识卡。
- HTTP Basic Auth 最小访问保护，可通过环境变量启用。
- 默认本机访问配置，以及按启动命令选择局域网监听。
- pytest 基础测试，测试数据库使用临时 SQLite 文件。

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- SQLite
- pytest
- httpx

## 项目目录

```text
app/        FastAPI 应用、API、配置、数据库、模型、Schema、Repository、Service
tests/      自动化测试
data/       本地 SQLite 数据目录
docs/       项目文档和验收记录
scripts/    后续脚本预留目录
```

## 当前未完成范围

- 未实现复习调度算法。
- 未实现今日任务、判题器和评分器。
- 未实现正式业务前端或手机业务页面。
- 未实现 Markdown 初始化题库或 Markdown 导入。
- 未实现 PracticeAttempt API。
- 未实现账户系统、云同步、公网部署、PWA、Tailscale、内网穿透、Docker、Redis、Celery 或消息队列。
- 未实现公网远程访问。

## Windows 本地开发

创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

后续开发优先使用项目根目录下的 `.venv`，不要把 `.venv` 提交到 Git。

如果 PowerShell 阻止执行激活脚本，可以只对当前终端临时允许脚本执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

仅当前电脑访问：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`127.0.0.1` 只允许当前电脑访问，这是默认推荐的开发方式。

本地开发默认关闭 Basic Auth，方便快速调试和运行测试。

启动后访问：

```text
http://127.0.0.1:8000/docs
```

当前 `/docs` 可以操作 KnowledgeCard CRUD API。

开启 Basic Auth：

```powershell
$env:OFFERFORGE_AUTH_ENABLED="true"
$env:OFFERFORGE_AUTH_USERNAME="offerforge"
$env:OFFERFORGE_AUTH_PASSWORD="请换成你自己的强密码"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果 `OFFERFORGE_AUTH_ENABLED=true`，但没有设置用户名或密码，应用会拒绝启动。云端部署必须开启 Basic Auth。

开启后，`/docs`、`/openapi.json` 和业务 API 需要认证；`/api/v1/health` 保持开放，便于健康检查。

同一 Wi-Fi 下允许手机访问：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`0.0.0.0` 只是服务监听地址，手机不能访问 `http://0.0.0.0:8000`。手机必须访问电脑在当前局域网中的实际 IPv4 地址。

查询 Windows 电脑局域网 IPv4 地址：

```powershell
ipconfig
```

找到当前 Wi-Fi 或以太网适配器的 IPv4 地址，例如：

```text
192.168.1.8
```

手机和电脑连接同一个 Wi-Fi 后，在手机浏览器访问：

```text
http://192.168.1.8:8000
```

API 文档地址：

```text
http://192.168.1.8:8000/docs
```

电脑上的 OfferForge 服务必须保持运行。第一次监听局域网地址时，Windows 防火墙可能弹出授权提示，需要允许 Python 在当前可信私人网络中通信。

## 数据保存位置

正式运行时 SQLite 数据库默认保存到：

```text
data/offerforge.db
```

该文件是本地运行数据，不提交到 Git。测试会使用临时 SQLite 数据库，不写入正式数据库。

## Deployment

本项目支持本地运行和私人云端部署。云端部署前必须配置 Basic Auth，并把 SQLite 数据库放到持久化磁盘或 volume。

手机复习页面路径：`/app`。

详细部署说明见 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

Cloud MVP smoke test record: [`docs/CLOUD_SMOKE_TEST.md`](docs/CLOUD_SMOKE_TEST.md)。

## 安全说明

HTTP Basic Auth 只是私人 MVP 的最小保护，不是完整账号系统。不要把密码写进代码，不要提交 `.env`，不要公开分享访问地址和密码。当前没有多用户账号、注册、登录会话或权限管理。

本地开发默认关闭 Basic Auth；云端部署必须设置 `OFFERFORGE_AUTH_ENABLED=true`、`OFFERFORGE_AUTH_USERNAME` 和 `OFFERFORGE_AUTH_PASSWORD`。

只建议在可信的家庭、私人局域网或受保护的私人云端环境中使用。不要在公共 Wi-Fi 中开放，不要在路由器中设置公网端口映射，也不要把未开启认证的服务暴露到公网。

项目当前不需要 CORS 配置：手机端和电脑端都会通过同一个 FastAPI 服务访问。

## 测试

```powershell
python -m compileall app tests
python -m pytest -q
```

测试会覆盖临时 SQLite 数据库路径，不会写入默认正式数据库 `data/offerforge.db`。

## API

本机启动后访问：

```text
http://127.0.0.1:8000/docs
```

当前提供：

- `GET /api/v1/health`
- `POST /api/v1/cards`
- `POST /api/v1/cards/bulk`
- `GET /api/v1/cards`
- `GET /api/v1/cards/{card_id}`
- `PATCH /api/v1/cards/{card_id}`
- `DELETE /api/v1/cards/{card_id}`

Bulk card import is available through `POST /api/v1/cards/bulk` with a JSON array body.

## Today done review

`GET /api/v1/reviews/done-today` returns cards practiced during the current UTC day. The `/app` page shows today's practiced cards after submission so the question and reference answer can be reviewed again. This is a same-day review aid and does not change scheduling rules.

## Seed cards

Week one interview seed cards are available at `data_seed/cards_seed_week1_interview_v3.json`.
The file contains 95 cards for interview replay, resume projects, debugging, UI automation, Python coding, SQL, Linux, and HR practice. It is designed for import through `POST /api/v1/cards/bulk` and does not contain sensitive information.

## Auto seed restore

On startup, OfferForge can auto-import `data_seed/cards_seed_week1_interview_v3.json` when the knowledge card table is empty. This helps restore the 95-card seed set after a Render free-environment redeploy or restart clears SQLite data. Existing cards are never duplicated, and this only restores knowledge cards, not practice attempts or today-done records. Set `OFFERFORGE_AUTO_SEED_ON_STARTUP=false` to disable it, or override the file with `OFFERFORGE_AUTO_SEED_PATH`.

## 移动端兼容预留原则

后续正式业务前端使用原生 HTML、CSS、JavaScript。页面采用 mobile-first 或响应式设计，支持常见手机浏览器，按钮和输入区域适合触屏操作，不依赖 hover 才能完成关键操作，不固定桌面端宽度。

今日任务、答题和复习页面需要适合单手浏览。手机端与电脑端调用同一套 FastAPI API。本轮不会创建虚假的完整手机页面。
