"""系統內 AI：統一的 LLM 呼叫介面、用量紀錄與每月上限。其他模組只透過 ai.service.complete 呼叫。"""

from app.modules.ai.router import router

__all__ = ["router"]
