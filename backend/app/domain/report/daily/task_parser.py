"""
Task Parser

자연어 업무 내용을 구조화된 TaskItem으로 변환.
"""
from typing import Dict, Any
from app.llm.client import LLMClient


class TaskParser:
    """자연어 업무를 TaskItem으로 변환하는 유틸리티."""

    def __init__(self, llm_client: LLMClient, prompt_registry=None):
        self.llm_client = llm_client
        if prompt_registry is None:
            from multi_agent.agents.report_main_router import ReportPromptRegistry

            prompt_registry = ReportPromptRegistry
        self.prompt_registry = prompt_registry

    async def parse(
        self,
        text: str,
        time_range: str
    ) -> Dict[str, Any]:
        """비동기: 자연어 입력을 TaskItem으로 변환."""
        user_prompt = self.prompt_registry.task_parser_user(time_range=time_range, text=text)

        try:
            result = await self.llm_client.acomplete_json(
                system_prompt=self.prompt_registry.task_parser_system(),
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=300
            )

            # time_range 보강
            result["time_range"] = time_range

            return result

        except Exception as e:
            print(f"[ERROR] Task parsing failed: {e}")
            return {
                "title": text[:50],
                "description": text,
                "category": "기타",
                "time_range": time_range
            }

    def parse_sync(
        self,
        text: str,
        time_range: str
    ) -> Dict[str, Any]:
        """동기: 자연어 입력을 TaskItem으로 변환."""
        user_prompt = self.prompt_registry.task_parser_user(time_range=time_range, text=text)

        try:
            result = self.llm_client.complete_json(
                system_prompt=self.prompt_registry.task_parser_system(),
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=300
            )

            result["time_range"] = time_range

            return result

        except Exception as e:
            print(f"[ERROR] Task parsing failed: {e}")
            return {
                "title": text[:50],
                "description": text,
                "category": "기타",
                "time_range": time_range
            }
