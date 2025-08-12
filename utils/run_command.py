"""
Run Command Utility for AI Coding Agent
Executes shell commands with proper error handling and output capture.
"""

import subprocess
import logging
import os
import time
from typing import Tuple

logger = logging.getLogger('run_command')

def run_command(command: str, working_dir: str = None, timeout: int = 30) -> Tuple[bool, str]:
    """
    Execute a shell command and return the result.
    
    Args:
        command (str): The command to execute
        working_dir (str): Working directory to run the command in
        timeout (int): Timeout in seconds (default: 30)
    
    Returns:
        Tuple[bool, str]: (success, output_or_error_message)
    """
    try:
        logger.info(f"Executing command: {command}")
        logger.info(f"Working directory: {working_dir or os.getcwd()}")
        
        # Special handling for streamlit commands
        if "streamlit run" in command.lower():
            # For streamlit, run in background and don't capture output to allow browser opening
            import threading
            import webbrowser
            
            def run_streamlit():
                subprocess.run(command, shell=True, cwd=working_dir)
            
            # Start streamlit in background thread
            streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
            streamlit_thread.start()
            
            # Give streamlit time to start
            time.sleep(3)
            
            # Open browser to streamlit app
            webbrowser.open("http://localhost:8501")
            
            return True, f"Streamlit application started successfully!\nCommand: {command}\nAccess at: http://localhost:8501\nThe application is running in the background."
        
        # Run the command normally for non-streamlit commands
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=timeout
        )
        
        # Combine stdout and stderr
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}"
        if result.stderr:
            if output:
                output += "\n\n"
            output += f"STDERR:\n{result.stderr}"
        
        if result.returncode == 0:
            logger.info(f"Command executed successfully. Return code: {result.returncode}")
            return True, output or f"Command executed successfully (no output)"
        else:
            logger.warning(f"Command failed with return code: {result.returncode}")
            return False, f"Command failed (exit code {result.returncode}):\n{output}"
            
    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        logger.error(error_msg)
        return False, error_msg
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {e}"
        logger.error(error_msg)
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error executing command: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def get_user_approval(command: str, reason: str) -> bool:
    """
    Get user approval for running a command in CLI mode.
    
    Args:
        command (str): The command to be executed
        reason (str): Reason why the AI wants to run this command
        
    Returns:
        bool: True if user approves, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"🤖 AI wants to run a command:")
    print(f"{'='*60}")
    print(f"Command: {command}")
    print(f"Reason:  {reason}")
    print(f"{'='*60}")
    import sys
    sys.stdout.flush()  # Ensure prompt is displayed immediately
    
    while True:
        try:
            response = input("Do you approve this command? [y/N/details]: ").strip().lower()
            
            if response in ['y', 'yes']:
                print("✅ Command approved by user")
                return True
            elif response in ['n', 'no', '']:
                print("❌ Command rejected by user")
                return False
            elif response in ['d', 'details', 'detail']:
                print(f"\n📋 Command Details:")
                print(f"Working Directory: {os.getcwd()}")
                print(f"Command Type: Shell command")
                print(f"Timeout: 30 seconds")
                print(f"Safety: Command will be executed with current user permissions")
                print()
                continue
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'details' for more info")
                continue
                
        except KeyboardInterrupt:
            print("\n❌ Command rejected by user (interrupted)")
            return False
        except EOFError:
            print("\n❌ Command rejected by user (EOF)")
            return False

def get_streamlit_approval(command: str, reason: str, shared_data: dict) -> tuple[bool, str]:
    """
    Streamlit approval - stores command and waits indefinitely for user approval.
    """
    # Store command for Streamlit UI to handle
    shared_data["pending_command"] = {
        "command": command,
        "reason": reason,
        "timestamp": time.time(),
        "status": "pending"
    }
    
    # Wait indefinitely until user approves or rejects
    while True:
        time.sleep(0.5)  # Check every 500ms
        
        pending_cmd = shared_data.get("pending_command", {})
        status = pending_cmd.get("status", "pending")
        
        if status == "approved":
            # Command approved - clean up and return success
            final_command = pending_cmd.get("final_command", command)
            shared_data.pop("pending_command", None)
            return True, final_command
        elif status == "rejected":
            # Command rejected - clean up and return failure
            shared_data.pop("pending_command", None)
            return False, "Command rejected by user"
        
        # Still pending - continue waiting

def execute_approved_command(command: str, working_dir: str = None) -> Tuple[bool, str]:
    """
    Execute a pre-approved command (for Streamlit use after user clicks approve)
    """
    return run_command(command, working_dir)