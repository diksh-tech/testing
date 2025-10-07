import asyncio
import os
import logging
from pathlib import Path

from computer import Computer  # Adjusted import based on earlier issues
from agent import ComputerAgent  # From cua-agent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create trajectory directory
trajectory_dir = Path("trajectories")
trajectory_dir.mkdir(exist_ok=True)

async def run_teams_automation():
    # Check and set API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not found in environment. Please enter it:")
        api_key = input("Enter your OpenAI API Key: ")
        os.environ["OPENAI_API_KEY"] = api_key

    # Create agent with OpenAI model and local computer tool
    async with Computer(
        use_host_computer_server=True,  # Connect to local computer_server
        os_type="windows",              # Set to Windows
        verbosity=logging.INFO
    ) as computer:
        agent = ComputerAgent(
            model="gpt-4o",  # Use GPT-4o model
            tools=[computer],
            trajectory_dir=str(trajectory_dir),
            only_n_most_recent_images=3,  # Limit context to last 3 screenshots
            verbosity=logging.INFO
        )

        # Tasks for Teams automation
        tasks = [
            "Open the Microsoft Teams application using the desktop or taskbar icon.",
            "Click on the search bar within Teams and type the name 'John Doe'.",
            "From the search results, click on 'John Doe' to open their chat window.",
            "Click on the message input area in the chat window and type 'Hello from Cua Agent!'",
            "Press the Enter key to send the message."
        ]

        for i, task in enumerate(tasks):
            print(f"\nExecuting task {i+1}/{len(tasks)}: {task}")
            try:
                async for result in agent.run(task):
                    # Log results (e.g., actions, observations)
                    if result.get("text"):
                        print(f" → {result.get('text')[:100]}...")  # Truncate for brevity
                    if result.get("screenshot"):
                        # Save screenshot if available
                        screenshot_path = trajectory_dir / f"task_{i+1}_screenshot.png"
                        with open(screenshot_path, "wb") as f:
                            f.write(result["screenshot"])
                        print(f" → Screenshot saved: {screenshot_path}")
            except Exception as e:
                logger.error(f"Task {i+1} failed: {e}")
                continue

            print(f"\n✅ Task {i+1}/{len(tasks)} completed: {task}")

    # Trajectory info
    print(f"Trajectories saved to: {trajectory_dir.absolute()}")
    print("Upload trajectory files to https://trycua.com/trajectory-viewer to visualize agent actions")

if __name__ == "__main__":
    asyncio.run(run_teams_automation())
