#!/usr/bin/env python3
"""
AI Agent FastAPI Server

Provides a FastAPI REST API interface for the AI agent, allowing HTTP clients
to interact with the agent functionality with simple stateless endpoints.
"""
import logging
import os
import sys
# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG') == '1' else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)


import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import uvicorn
import jwt
from strands import Agent
from .agent import create_agent


OAUTH_JWKS_URL = os.environ.get('OAUTH_JWKS_URL')
# Disable authentication for testing if OAUTH_JWKS_URL contains localhost or is a test URL
TESTING_MODE = not OAUTH_JWKS_URL or 'localhost' in OAUTH_JWKS_URL or os.environ.get('DISABLE_AUTH') == '1'
jwks_client = jwt.PyJWKClient(OAUTH_JWKS_URL) if OAUTH_JWKS_URL and not TESTING_MODE else None

# Debug logging
logger.info(f"OAUTH_JWKS_URL: {OAUTH_JWKS_URL}")
logger.info(f"Testing mode: {TESTING_MODE}")
logger.info(f"Authentication enabled: {not TESTING_MODE}")

# DynamoDB setup for agent state management (with in-memory fallback for testing)
USE_DYNAMODB = os.environ.get('DYNAMODB_AGENT_STATE_TABLE_NAME') is not None

if USE_DYNAMODB:
    import boto3
    from boto3.dynamodb.conditions import Key
    ddb = boto3.resource('dynamodb')  # type: ignore
    agent_state_table = ddb.Table(os.environ['DYNAMODB_AGENT_STATE_TABLE_NAME'])  # type: ignore
    logger.info("Using DynamoDB for agent state management")
else:
    # In-memory storage for testing purposes
    agent_state_memory: Dict[str, str] = {}
    logger.info("Using in-memory storage for agent state management (testing mode)")


def save_agent_state(user_id: str, agent: Agent):
    """Save agent state to DynamoDB or in-memory storage"""
    logger.info(f"saving agent state for user.id={user_id}")
    messages = agent.messages

    if USE_DYNAMODB:
        agent_state_table.put_item(Item={
            'user_id': user_id,
            'state': json.dumps(messages)
        })
    else:
        # Save to in-memory storage
        agent_state_memory[user_id] = json.dumps(messages)


def restore_agent_state(user_id: str):
    """Restore agent state from DynamoDB or in-memory storage"""
    logger.info(f"restoring agent state for user.id={user_id}")

    if USE_DYNAMODB:
        ddb_response = agent_state_table.get_item(Key={'user_id': user_id})
        item = ddb_response.get('Item')
        if item:
            messages = json.loads(item['state'])
        else:
            messages = []
    else:
        # Restore from in-memory storage
        state_json = agent_state_memory.get(user_id)
        if state_json:
            messages = json.loads(state_json)
        else:
            messages = []

    print(f"messages={messages}")
    return messages


# Pydantic models for request/response
class PromptRequest(BaseModel):
    text: str

class PromptResponse(BaseModel):
    text: str

class HealthResponse(BaseModel):
    status: str

class AgentFastAPI:
    """FastAPI REST API wrapper for the AI Agent"""

    def __init__(self, host: str = "0.0.0.0", port: int = 3000):
        self.host = host
        self.port = port

        # Initialize FastAPI app
        self.app = FastAPI(
            title="AI Agent FastAPI",
            description="FastAPI REST API interface for the AI Agent",
            version="1.0.0"
        )

        self._setup_routes()

    def _get_jwt_claims(self, authorization_header: str) -> Any:
        if not jwks_client:
            # Return mock claims for testing when OAUTH_JWKS_URL is not set
            return {"sub": "test-user", "username": "test-user"}

        jwt_string = authorization_header.split(" ")[1]
        #print(jwt_string)
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(jwt_string)
            claims = jwt.decode(jwt_string, signing_key.key, algorithms=["RS256"])
        except Exception as e:
                logger.error("Failed to parse authorization_header", exc_info=True)
                raise HTTPException(status_code=401, detail="Invalid authorization_header")
        print(claims)
        return claims

    def _setup_routes(self):
        """Configure FastAPI routes"""

        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint"""
            return HealthResponse(status="healthy")

        @self.app.post("/prompt", response_model=PromptResponse)
        async def prompt(request: PromptRequest, authorization: Optional[str] = Header(None)):
            """Process prompt with the AI assistant"""
            # Validate and parse JWT token (optional for testing)
            try:
                logger.info(f"Testing mode: {TESTING_MODE}")
                logger.info(f"Authorization header present: {authorization is not None}")

                if not TESTING_MODE and not authorization:
                    logger.info("Authentication required but no header provided")
                    raise HTTPException(status_code=401, detail="Authorization header required")

                if authorization and not TESTING_MODE:
                    claims = self._get_jwt_claims(authorization)
                    user_id = claims.get("sub")
                    username = claims.get("username")
                else:
                    # Use default values for testing when no auth is configured
                    logger.info("Using test user credentials (testing mode)")
                    user_id = "test-user"
                    username = "test-user"

                logger.info(f"User authenticated. user_id={user_id} username={username}")

            except HTTPException:
                raise
            except Exception as e:
                logger.error("Failed to parse JWT", exc_info=True)
                raise HTTPException(status_code=401, detail="Invalid authorization token")

            # Process the prompt
            try:
                if not request.text or not request.text.strip():
                    raise HTTPException(status_code=400, detail="Text cannot be empty")

                prompt = request.text.strip()
                logger.info(f"User username: {username}")
                logger.info(f"User id: {user_id}")
                logger.info(f"User prompt: {prompt}")
                messages = restore_agent_state(user_id)

                # Get agent instance (lazy loading)
                agent = create_agent(messages)

                # Process the text with the agent
                response = str(await agent.invoke_async(prompt))

                save_agent_state(user_id, agent)

                return PromptResponse(text=response)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing prompt request: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process prompt request: {str(e)}" if os.getenv('DEBUG') else "Internal server error"
                )

        @self.app.get("/")
        async def root():
            """Root endpoint with API information"""
            return {
                "message": "Welcome to AI Agent FastAPI",
                "endpoints": {
                    "health": "/health",
                    "prompt": "/prompt"
                }
            }


    def run(self, debug: bool = False):
        """Start the FastAPI server"""
        logger.info(f"Starting AI Agent FastAPI server on {self.host}:{self.port}")
        logger.info(f"Debug mode: {debug}")

        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="debug" if debug else "info",
                reload=debug
            )
        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}")
            raise


def fastapi_agent():
    """Main entry point for the FastAPI server"""
    # Get configuration from environment variables
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "3000"))
    debug = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

    # Create and start the server
    server = AgentFastAPI(host=host, port=port)
    server.run(debug=debug)


if __name__ == "__main__":
    fastapi_agent()
