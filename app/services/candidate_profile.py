from __future__ import annotations

CANDIDATE_PROFILE = """
Candidate profile:
- Software testing engineer with about 5 years of testing experience.
- Currently outsourced to bank IT / ICBC-related projects, mainly testing banking business systems.
- Career direction: transition from functional testing and API testing to test development, API automation, server-side testing, SDET, and fintech QA.
- Target role is not Java backend development and not an algorithm role.
- Main technical stack: Python, pytest, requests, YAML, SQL, PostgreSQL, API automation, database assertions, business-flow testing, GitHub Actions, Locust, JMeter, Selenium.
- Java baseline: can read and understand basic Java, but Java backend development is not the main path.

Project anchors:
1. server-api-automation-engineering: Python + pytest + requests + YAML + PostgreSQL + GitHub Actions + Locust. Focus on APIClient, fixtures, YAML data, SQL assertions, CI gate, and UserService business chain: login -> create_user -> get_user -> update_user_status -> db assert.
2. api-test-gen: reads API JSON descriptions and generates pytest + requests code, YAML test data, SQL check placeholders, assertion suggestions, and test-point suggestions.
3. API security test case generator: offline bank-intranet tool for security scenarios, parameter variants, pytest/Java templates, test records, and risk checkpoints covering auth, unauthorized access, over-permission, business security, and response security.
4. SQL test data generator: offline HTML + JS tool converting Excel/CSV to INSERT SQL, with NULL handling, quote escaping, and batch generation.
5. Banking business experience: marketing management, customer profiling, business analytics systems, UI/API/database checks, data permission rules, business-flow validation, regression, and security issue tracking.
""".strip()

CANDIDATE_ANSWER_RULES = """
Candidate-aware answer rules:
1. Do not package the user as a Java backend developer, algorithm engineer, or senior pure developer.
2. For Java backend, JVM, Spring, algorithm, or deep framework questions, give the basic correct answer first, then state the candidate boundary honestly.
3. A strong answer should move back to test-development value: concurrent API testing, load testing, data consistency, debugging, automation framework design, CI, logs, database assertions, and quality risk control.
4. The answer should be honest, speakable, and suitable for a test-development interview.
5. The user is still learning; do not only give abstract ideas. Provide complete answers and concrete examples.
""".strip()

NON_CORE_DEV_KEYWORDS = (
    "java",
    "多线程",
    "thread",
    "runnable",
    "callable",
    "future",
    "executorservice",
    "线程池",
    "jvm",
    "spring",
    "synchronized",
    "volatile",
    "算法",
    "图像算法",
)

TEST_DEV_LANDING_KEYWORDS = (
    "并发测试",
    "压测",
    "接口压测",
    "数据一致性",
    "超卖",
    "重复提交",
    "锁",
    "事务",
    "日志",
    "数据库",
    "自动化框架",
    "pytest",
    "接口",
    "断言",
    "质量保障",
    "问题定位",
    "ci",
)

NON_CORE_DEV_ANSWER_30S = (
    "Java 多线程常见有 Thread、Runnable、Callable/Future 和线程池。"
    "我不是以 Java 后端开发为主线，但测试开发要理解这些概念，"
    "因为并发接口、压测、重复提交、超卖和数据一致性验证都会用到。"
)

NON_CORE_DEV_SUGGESTION = (
    "这类偏开发题建议先答基础概念，再转测试开发应用场景，"
    "补充并发测试、接口压测、数据一致性和问题定位落点。"
)
