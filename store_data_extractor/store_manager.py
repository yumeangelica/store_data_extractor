from datetime import datetime
import asyncio
import aiohttp
import logging
import os
import json
from store_data_extractor.src.data_extractor import main_program
from typing import Optional, List
from store_data_extractor.store_types import StoreConfigDataType

# Path to the stores configuration file
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "stores.json")

store_config: Optional[List[StoreConfigDataType]] = None
with open(CONFIG_PATH, 'r') as f:
    store_config = json.load(f)

SEMAPHORE = asyncio.Semaphore(3) # Limit the number of concurrent requests

# Import the global instance instead of the class
from store_data_extractor.src.user_agent_manager import user_agent_manager

class StoreManager:
    """Manage the stores and their data."""
    def __init__(self) -> None:
        self.stores: Optional[List[StoreConfigDataType]] = store_config
        self.session = None
        self.logger = logging.getLogger("StoreManager")
        from store_data_extractor.src.store_database import StoreDatabase
        self.db: StoreDatabase = StoreDatabase()
        self.user_agent_manager = user_agent_manager # only one instance of UserAgentManager, prevent multiple instances
        self._shutdown_event = asyncio.Event() # Event to signal shutdown
        self.current_tasks: List[asyncio.Task] = []


    async def start_session(self) -> None:
        """Start a new session."""
        self.logger.info("Starting session...")
        if not self.session:
            self.session: Optional[aiohttp.ClientSession] = aiohttp.ClientSession()


    async def stop_session(self) -> None:
        """Close the session."""
        self.logger.info("Stopping session...")
        if self.session:
            await self.session.close()
            self.session = None
        await self.db.close_connection() # Close the database connection


    async def schedule_runner(self) -> None:
        """Manage store updates with graceful shutdown support."""
        await self.start_session()
        try:
            while not self._shutdown_event.is_set():
                await self.run_scheduled_tasks()
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60)
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue with next iteration
        finally:
            await self.graceful_shutdown()


    async def run_scheduled_tasks(self) -> None:
        """Run the scheduled tasks for all stores."""
        tasks = []
        for store in self.stores: # type: ignore
            if await self.should_run_now(store):
                self.logger.info(f"Scheduling task for {store['name']}")
                tasks.append(asyncio.create_task(self.fetch_store_data(store)))

        # Run all tasks in parallel
        if tasks:
            await asyncio.gather(*tasks)


    async def should_run_now(self, store: StoreConfigDataType) -> bool:
        """Check if the store should be updated now."""

        now = datetime.now()

        schedule = store["schedule"]
        minutes = schedule["minutes"]   # "*" not allowed
        hours = schedule["hours"]       # "*" allowed
        days = schedule["days"]         # "*" allowed
        months = schedule["months"]     # "*" allowed
        years = schedule["years"]       # "*" allowed

        if str(now.minute) not in map(str, minutes):
            return False

        if hours != "*" and str(now.hour) not in map(str, hours):
            return False

        if days != "*" and str(now.day) not in map(str, days):
            return False

        if months != "*" and str(now.month) not in map(str, months):
            return False

        if years != "*" and str(now.year) not in map(str, years):
            return False

        return True

    async def fetch_store_data(self, store: StoreConfigDataType) -> None:
        """Fetch and process store data with improved error handling."""
        try:
            async with SEMAPHORE:
                task = asyncio.current_task()
                if task:
                    self.current_tasks.append(task)

                new_products = await main_program(self.session, store)
                for product in new_products:
                    print(f'name: {product["name"]}, url: {product["product_url"]}, image: {product["image_url"]}, prices: {product["prices"]}')
                    print()

        except asyncio.CancelledError:
            self.logger.warning(f"Task cancelled for {store['name']}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching data for {store['name']}: {e}")
        finally:
            try:
                await self.user_agent_manager.save_index_after_task(force=True)
            except Exception as e:
                self.logger.error(f"Failed to save user agent index: {e}")

            # Remove the task from the current tasks list
            task = asyncio.current_task()
            if task and task in self.current_tasks:
                self.current_tasks.remove(task)

    async def graceful_shutdown(self) -> None:
        """Initiate graceful shutdown of all operations."""
        if self._shutdown_event.is_set():
            return

        self._shutdown_event.set()
        self.logger.info("Initiating graceful shutdown...")

        # Cancel and wait for current tasks to complete
        for task in self.current_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self.stop_session()


    async def run_all_stores(self) -> None:
        """Fetch data for all stores."""
        for store in self.stores: # type: ignore
            await self.fetch_store_data(store)
