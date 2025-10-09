import asyncio
import os
import base64
import traceback
from typing import List, Dict, Any

from computer.computer import Computer
from computer.logger import LogLevel
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CUAAgent:
    def __init__(self):
        # Azure AI Foundry configuration
        self.client = AzureOpenAI(
            base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT')}/openai/v1/",
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="preview"  # Must be preview for CUA
        )
        self.response_history = []
    
    async def get_agent_actions(self, screenshot_bytes: bytes, user_prompt: str) -> List[Dict[str, Any]]:
        """Get actions from CUA agent based on screenshot and prompt"""
        try:
            # Convert screenshot to base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Prepare input for the agent
            input_content = [
                {
                    "type": "input_text",
                    "text": user_prompt
                },
                {
                    "type": "input_image", 
                    "image_url": f"data:image/png;base64,{screenshot_b64}"
                }
            ]
            
            # If we have previous response, use it for context
            if self.response_history:
                last_response_id = self.response_history[-1].id
            else:
                last_response_id = None
            
            # Call Azure AI Foundry CUA model
            response = self.client.responses.create(
                model="computer-use-preview",
                previous_response_id=last_response_id,
                tools=[{
                    "type": "computer_use_preview",
                    "display_width": 1920,  # Adjust based on your screen
                    "display_height": 1080,
                    "environment": "windows"
                }],
                input=[{"role": "user", "content": input_content}],
                truncation="auto",
                max_output_tokens=1500
            )
            
            # Store response for context
            self.response_history.append(response)
            
            # Extract computer call actions
            computer_calls = [
                item for item in response.output 
                if item.type == "computer_call"
            ]
            
            actions = []
            for call in computer_calls:
                actions.append({
                    "type": call.action.type,
                    "details": call.action,
                    "call_id": call.call_id
                })
            
            return actions
            
        except Exception as e:
            print(f"Error getting agent actions: {e}")
            traceback.print_exc()
            return []
    
    def clear_history(self):
        """Clear conversation history"""
        self.response_history.clear()


class TeamsAutomationWithAgent:
    def __init__(self):
        self.computer = None
        self.agent = CUAAgent()
    
    async def initialize_computer(self):
        """Initialize the computer interface"""
        try:
            print("\n=== Initializing host computer ===")
            self.computer = Computer(
                use_host_computer_server=True,
                os_type="windows",
                name="windows_host",
                verbosity=LogLevel.VERBOSE,
            )
            await self.computer.run()
            return True
        except Exception as e:
            print(f"Failed to initialize computer: {e}")
            return False
    
    async def execute_agent_action(self, action: Dict[str, Any]):
        """Execute an action returned by the agent"""
        action_type = action["type"]
        details = action["details"]
        
        try:
            if action_type == "click":
                x = getattr(details, 'x', 0)
                y = getattr(details, 'y', 0)
                button = getattr(details, 'button', 'left')
                print(f"Agent action: Click at ({x}, {y}) with {button} button")
                await self.computer.interface.left_click(x, y)
                
            elif action_type == "type":
                text = getattr(details, 'text', '')
                print(f"Agent action: Type text: '{text}'")
                await self.computer.interface.type_text(text)
                
            elif action_type == "scroll":
                scroll_x = getattr(details, 'scroll_x', 0)
                scroll_y = getattr(details, 'scroll_y', 0)
                print(f"Agent action: Scroll by ({scroll_x}, {scroll_y})")
                # You might need to implement scroll in your computer interface
                # await self.computer.interface.scroll(scroll_x, scroll_y)
                
            elif action_type == "keypress":
                keys = getattr(details, 'keys', [])
                for key in keys:
                    print(f"Agent action: Press key: {key}")
                    if key.lower() == "enter":
                        await self.computer.interface.press_key("enter")
                    # Add other key mappings as needed
                    
            elif action_type == "wait":
                wait_ms = getattr(details, 'ms', 2000)
                print(f"Agent action: Wait for {wait_ms}ms")
                await asyncio.sleep(wait_ms / 1000)
                
            else:
                print(f"Unknown action type: {action_type}")
                
        except Exception as e:
            print(f"Error executing agent action {action_type}: {e}")
    
    async def take_screenshot(self) -> bytes:
        """Take screenshot using computer interface"""
        try:
            return await self.computer.interface.screenshot()
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            # Fallback: You might need to implement alternative screenshot method
            return b""
    
    async def automate_teams_with_agent(self, person_name: str, message: str, max_iterations: int = 15):
        """Use AI agent to automate Teams message sending"""
        if not await self.initialize_computer():
            return False
        
        try:
            # Main task prompt for the agent
            task_prompt = f"""
            Send a message to {person_name} in Microsoft Teams with the following message: "{message}"
            
            Steps needed:
            1. Find and open Microsoft Teams (look for taskbar icon or start menu)
            2. Search for the person named "{person_name}"
            3. Click on their name to open the chat
            4. Type the message in the chat input field
            5. Send the message
            
            Please perform these actions step by step.
            """
            
            print(f"\n=== Starting Teams Automation with AI Agent ===")
            print(f"Target: {person_name}")
            print(f"Message: {message}")
            
            iteration = 0
            task_completed = False
            
            while iteration < max_iterations and not task_completed:
                iteration += 1
                print(f"\n--- Agent Iteration {iteration} ---")
                
                # Take current screenshot
                screenshot = await self.take_screenshot()
                if not screenshot:
                    print("Failed to capture screenshot, stopping...")
                    break
                
                # Save screenshot for debugging
                output_dir = "./output"
                os.makedirs(output_dir, exist_ok=True)
                screenshot_path = os.path.join(output_dir, f"iteration_{iteration}.png")
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot)
                print(f"Screenshot saved: {screenshot_path}")
                
                # Get actions from agent
                actions = await self.agent.get_agent_actions(screenshot, task_prompt)
                
                if not actions:
                    print("No actions returned by agent. Task might be completed or stuck.")
                    # Check if we should break or continue
                    if iteration > 3:  # After few attempts with no actions, assume completion
                        task_completed = True
                    break
                
                print(f"Agent returned {len(actions)} action(s)")
                
                # Execute each action
                for i, action in enumerate(actions):
                    print(f"Executing action {i+1}/{len(actions)}: {action['type']}")
                    await self.execute_agent_action(action)
                    await asyncio.sleep(1)  # Brief pause between actions
                
                # Wait for actions to take effect before next iteration
                await asyncio.sleep(2)
                
                # Check for completion (you might want to add more sophisticated checks)
                if iteration >= max_iterations:
                    print(f"Reached maximum iterations ({max_iterations})")
            
            if task_completed:
                print("\n=== Task completed successfully! ===")
            else:
                print("\n=== Task ended (may not be fully completed) ===")
            
            return task_completed
            
        except Exception as e:
            print(f"Error during automation: {e}")
            traceback.print_exc()
            return False
        
        finally:
            # Clean up
            if self.computer:
                await self.computer.stop()
            self.agent.clear_history()


async def main():
    """Main function to run the Teams automation with AI agent"""
    
    # Configuration
    person_name = "John Doe"  # Change to actual contact name
    message = "Hello, this is an automated test message sent by AI agent!"
    
    # Create automation instance
    automation = TeamsAutomationWithAgent()
    
    # Run the automation
    success = await automation.automate_teams_with_agent(
        person_name=person_name,
        message=message,
        max_iterations=15
    )
    
    if success:
        print("🎉 Automation completed successfully!")
    else:
        print("❌ Automation encountered issues.")


if __name__ == "__main__":
    # Required environment variables in .env file:
    # AZURE_OPENAI_ENDPOINT=https://your-workspace.ai.azure.com
    # AZURE_OPENAI_KEY=your-api-key
    
    asyncio.run(main())








# Azure AI Foundry Configuration
AZURE_OPENAI_ENDPOINT=https://your-workspace.ai.azure.com
AZURE_OPENAI_KEY=your-api-key-here

# Optional: Additional configuration
AZURE_API_VERSION=preview





venv06) PS C:\Users\Deeksha.x.Srivastava\OneDrive - InterGlobe Aviation Limited\Desktop\cua_code> python teams_automation.py
error uploading: HTTPSConnectionPool(host='eu.i.posthog.com', port=443): Max retries exceeded with url: /batch/ (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')))
