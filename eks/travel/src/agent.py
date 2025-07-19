import logging
import os
import sys
from strands_tools.a2a_client import A2AClientToolProvider

from strands import Agent
from strands.agent.conversation_manager import ConversationManager
from strands.types.content import Messages
from strands.models.bedrock import BedrockModel

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG') == '1' else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

import json
import re
from typing import Dict, List, Optional, Any, Tuple


def load_agent_config(config_file: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Load agent configuration from agent.md file.

    Args:
        config_file: Optional path to config file. If None, uses AGENT_CONFIG_FILE env var or default agent.md

    Returns:
        Tuple[str, str, str]: (name, description, system_prompt)

    Raises:
        FileNotFoundError: If no configuration file is found
        ValueError: If configuration file is missing required sections
    """
    # Get agent config file path from parameter, environment variable, or use default
    if config_file is None:
        # Try multiple locations for the config file
        current_dir = os.path.dirname(__file__)

        # Location 1: Check if AGENT_CONFIG_FILE is set
        if os.getenv("AGENT_CONFIG_FILE"):
            config_file = os.getenv("AGENT_CONFIG_FILE")
        else:
            # Location 2: Try project root (development mode - src/ is in project)
            project_root = os.path.dirname(current_dir)
            dev_config = os.path.join(project_root, "agent.md")

            # Location 3: Try /app/ directory (container mode - installed package)
            container_config = "/app/agent.md"

            # Location 4: Try current working directory
            cwd_config = os.path.join(os.getcwd(), "agent.md")

            if os.path.exists(dev_config):
                config_file = dev_config
            elif os.path.exists(container_config):
                config_file = container_config
            elif os.path.exists(cwd_config):
                config_file = cwd_config
            else:
                # Default to project root for error message
                config_file = dev_config

    if config_file is None or not os.path.exists(config_file):
        logger.warning(f"Agent config file not found at {config_file}")
        # Try fallback to cloudbot.md in multiple locations
        current_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(current_dir)

        fallback_locations = [
            os.path.join(project_root, "cloudbot.md"),  # Development mode
            "/app/cloudbot.md",                         # Container mode
            os.path.join(os.getcwd(), "cloudbot.md")    # Current working directory
        ]

        fallback_config = None
        for location in fallback_locations:
            if os.path.exists(location):
                fallback_config = location
                break

        if fallback_config:
            logger.info(f"Using fallback configuration: {fallback_config}")
            config_file = fallback_config
        else:
            raise FileNotFoundError(f"No agent configuration file found. Please provide either {config_file} or set AGENT_CONFIG_FILE environment variable.")

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the markdown content
        name = _extract_section(content, "Agent Name")
        description = _extract_section(content, "Agent Description")
        system_prompt = _extract_section(content, "System Prompt")

        if not name or not description or not system_prompt:
            raise ValueError(f"Agent configuration file {config_file} is missing required sections: Agent Name, Agent Description, or System Prompt")

        return name.strip(), description.strip(), system_prompt.strip()

    except Exception as e:
        logger.error(f"Error reading agent config file {config_file}: {str(e)}")
        raise


def _extract_section(content: str, section_name: str) -> Optional[str]:
    """
    Extract a section from markdown content.

    Args:
        content: The markdown content
        section_name: The section header to look for

    Returns:
        Optional[str]: The section content or None if not found
    """
    # Pattern to match ## Section Name followed by content until next ## or end
    pattern = rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None

agent_name, agent_description, system_prompt = load_agent_config()

DEFAULT_A2A_LIST=[
    "http://localhost:9000", # Weather
    #"http://localhost:3002" # Recs
]
def _get_a2a_agent_urls() -> List[str]:
    """
    Load a2a agent URLs from a config file or return default list if file doesn't exist.
    
    Returns:
        List[str]: List of a2a agent URLs
    """
    # Define possible config file locations
    current_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(current_dir)
    
    config_locations = [
        os.path.join(project_root, "a2a_agents.json"),  # Project root
        os.path.join(current_dir, "a2a_agents.json"),   # src directory
        "/app/a2a_agents.json",                         # Container path
        os.path.join(os.getcwd(), "a2a_agents.json")    # Current working directory
    ]
    
    # Try to load from config file
    for config_file in config_locations:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    if isinstance(config_data, list):
                        logger.info(f"Loaded {len(config_data)} a2a agent URLs from {config_file}")
                        return config_data
                    elif isinstance(config_data, dict) and "urls" in config_data:
                        logger.info(f"Loaded {len(config_data['urls'])} a2a agent URLs from {config_file}")
                        return config_data["urls"]
                    else:
                        logger.warning(f"Invalid format in {config_file}, expected list or dict with 'urls' key")
            except Exception as e:
                logger.warning(f"Error loading a2a agent URLs from {config_file}: {str(e)}")
    
    # Return default list if no config file found or loading failed
    logger.info("Using default a2a agent URLs")
    return DEFAULT_A2A_LIST  # Return empty list as default


def create_agent(messages: Optional[Messages]=None,conversation_manager: Optional[ConversationManager] = None) -> Agent:
    """
    Create and return an Agent instance with dynamically loaded MCP tools.

    Returns:
        Agent: A configured AI assistant agent with tools from enabled MCP servers
    """
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    bedrock_model = BedrockModel(model_id=model_id)
    provider = A2AClientToolProvider(known_agent_urls=_get_a2a_agent_urls())

    try:
        # Load and combine tools from all enabled MCP servers (cached)

        # Create the agent with configuration from agent.md
        agent = Agent(
            name=agent_name,
            description=agent_description,
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=provider.tools,
            messages=messages,
            conversation_manager=conversation_manager
        )

        return agent

    except Exception as e:
        logger.error(f"Error getting agent: {str(e)}")
        # Return a fallback agent when client fails
        fallback_agent = Agent(
            model=bedrock_model,
            system_prompt="""I am an AI Assistant, but I'm currently experiencing technical difficulties accessing my tools.
I apologize for the inconvenience. Please try again later or contact support if the issue persists.""",
            tools=[],
        )
        return fallback_agent



if __name__ == "__main__":
    # Test the agent functionality
    agent = create_agent()
    response = agent("Hello, how can you help me?")
    logger.info(f"Test response: {response}")
