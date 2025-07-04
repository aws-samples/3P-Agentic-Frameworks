import os
import re
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from strands import Agent as StrandsAgent
from strands.models import BedrockModel
from a2a.types import Task, TaskStatus, TaskState, Message, Artifact, Role, TextPart, DataPart

SYSTEM_PROMPT = (
    "You are a financial analyst. Provide clear, insightful market summaries. "
    "Answer the questions to the best of your model training data."
)

def extract_user_input_from_task(task: Task) -> Dict[str, Any]:
    _input_data = {}

    print(f"DEBUG: Received task: {task}")

    if not task or not task.history:
        print("DEBUG: No task or history found")
        return {"error": "No task or history found"}

    # Find the most recent user message
    user_messages = [msg for msg in task.history if msg.role.value == "user"]
    if not user_messages:
        print("DEBUG: No user messages found")
        return {"error": "No user messages found"}

    latest_user_message = user_messages[-1]
    print(f"DEBUG: Latest user message: {latest_user_message}")

    # Process message parts
    for part in latest_user_message.parts:
        print(f"DEBUG: Processing part: {part}")
        if part.root.kind == "text":
            _input_data["userContext"] = part.root.text
        if part.root.kind == "data" and part.root.data:
            # Extract main data fields
            data = part.root.data
            _input_data["sector"] = data.get("sector", "UNKNOWN_SECTOR")
            _input_data["focus"] = data.get("focus", "UNKNOWN_FOCUS")
            _input_data["riskFactors"] = data.get("riskFactors", [])
            _input_data["summaryLength"] = data.get("summaryLength", 200)
            # Extract extra context if present
            if "extraContext" in data:
                _input_data["extraContext"] = data["extraContext"]

    print(f"DEBUG: Extracted data: {_input_data}")
    return _input_data


class MarketAnalysisAgent:
    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
        region_name = region or os.environ.get("AWS_PRIMARY_REGION", "us-east-1")
        self.model = BedrockModel(
            model_id=model_id,
            streaming=True,
            region_name=region_name,
            max_tokens=600
        )
        self.strands_agent = StrandsAgent(
            model=self.model,
            system_prompt=SYSTEM_PROMPT
        )

    def build_prompt(self, input_: Dict[str, Any]) -> str:
        extra_context = input_.get("extraContext", None)
        user_context = input_.get("userContext", None)
        sector = input_.get("sector", "technology sector")
        focus = input_.get("focus", "overall outlook")
        risk_factors = input_.get("riskFactors", [])
        summary_length = input_.get("summaryLength", 150)
        risks = ", ".join(risk_factors) if risk_factors else "market uncertainty"
        prompt = (
            f"Knowing the user request: {user_context}. "
            f"Write a concise, coherent, and natural-sounding market summary (about {summary_length} words) for the {sector} sector. "
            f"Focus on {focus}. Discuss key trends, opportunities, and threats in a single paragraph. "
            f"If the user request has the intention of making a trade but did not specify which stock or company, "
            f"then the summary should name out what is the company that matches user description for investment. "
            f"Do NOT include a title, bullet points, or any formatting—write in natural English prose only. "
            f"Consider risk factors such as: {risks}."
        )

        '''
        For local use only
        '''
        if extra_context:
            prompt += f" Here is more context: {extra_context}."
        return prompt

    def analyze(self, task: Task) -> Task:
        prompt_input = extract_user_input_from_task(task)

        prompt = self.build_prompt(prompt_input)

        try:
            response = self.strands_agent(prompt)
            summary = str(response)
            tag_data = self.extract_tags(summary)

            parts = [
                {
                    "kind": "text",
                    "text": summary,
                    "metadata": {}
                },
                {
                    "kind": "data",
                    "data": tag_data,
                    "metadata": {}
                }
            ]
            artifact = Artifact(
                artifactId=str(uuid.uuid4()),
                parts=parts,
                name="Market Summary",
                description="Summary and tags generated by LLM"
            )
            msg = Message(
                role="agent",
                parts=[TextPart(kind="text", text="Market summary successfully generated.", metadata={})],
                messageId=str(uuid.uuid4()),
                kind="message",
                taskId=task.id,
                contextId=getattr(task, "contextId", None)
            )
            status = TaskStatus(
                state=TaskState.completed,
                message=msg,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            task.status = status
            task.artifacts = task.artifacts or []
            task.artifacts.append(artifact)
            if hasattr(task, "kind"):
                task.kind = "task"
            else:
                setattr(task, "kind", "task")
        except Exception as e:
            error_parts = [
                {
                    "kind": "text",
                    "text": str(e),
                    "metadata": {}
                }
            ]

            artifact = Artifact(
                artifactId=str(uuid.uuid4()),
                parts=error_parts,
                name="Error",
                description="Error encountered during market analysis"
            )

            error_msg = Message(
                role="agent",
                parts=error_parts,
                messageId=str(uuid.uuid4()),
                kind="message",
                taskId=task.id,
                contextId=getattr(task, "contextId", None)
            )

            status = TaskStatus(
                state=TaskState.failed,
                message=error_msg,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )

            task.status = status
            task.artifacts = task.artifacts or []
            task.artifacts.append(artifact)
            if hasattr(task, "kind"):
                task.kind = "task"
            else:
                setattr(task, "kind", "task")
        return task


    def extract_tags(self, summary: str) -> Dict[str, Any]:
        prompt = (
            "Analyze the following market summary and return exactly 4-7 key themes as a list of 'tags', "
            "and the overall sentiment (positive, neutral, or negative) for investors. "
            "Respond with nothing except a single JSON object with this format:\n"
            '{"tags": ["tag1", "tag2", "tag3"], "sentiment": "positive"}\n'
            "No title. No explanation. No extra text.\n\n"
            f"Summary:\n\"{summary}\""
        )
        try:
            result = str(self.strands_agent(prompt))
            try:
                parsed = json.loads(result)
            except Exception:
                match = re.search(r'\{[\s\S]*?}', result)
                parsed = json.loads(match.group()) if match else {}
            tags = parsed.get("tags", [])
            sentiment = parsed.get("sentiment", "unknown")
            if not isinstance(tags, list):
                tags = [tags] if tags else []
            if not isinstance(sentiment, str):
                sentiment = str(sentiment)
            return {"tags": tags, "sentiment": sentiment}
        except Exception as e:
            return {"tags": [], "sentiment": "unknown"}
