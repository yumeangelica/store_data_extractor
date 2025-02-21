import signal
from store_data_extractor.store_manager import StoreManager
from utils.logger import configure_logger
import logging
import asyncio
from typing import Optional
import sys

logger: logging.Logger = logging.getLogger("Main")
store_manager: Optional[StoreManager] = None
shutdown_event = asyncio.Event()


async def graceful_shutdown():
    """Handle graceful shutdown once."""
    if not shutdown_event.is_set():
        logger.info("Setting shutdown event...")
        shutdown_event.set()
        if store_manager:
            logger.info("Shutting down StoreManager...")
            await store_manager.graceful_shutdown()
            logger.info("StoreManager shutdown complete")

def signal_handler(signum, frame):
    """Handle termination signals by scheduling async handler."""
    logger.info(f"Received signal {signum}")

    try:
        loop = asyncio.get_running_loop()
        # Create task for graceful shutdown
        loop.create_task(graceful_shutdown())
    except RuntimeError:
        # If we're not in an event loop, create a new loop and run the shutdown
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(graceful_shutdown())
    finally:
        # Force exit after shutdown
        sys.exit(0)

async def main_run() -> None:
    global store_manager
    configure_logger()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting application...")
    store_manager = StoreManager()

    try:
        await store_manager.schedule_runner()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await graceful_shutdown()
        sys.exit(1)
