"""Main entry point for the Agent application."""

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

import signal
import subprocess
import time

from dotenv import load_dotenv
load_dotenv()  # take environment variables

from .agent_server_fastapi  import fastapi_agent
from .agent_interactive     import interactive_agent

def main_fastapi():
    """Start the FastAPI server."""
    logging.info("Starting FastAPI Server")
    fastapi_agent()


def main_interactive():
    """Start the interactive command-line interface."""
    logging.info("Starting Interactive Agent")
    interactive_agent()


def servers():
    """Start MCP, A2A, and FastAPI servers concurrently using subprocesses."""
    logger.info("Starting Agent Triple Server...")
    logger.info(f"FastAPI Server will run on port {os.getenv('FASTAPI_PORT', '3000')}")

    processes = []

    def cleanup_and_exit(signum=None, frame=None):
        if signum:
            logger.info(f"Received signal {signum}, shutting down...")
        else:
            logger.info("Shutting down...")

        # Terminate all processes
        for name, process in processes:
            if process.poll() is None:  # Still running
                logger.info(f"Terminating {name} (PID: {process.pid})")
                try:
                    process.terminate()
                    process.wait(timeout=2)
                    logger.info(f"{name} terminated gracefully")
                except subprocess.TimeoutExpired:
                    logger.info(f"Force killing {name}")
                    process.kill()
                    process.wait()
                except Exception as e:
                    logger.error(f"Error stopping {name}: {e}")

        logger.info("All servers stopped")
        sys.exit(0)

    # Set up signal handlers
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    try:
        # Start FastAPI server
        logger.info("Starting FastAPI Server...")
        fastapi_process = subprocess.Popen([
            "uv", "run", "fastapi-server"
        ])
        processes.append(("FastAPI Server", fastapi_process))

        logger.info("All servers started successfully!")
        logger.info("Press Ctrl+C to stop all servers")

        # Monitor processes
        while True:
            # Check if any process has died
            for name, process in processes:
                if process.poll() is not None:
                    logger.error(f"{name} exited with code {process.returncode}")
                    cleanup_and_exit()
                    return

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        cleanup_and_exit()
    except Exception as e:
        logger.error(f"Error: {e}")
        cleanup_and_exit()


if __name__ == "__main__":
    servers()
