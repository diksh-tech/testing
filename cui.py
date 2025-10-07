import asyncio
import os
import traceback

from computer.computer import Computer  # Adjust if import fails (try cua_computer)
from computer.logger import LogLevel

async def automate_teams():
    try:
        print("\n=== Using host computer initialization ===")

        # Create a local Windows computer using host server
        computer = Computer(
            use_host_computer_server=True,  # Connect to local computer_server
            os_type="windows",              # Set to Windows
            name="windows_host",
            verbosity=LogLevel.VERBOSE,
        )

        try:
            # Run the computer to connect to the host desktop
            await computer.run()

            # Your tested coordinates (adjust based on trials)
            coords = {
                "teams_icon": (813, 1046),  # Trial for Teams taskbar/desktop icon
                "search_bar": (45, 95),     # Trial for Teams search bar
                "person_name": (793, 950),  # Trial for person's name in search results
                "message_bar": (1798, 945), # Trial for chat message input
            }

            # Task parameters
            person_name = "John Doe"
            message = "Hello, this is an automated test message!"

            # Step 1: Take a screenshot for debugging
            screenshot = await computer.interface.screenshot()
            output_dir = "./output"
            os.makedirs(output_dir, exist_ok=True)
            screenshot_path = os.path.join(output_dir, "screenshot.png")
            with open(screenshot_path, "wb") as f:
                f.write(screenshot)
            print(f"Screenshot saved to: {screenshot_path}")

            # Step 2: Open Microsoft Teams
            print("\n=== Opening Teams ===")
            await computer.interface.left_click(coords["teams_icon"][0], coords["teams_icon"][1])
            await asyncio.sleep(5)  # Wait for Teams to load

            # Step 3: Click the search bar and type the person's name
            print("\n=== Searching for Person ===")
            await computer.interface.left_click(coords["search_bar"][0], coords["search_bar"][1])
            await computer.interface.type_text(person_name)
            await asyncio.sleep(2)  # Wait for search results

            # Step 4: Click the person's name to open chat
            print("\n=== Opening Chat ===")
            await computer.interface.left_click(coords["person_name"][0], coords["person_name"][1])
            await asyncio.sleep(3)  # Wait for chat to load

            # Step 5: Click the message bar, type, and send
            print("\n=== Sending Message ===")
            await computer.interface.left_click(coords["message_bar"][0], coords["message_bar"][1])
            await computer.interface.type_text(message)
            await computer.interface.press_key("enter")

            print("Automation completed successfully!")

            # Optional: Get screen size for coord validation
            screen_size = await computer.interface.get_screen_size()
            print(f"Screen size: {screen_size}")

        finally:
            # Clean up resources using the correct method
            await computer.stop()

    except Exception as e:
        print(f"Error in automate_teams: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(automate_teams())
