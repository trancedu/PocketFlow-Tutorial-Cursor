"""
Run Command Utility for AI Coding Agent
Executes shell commands with proper error handling and output capture.
"""

import subprocess
import logging
import os
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
        
        # Run the command
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