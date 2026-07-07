from datetime import datetime
import asyncio
import aiohttp
import logging
import os
import json
from store_data_extractor.src.data_extractor import main_program
from typing import Dict, Optional, List
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
        self._shutdown_started = False
        self._stopped = False
        self.current_tasks: List[asyncio.Task] = []
        self._store_locks: Dict[str, asyncio.Lock] = {} # Prevent concurrent runs for the same store

    def get_store_lock(self, store_name: str) -> asyncio.Lock:
        """Get (or create) the lock that serializes runs for a single store."""
        if store_name not in self._store_locks:
            self._store_locks[store_name] = asyncio.Lock()
        return self._store_locks[store_name]


    async def start_session(self) -> None:
        """Start a new session."""
        self.logger.info("Starting session...")
        self._stopped = False
        if not self.session:
            self.session: Optional[aiohttp.ClientSession] = aiohttp.ClientSession()


    async def stop_session(self) -> None:
        """Close the session."""
        if self._stopped:
            return

        self._stopped = True
        self.logger.info("Stopping session...")
        if self.session:
            await self.session.close()
            self.session = None
        await self.db.close_connection() # Close the database connection


    async def schedule_runner(self) -> None:
        """Manage store updates with graceful shutdown support."""
        await self.start_session()

        await self.resend_unsent_products()
        await self.run_startup_tasks()
        try:
            while not self._shutdown_event.is_set():
                scheduled_count = await self.run_scheduled_tasks()
                if scheduled_count == 0:
                    self.logger.info("No stores scheduled at current time. Waiting for next check...")
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60)
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue with next iteration
        except asyncio.CancelledError:
            self.logger.warning("Schedule runner task was cancelled.")
        except Exception as e:
            self.logger.error(f"Error in schedule runner: {e}")
        finally:
            await self.graceful_shutdown()
            await asyncio.sleep(0.1)

    async def run_startup_tasks(self) -> None:
        """Run stores configured to fetch immediately when the process starts."""
        tasks = []
        for store in self.stores or []:
            if store.get("run_on_start", False):
                self.logger.info(f"Running startup task for {store['name']}")
                tasks.append(asyncio.create_task(self.fetch_store_data(store)))

        if tasks:
            await asyncio.gather(*tasks)

    async def run_scheduled_tasks(self) -> int:
        """Run the scheduled tasks for all stores."""
        tasks = []
        for store in self.stores or []:
            if await self.should_run_now(store):
                self.logger.info(f"Scheduling task for {store['name']}")
                tasks.append(asyncio.create_task(self.fetch_store_data(store)))

        # Run all tasks in parallel
        if tasks:
            await asyncio.gather(*tasks)

        return len(tasks)


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

    async def resend_unsent_products(self) -> None:
        """Resend unsent products to the database."""
        products = await self.db.get_unsent_products()
        if not products:
            return
        self.logger.info("Resending unsent products...")
        for product in products:
            try:
                product_id = product["id"] if "id" in product else None
                if product_id:
                    await self.db.mark_product_as_sent(product_id)
                self.logger.info(f"Product {product['name']} marked as sent.")
            except Exception as e:
                self.logger.error(f"Failed to mark product {product['name']} as sent: {e}")

    async def fetch_store_data(self, store: StoreConfigDataType) -> None:
        """Fetch and process store data with improved error handling."""
        async with self.get_store_lock(store['name']):
            await self._fetch_store_data_locked(store)

    async def _fetch_store_data_locked(self, store: StoreConfigDataType) -> None:
        """Fetch and process store data; caller must hold the store lock."""
        try:
            await self.resend_unsent_products()

            async with SEMAPHORE:
                task = asyncio.current_task()
                if task:
                    self.current_tasks.append(task)

                result = await main_program(self.session, store, self.db)
                new_products, updated_products = result

                if new_products:
                    self.logger.info(f"New products found for {store['name']}:")
                    for product in new_products:
                        self.logger.info(f'New product: {product["name"]}, url: {product["product_url"]}, image: {product["image_url"]}, prices: {product["prices"]}')
                        product_id = product["id"] if "id" in product else None
                        if product_id:
                            await self.db.mark_product_as_sent(product_id)
                            self.logger.info(f"Product {product['name']} marked as sent.")
                if updated_products:
                    self.logger.info(f"Updated products found for {store['name']}:")
                    for product in updated_products:
                        self.logger.info(f'Updated product: {product["name"]}, url: {product["product_url"]}, image: {product["image_url"]}, prices: {product["prices"]}')
                        product_id = product["id"] if "id" in product else None
                        if product_id:
                            await self.db.mark_product_as_sent(product_id)
                            self.logger.info(f"Product {product['name']} marked as sent.")

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
        if self._shutdown_started:
            return

        self._shutdown_started = True
        self._shutdown_event.set()
        self.logger.info("Initiating graceful shutdown...")

        # Cancel and wait for current tasks to complete
        current_task = asyncio.current_task()
        for task in list(self.current_tasks):
            if task is current_task:
                continue
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self.stop_session()


    async def run_all_stores(self) -> None:
        """Fetch data for all stores."""
        for store in self.stores or []:
            await self.fetch_store_data(store)
