"""内置与导入的发布、日志和指标记录，通过同一套 SQLite 只读查询访问。"""

import sqlite3
from contextlib import closing, contextmanager
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

TOOLS = {
    "releases": ("查发布变更", "读取版本、变更项和变更前后的配置。"),
    "logs": ("查错误日志", "读取应用报错和请求采样。"),
    "metrics": ("查服务指标", "对比告警前后的错误率、耗时和业务指标。"),
}

UPLOAD_SCENARIO = "upload"
ClockTime = Annotated[str, Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]
SIGNALS = {
    "payment_timeout_ms": ("releases", "previous", "current"),
    "payment_timeout": ("logs", "current"),
    "payment_p95_ms": ("metrics", "previous", "current"),
    "checkout_error_pct": ("metrics", "previous", "current"),
    "db_pool_max": ("releases", "previous", "current"),
    "db_pool_in_use": ("metrics", "current"),
    "pool_checkout_timeout": ("logs",),
    "inventory_error": ("logs",),
}


class QueryWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: ClockTime = "00:00"
    end: ClockTime = "23:59"

    @model_validator(mode="after")
    def check_order(self):
        if self.start > self.end:
            raise ValueError("起始时刻不能晚于结束时刻。")
        return self


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
    source: Literal["releases", "logs", "metrics"]
    at: ClockTime
    signal: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    previous: Annotated[FiniteFloat, Field(ge=0)] | None = None
    current: Annotated[FiniteFloat, Field(ge=0)] | None = None
    description: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def check_signal(self):
        specification = SIGNALS.get(self.signal)
        if specification and (
            self.source != specification[0]
            or any(getattr(self, field) is None for field in specification[1:])
        ):
            raise ValueError("已知信号必须来自规定来源，并提供要求的数值。")
        if self.signal == "checkout_error_pct" and max(self.previous, self.current) > 100:
            raise ValueError("结算错误率须在 0 至 100 之间。")
        return self


SCENARIOS = {
    "case-01": ("演示 01 · 结算接口报警", "发布后结算接口错误率从 1% 涨到 18%，帮我查一下原因。"),
    "case-02": ("演示 02 · 支付请求积压", "支付一直等待，刚好发过版，是这次变更引起的吗？"),
    "case-03": ("演示 03 · 下单返回 503", "下单接口频繁返回 503，请定位故障。"),
    "case-04": ("演示 04 · 告警数据缺失", "结算告警出现了，但监控还有部分数据没到。"),
    "case-05": ("演示 05 · 超时阈值边界", "结算有少量超时，看看是否与新阈值有关。"),
    "case-06": ("演示 06 · 库存错误但下单正常", "日志出现库存服务异常，请核对结算是否受影响。"),
}

# 每条记录依次为：编号、来源、UTC 时间、信号、前值、后值、观测说明。
RECORDS = {
    "case-01": [
        ("R-11", "releases", "10:00", "payment_timeout_ms", 2000, 200, "checkout v1.7.3 将支付请求超时从 2000 毫秒改为 200 毫秒。"),
        ("L-11", "logs", "10:03", "payment_timeout", None, 200, "结算请求支付时达到 200 毫秒等待上限。"),
        ("M-11", "metrics", "10:06", "payment_p95_ms", 440, 450, "支付服务 P95 响应耗时从 440 毫秒变为 450 毫秒。"),
        ("M-12", "metrics", "10:06", "checkout_error_pct", 1, 18, "结算错误率从 1% 升至 18%。"),
    ],
    "case-02": [
        ("R-21", "releases", "10:00", "payment_timeout_ms", 1200, 1200, "此次发布更新了结算页文案，支付超时仍是 1200 毫秒。"),
        ("L-21", "logs", "10:05", "payment_timeout", None, 1200, "结算等待支付响应超过 1200 毫秒。"),
        ("M-21", "metrics", "10:06", "payment_p95_ms", 390, 1720, "支付服务 P95 响应耗时从 390 毫秒升到 1720 毫秒。"),
        ("M-22", "metrics", "10:06", "checkout_error_pct", 1, 12, "结算错误率从 1% 升到 12%。"),
    ],
    "case-03": [
        ("R-31", "releases", "10:00", "db_pool_max", 40, 8, "checkout v1.8.1 将数据库连接池上限从 40 改成 8。"),
        ("L-31", "logs", "10:02", "pool_checkout_timeout", None, None, "下单请求等待数据库连接超时，返回 503。"),
        ("M-31", "metrics", "10:05", "db_pool_in_use", 19, 8, "发版后 8 个可用连接全部被占用。"),
        ("M-32", "metrics", "10:05", "checkout_error_pct", 1, 21, "下单错误率从 1% 升至 21%。"),
    ],
    "case-04": [
        ("R-41", "releases", "10:00", "payment_timeout_ms", 2000, 250, "发布将支付超时改为 250 毫秒。"),
        ("M-41", "metrics", "10:05", "checkout_error_pct", 1, 8, "结算错误率从 1% 升至 8%，支付耗时样本缺失。"),
    ],
    "case-05": [
        ("R-51", "releases", "10:00", "payment_timeout_ms", 1500, 500, "支付超时从 1500 毫秒改为 500 毫秒。"),
        ("L-51", "logs", "10:03", "payment_timeout", None, 500, "结算请求达到 500 毫秒等待上限。"),
        ("M-51", "metrics", "10:05", "payment_p95_ms", 500, 500, "支付服务 P95 响应耗时稳定在 500 毫秒。"),
        ("M-52", "metrics", "10:05", "checkout_error_pct", 2, 7, "结算错误率从 2% 升至 7%。"),
    ],
    "case-06": [
        ("R-61", "releases", "10:00", "payment_timeout_ms", 1500, 1500, "这次发布只更新了库存页样式。"),
        ("L-61", "logs", "10:03", "inventory_error", None, None, "库存后台同步任务报错。"),
        ("M-61", "metrics", "10:06", "checkout_error_pct", 1, 1, "结算错误率保持在 1%。"),
    ],
}


@contextmanager
def evidence_database(scenario=None, evidence=None):
    with closing(sqlite3.connect(":memory:", check_same_thread=False)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """CREATE TABLE evidence (
                scenario TEXT, id TEXT, source TEXT, at TEXT, signal TEXT,
                previous REAL, current REAL, description TEXT,
                PRIMARY KEY (scenario, id)
            )"""
        )
        if evidence is None:
            rows = [(case, *record) for case, records in RECORDS.items() for record in records]
        else:
            rows = [
                (scenario, row.id, row.source, row.at, row.signal, row.previous, row.current, row.description)
                for row in evidence
            ]
        conn.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.execute("PRAGMA query_only = ON")
        yield conn


def query_evidence(conn, scenario, source, window=None):
    window = window or QueryWindow()
    return [
        dict(row)
        for row in conn.execute(
            """SELECT id, source, at, signal, previous, current, description
            FROM evidence
            WHERE scenario = ? AND source = ? AND at BETWEEN ? AND ?
            ORDER BY at, id""",
            (scenario, source, window.start, window.end),
        )
    ]
