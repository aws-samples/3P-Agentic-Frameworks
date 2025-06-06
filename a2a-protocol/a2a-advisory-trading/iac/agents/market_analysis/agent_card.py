import json
import os

def lambda_handler(event, context):
    domain = event['requestContext']['domainName']
    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "id": "market-analysis-agent",
            "name": "MarketAnalysisAgent",
            "description": "Provides market analysis summaries and sentiment insights via Bedrock.",
            "protocol": "A2A/1.0",
            "skills": ["MarketSummary"],
            "endpoints": {
                "send": f"https://{domain}/dev/tasks/send"
            },
            "metadata": {
                "streaming": True,
                "modelId": model_id,
                "region": region,
                "provider": "Bedrock/Anthropic"
            }
        }),
        "headers": {
            "Content-Type": "application/json"
        }
    }
