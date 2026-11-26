"""FastAPI 和本机演示入口。"""

import os
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent import investigate
from .data import SCENARIOS, UPLOAD_SCENARIO, EvidenceRecord

WEB = Path(__file__).parent / "web"
app = FastAPI(title="发布异常归因 Agent", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.mount("/static", StaticFiles(directory=WEB), name="static")


class Request(BaseModel):
    scenario: str
    alert: str = Field(min_length=1, max_length=300)
    mode: Literal["local", "bailian"] = "local"
    evidence: list[EvidenceRecord] | None = Field(default=None, max_length=100)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/scenarios")
def scenarios():
    return {
        "cases": [{"id": key, "label": label, "alert": alert} for key, (label, alert) in SCENARIOS.items()],
        "bailian_ready": bool(os.getenv("DASHSCOPE_API_KEY")),
    }


@app.post("/api/investigate")
def run(request: Request):
    if request.scenario == UPLOAD_SCENARIO:
        if not request.evidence:
            raise HTTPException(422, "请导入至少一条证据记录。")
        if len({row.id for row in request.evidence}) != len(request.evidence):
            raise HTTPException(422, "证据编号需要唯一。")
    elif request.scenario not in SCENARIOS:
        raise HTTPException(404, "找不到该模拟案例。")
    elif request.evidence is not None:
        raise HTTPException(422, "导入证据时请使用自定义案例。")
    if not request.alert.strip():
        raise HTTPException(422, "请输入告警描述。")
    if request.mode == "bailian" and not os.getenv("DASHSCOPE_API_KEY"):
        raise HTTPException(409, "请先在本机设置 DASHSCOPE_API_KEY。")
    return investigate(request.scenario, request.alert.strip(), request.mode, request.evidence)


def serve():
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("RELEASE_TRIAGE_PORT", "8767")))


if __name__ == "__main__":
    serve()
