"""Interactive command-line interface for the AI Agent."""

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

from rich.console import Console
from rich.markdown import Markdown

from .agent import create_agent

def interactive_agent():
    """Run an interactive command-line interface for the AI Agent."""
    logger.info("Starting Interactive Agent")
    console = Console()

    try:
        # Get agent instance to retrieve configuration
        agent = create_agent()
        logger.info(f"Agent loaded: {agent.name}")

        # Query the agent for welcome message and instructions
        welcome_query = """Please provide a welcome message for users starting an interactive session with you. Include:
1. Your name and brief description
2. What you can help with
3. 2-3 example queries users can try
4. Instructions to type /quit to exit the session

Format your response as a friendly welcome message."""

        try:
            logger.debug("Generating welcome message")
            welcome_response = agent(welcome_query)
            console.print(Markdown(str(welcome_response)))
        except Exception as e:
            # Fallback welcome message if agent query fails
            logger.warning(f"Failed to generate welcome message: {str(e)}")
            console.print(f"\n🤖 {agent.name}\n")
            console.print(f"{agent.description}\n")
            console.print("Ask me anything and I'll do my best to help!\n")
            console.print("Type '/quit' to exit the session.\n")

        logger.info("Starting interactive session")
        # Interactive loop
        while True:
            try:
                user_input = input("\n> ")
                if user_input.lower() == "/quit":
                    console.print("\nGoodbye! 👋")
                    logger.info("User quit interactive session")
                    break

                logger.debug(f"Processing user input: {user_input[:50]}...")
                response = agent(user_input)
                logger.debug(f"Generated response length: {len(str(response))} characters")

                console.print("\n")
                console.print(Markdown(str(response)))

            except KeyboardInterrupt:
                console.print("\n\nExecution interrupted. Exiting...")
                logger.info("Interactive session interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing user input: {str(e)}", exc_info=True)
                console.print(f"\nAn error occurred: {str(e)}")
                console.print("Please try asking a different question.")

    except Exception as e:
        logger.error(f"Failed to start interactive agent: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    interactive_agent()
