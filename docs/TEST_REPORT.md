# Test Report

验收日期：2026-06-27

## 环境版本

- Python 3.12.7
- FastAPI 0.138.1
- SQLAlchemy 2.0.51
- Pydantic 2.13.4
- Uvicorn 0.49.0
- pytest 8.4.2
- httpx 0.28.1

## 自动化测试

执行命令：

```powershell
python -m compileall app tests
python -m pytest -q
python -m pytest -W error
```

结果：

- `compileall` 通过。
- `python -m pytest -q`：`93 passed in 5.53s`。
- `python -m pytest -W error`：`93 passed in 5.39s`。
- 未使用 warning 全局过滤器。
- `data/offerforge.db` 在测试前后文件大小和 mtime 未变化，测试未污染正式数据库。

## 数据库结构验收

确认结果：

- 正式数据库路径：`data/offerforge.db`。
- 初始化后存在表：`knowledge_cards`、`practice_attempts`。
- 唯一约束：`uq_knowledge_cards_category_title`，字段为 `category`、`title`。
- 索引：`ix_knowledge_cards_category`、`ix_knowledge_cards_difficulty`、`ix_knowledge_cards_is_active`、`ix_knowledge_cards_mastery_level`、`ix_knowledge_cards_next_review_at`。
- `practice_attempts.knowledge_card_id` 外键指向 `knowledge_cards.id`，`ondelete=CASCADE`。
- `PRAGMA foreign_keys` 返回 `1`。
- Enum 底层保存公开字符串 value：`python`、`medium`、`new`。
- JSON 字段可保存和读取。
- 级联删除验证通过，删除知识卡后关联练习记录为 `0`。

## 真实启动结果

启动命令：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

结果：

- `GET /api/v1/health`：`200`
- `GET /docs`：`200`
- `GET /openapi.json`：`200`
- OpenAPI 中存在：
  - `POST /api/v1/cards`
  - `GET /api/v1/cards`
  - `GET /api/v1/cards/{card_id}`
  - `PATCH /api/v1/cards/{card_id}`
  - `DELETE /api/v1/cards/{card_id}`
  - `GET /api/v1/health`
- OpenAPI schema 中可以看到枚举、请求体和响应模型。

## CRUD 与持久化验收

使用验收卡：

- title：`Milestone 1 持久化验收卡`
- category：`python`

结果：

- POST 创建成功，返回 id。
- 停止并重新启动 Uvicorn 后，使用相同 id GET 成功。
- PATCH 修改标题和 core_knowledge 成功。
- 再次 GET 确认修改持久化。
- DELETE 返回 `204`。
- 删除后 GET 返回 `404`。
- 验收数据已删除，未残留 `Milestone 1` / `Milestone1` 验收卡。

## API 边界验收

确认结果：

- 同分类同标题重复创建：`409`
- 不同分类同标题：允许创建
- 不存在卡片：`404`
- 空标题：`422`
- 非法 category：`422`
- `offset < 0`：`422`
- `limit = 0`：`422`
- `limit > 100`：`422`
- DELETE 成功：`204` 且 body 长度为 `0`
- keyword 匹配标题：通过
- keyword 匹配题目：通过
- `total` 不受分页影响：通过

## 局域网监听验收

启动命令：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

结果：

- 服务监听启动成功。
- 本机 health 验证：`200`。
- 当前 WLAN IPv4：`172.20.10.2`。
- 手机访问格式：`http://172.20.10.2:8000/docs`。

说明：

- Codex 只验证了服务监听，不能替用户确认真实手机浏览器已连接。
- 手机和电脑必须在同一 Wi-Fi 或局域网。
- 手机访问电脑 IPv4 地址，不能访问 `0.0.0.0`。
- Windows 防火墙需要允许 Python 在私人网络通信。
- 当前没有鉴权，只建议在可信私人局域网使用。

## Git 验收

提交历史包含：

- `chore: initialize OfferForge local web application`
- `feat: add knowledge card domain models`
- `feat: add knowledge card schemas`
- `feat: add knowledge card repository`
- `feat: add knowledge card service`
- `feat: add knowledge card CRUD API`

未提交：

- `data/offerforge.db`
- `.venv`
- `__pycache__`
- `.pytest_cache`
- 临时验收文件
- 其他运行时数据库

本轮验收前 `data/offerforge.db` 不存在；真实启动和持久化验收过程中创建了该运行时数据库。验收数据删除后，运行时数据库文件也已清理，避免把本轮运行产物留在工作区。

## 已知限制

- 尚未实现复习调度、今日任务、PracticeAttempt API、判题器、正式前端、Markdown 初始化题库和账户鉴权。
- 当前服务只建议在可信私人局域网使用。
- 当前没有公网部署、云同步、内网穿透或端口映射配置。
