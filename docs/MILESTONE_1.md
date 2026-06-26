# Milestone 1 Acceptance

验收日期：2026-06-27

## 产品理解

OfferForge 是本地优先的 SDET 面试训练 Web 应用。当前阶段围绕知识卡的本地持久化和基础 CRUD 能力搭建底座，不把 `offerforge_scope.md` 中的 Week/Day 内容做成固定课程表。

## V0.1 / Milestone 1 边界

已完成：

- 产品说明与本地优先运行边界。
- Python / FastAPI / SQLite 工程骨架。
- KnowledgeCard / PracticeAttempt 数据模型。
- KnowledgeCard Schema、Repository、Service。
- KnowledgeCard REST CRUD API。
- Swagger / OpenAPI 可操作接口。
- SQLite 初始化、外键、约束、索引和测试隔离。
- 基础自动化测试。

未完成：

- 复习调度。
- 今日任务。
- 完成记录业务流程。
- 错题回炉。
- Python / SQL / XPath 判题。
- PracticeAttempt API。
- 正式前端。
- Markdown 初始化题库或导入。
- 用户账户或鉴权。

## 数据库表设计

`knowledge_cards`

- 存储知识卡主体内容、分类、难度、题型、掌握等级、复习时间、统计计数和 JSON 标签/评分规则。
- 唯一约束：`knowledge_cards(category, title)`。
- 索引：`category`、`difficulty`、`mastery_level`、`next_review_at`、`is_active`。
- Enum 保存公开字符串 value，例如 `python`、`medium`、`new`。

`practice_attempts`

- 存储一次练习记录、评价、答案、反馈和本次计算的下次复习时间。
- `knowledge_card_id` 外键指向 `knowledge_cards.id`，`ondelete="CASCADE"`。

时间策略：

- 数据库存储 UTC naive datetime。
- 代码通过 `datetime.now(timezone.utc).replace(tzinfo=None)` 生成时间。

## API 设计

统一前缀：`/api/v1`

- `GET /health`
- `POST /cards`
- `GET /cards`
- `GET /cards/{card_id}`
- `PATCH /cards/{card_id}`
- `DELETE /cards/{card_id}`

HTTP 映射：

- 找不到知识卡：`404`
- 同分类标题重复：`409`
- 请求体、路径和查询参数错误：`422`
- 删除成功：`204`，无响应体

## 分层架构

```text
Router -> Service -> Repository -> SQLAlchemy Model
```

- Router 只处理 HTTP、依赖注入和业务异常到 HTTP 状态码的映射。
- Service 处理存在性、重复标题、分页边界和明确唯一约束冲突转换。
- Repository 封装 SQLAlchemy 查询和事务。
- Model 只定义数据库结构和 ORM 关系。
- Schema 与 ORM Model 分离。

## 已完成内容证明

- 产品说明：`offerforge_scope.md`、`README.md`
- 应用入口：`app/main.py`
- API router：`app/api/router.py`、`app/api/knowledge_cards.py`
- 数据库：`app/db/base.py`、`app/db/session.py`、`app/db/init_db.py`
- 模型：`app/models/knowledge_card.py`、`app/models/practice_attempt.py`
- Schema：`app/schemas/knowledge_card.py`、`app/schemas/practice_attempt.py`
- Repository：`app/repositories/knowledge_card.py`
- Service：`app/services/knowledge_card.py`、`app/services/exceptions.py`
- 测试：`tests/`

## 验收标准

- 应用可启动。
- `/docs` 可打开。
- KnowledgeCard CRUD 可通过 REST API 操作。
- SQLite 数据重启后仍可读取。
- 自动化测试全部通过且无 warning。
- 局域网监听命令可启动。
- 运行时数据库、缓存和虚拟环境不提交到 Git。

## 实际验收结果

- `python -m compileall app tests` 通过。
- `python -m pytest -q`：`93 passed in 5.66s`。
- `python -m pytest -W error`：`93 passed in 5.39s`。
- `GET /api/v1/health`：`200`。
- `GET /docs`：`200`。
- `GET /openapi.json`：`200`。
- OpenAPI 包含所有 Milestone 1 API path。
- SQLite 重启持久化验收通过。
- API 边界场景验收通过。
- `0.0.0.0:8000` 局域网监听启动通过。
