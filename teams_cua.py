#!/usr/bin/env python3
"""
CUA Teams Daemon (Azure OpenAI ready)
- Uses local computer server (use_host_computer_server=True)
- Uses Azure OpenAI deployment to drive UI actions
- Runs as a background worker consuming task queue
- Saves trajectories/screenshots in `trajectories/`
NOTE: Adjust imports / constructor args to match your installed CUA SDK if needed.
"""

import asyncio
import os
import logging
import signal
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# ====== Adjust these imports if your SDK exposes different names ======
from computer import Computer            # trycua / cua computer tool
from agent import ComputerAgent          # agent wrapper from cua-agent
# =====================================================================

# ---------- Config (read from env) ----------
MODEL_NAME = os.getenv("CUA_MODEL", "azure/gpt-4o")   # or set to something like "azure/gpt-4o-preview"
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  # e.g. https://<resource-name>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # your deployment name in Azure
TRAJECTORY_DIR = Path("trajectories")
TRAJECTORY_DIR.mkdir(exist_ok=True)
MAX_RECENT_IMAGES = int(os.getenv("CUA_MAX_RECENT_IMAGES", "3"))
NUM_AGENTS = int(os.getenv("CUA_NUM_AGENTS", "1"))
# -----------------------------------------------------

# Basic validation
if not AZURE_OPENAI_KEY or not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT:
    raise RuntimeError(
        "Azure OpenAI configuration missing. Please set AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT env vars."
    )

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cua-teams-daemon-azure")

def _timestamp():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


class AgentWorker:
    def __init__(self, name: str, computer: Computer, model: str = MODEL_NAME,
                 azure_key: Optional[str] = None, azure_endpoint: Optional[str] = None,
                 azure_deployment: Optional[str] = None):
        self.name = name
        self.computer = computer
        self.model = model
        self.agent = None
        self._ready = False
        self.azure_key = azure_key
        self.azure_endpoint = azure_endpoint
        self.azure_deployment = azure_deployment

    async def init_agent(self):
        logger.info(f"[{self.name}] Initializing ComputerAgent (Azure model={self.model})")
        # NOTE: passing azure-specific kwargs — your SDK may use different param names
        self.agent = ComputerAgent(
            model=self.model,
            tools=[self.computer],
            trajectory_dir=str(TRAJECTORY_DIR),
            only_n_most_recent_images=MAX_RECENT_IMAGES,
            verbosity=logging.INFO,
            # Azure-specific:
            api_key=self.azure_key,
            api_base=self.azure_endpoint,
            deployment_id=self.azure_deployment,
            provider="azure"
        )
        # If agent requires async start, do it here:
        # if hasattr(self.agent, "start") and asyncio.iscoroutinefunction(self.agent.start):
        #     await self.agent.start()
        self._ready = True
        logger.info(f"[{self.name}] Agent initialized.")

    async def _save_screenshot_bytes(self, img_bytes: bytes):
        fname = TRAJECTORY_DIR / f"{self.name}_task_{_timestamp()}.png"
        try:
            with open(fname, "wb") as f:
                f.write(img_bytes)
            logger.info(f"[{self.name}] Saved screenshot: {fname}")
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to save screenshot: {e}")

    async def run_task(self, task_text: str):
        if not self._ready:
            raise RuntimeError("Agent not initialized")
        logger.info(f"[{self.name}] Running task: {task_text!r}")
        try:
            # If agent.run yields streaming results, iterate
            async for result in self.agent.run(task_text):
                text = result.get("text") or result.get("message")
                if text:
                    snippet = text.replace("\n", " ")[:300]
                    logger.info(f"[{self.name}] -> {snippet}")

                screenshot = result.get("screenshot") or result.get("image")
                if screenshot:
                    img_bytes = None
                    if isinstance(screenshot, (bytes, bytearray)):
                        img_bytes = bytes(screenshot)
                    elif isinstance(screenshot, str):
                        # possibly base64
                        try:
                            import base64
                            img_bytes = base64.b64decode(screenshot)
                        except Exception:
                            img_bytes = None
                    if img_bytes:
                        await self._save_screenshot_bytes(img_bytes)

            logger.info(f"[{self.name}] Task finished.")
            return True
        except Exception as e:
            logger.exception(f"[{self.name}] Task error: {e}")
            return False


class CUADaemon:
    def __init__(self, num_agents: int = 1):
        self.num_agents = num_agents
        self.queue: asyncio.Queue = asyncio.Queue()
        self.agents: List[AgentWorker] = []
        self.computer: Optional[Computer] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self):
        logger.info("Starting Computer container/session (local host server)...")
        # create/connect to Computer container — adjust constructor if SDK differs
        # Using context manager manual entry so it stays alive for entire daemon lifetime
        self.computer = await Computer(
            use_host_computer_server=True,
            os_type="windows",
            verbosity=logging.INFO
        ).__aenter__()

        # Initialize workers
        for i in range(self.num_agents):
            worker = AgentWorker(
                name=f"agent{i+1}",
                computer=self.computer,
                model=MODEL_NAME,
                azure_key=AZURE_OPENAI_KEY,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                azure_deployment=AZURE_OPENAI_DEPLOYMENT
            )
            await worker.init_agent()
            self.agents.append(worker)

        # spawn worker loops
        for worker in self.agents:
            t = asyncio.create_task(self._agent_loop(worker))
            self._tasks.append(t)

        self._running = True
        logger.info("CUA Daemon (Azure) started with %d agents.", len(self.agents))

    async def _agent_loop(self, worker: AgentWorker):
        while self._running:
            try:
                task_text = await self.queue.get()
                if task_text is None:
                    logger.info(f"[{worker.name}] Stop sentinel received.")
                    self.queue.task_done()
                    break
                logger.info(f"[{worker.name}] Dequeued task.")
                await worker.run_task(task_text)
                self.queue.task_done()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                logger.info(f"[{worker.name}] Cancelled.")
                break
            except Exception as e:
                logger.exception(f"[{worker.name}] Loop error: {e}")
                await asyncio.sleep(1.0)

    async def stop(self):
        logger.info("Stopping CUA Daemon...")
        self._running = False
        # send sentinel to each agent loop
        for _ in self.agents:
            await self.queue.put(None)
        await self.queue.join()
        for t in self._tasks:
            t.cancel()
        # close computer session
        try:
            await self.computer.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Error during computer shutdown: {e}")
        logger.info("CUA Daemon stopped.")

    async def enqueue_teams_message(self, person_name: str, message_text: str):
        instruction = (
            f"Open Microsoft Teams on the desktop, wait until the app is visible, "
            f"click the search box, type the name '{person_name}', select the person from results, "
            f"open the chat, click the message input area, type the message: \"{message_text}\", and press Enter to send."
        )
        await self.queue.put(instruction)
        logger.info(f"Enqueued Teams message task for {person_name}")


async def main():
    daemon = CUADaemon(num_agents=NUM_AGENTS)
    await daemon.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal():
        logger.info("Received termination signal.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass

    # Demo enqueue — in production you may make an HTTP endpoint to enqueue tasks
    await daemon.enqueue_teams_message("John Doe", "Hello from CUA agent (automated via Azure)")

    logger.info("Daemon running. Press Ctrl+C to stop.")
    await stop_event.wait()
    await daemon.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        logger.exception(f"Daemon crashed: {exc}")
