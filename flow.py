from pocketflow import Node, Flow, BatchNode
import os
import json  # Add JSON support
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Import utility functions
from utils.call_llm import call_llm
from utils.read_file import read_file
from utils.delete_file import delete_file
from utils.replace_file import replace_file
from utils.search_ops import grep_search
from utils.dir_ops import list_dir
from utils.run_command import run_command, get_user_approval, get_streamlit_approval
from utils.context_manager import ContextManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('coding_agent.log')
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger('coding_agent')

context_manager = ContextManager()

#############################################
# Main Decision Agent Node
#############################################
class MainDecisionAgent(Node):
    def prep(self, shared: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        # Get user query and history
        user_query = shared.get("user_query", "")
        history = shared.get("history", [])
        
        # Store conversation history in instance for access in exec
        self._conversation_history = shared.get("conversation_history", [])
        
        return user_query, history
    
    def exec(self, inputs: Tuple[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        user_query, history = inputs
        logger.info(f"MainDecisionAgent: Analyzing user query: {user_query}")

        # Use context manager to get optimized history
        history_str = context_manager.get_contextual_history(history, user_query)
        
        # Get conversation history from shared state if available
        conversation_history = getattr(self, '_conversation_history', [])
        
        # Format conversation history for context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n\nPrevious conversation context:\n"
            # Show last 3 conversations for context
            recent_conversations = conversation_history[-3:]
            for i, conv in enumerate(recent_conversations):
                conversation_context += f"\nPrevious Query {i+1}: {conv['user_query']}\n"
                conversation_context += f"Previous Response {i+1}: {conv['response'][:200]}{'...' if len(conv['response']) > 200 else ''}\n"
        
        # Create prompt for the LLM using JSON format
        prompt = f"""You are a coding assistant that helps modify and navigate code. Given the following request, 
decide which tool to use from the available options.

User request: {user_query}

Here are the actions you performed for this current request:
history_str: {history_str}
conversation_context: {conversation_context}

Available tools:
1. read_file: Read content from a file
   - Parameters: target_file (path)
   - Example:
     tool: read_file
     reason: I need to read the main.py file to understand its structure
     params:
       target_file: main.py

2. edit_file: Make changes to a file
   - Parameters: target_file (path), instructions, code_edit
   - Code_edit_instructions:
       - The code changes with context, following these rules:
       - Use "// ... existing code ..." to represent unchanged code between edits
       - Include sufficient context around the changes to resolve ambiguity
       - Minimize repeating unchanged code
       - Never omit code without using the "// ... existing code ..." marker
       - No need to specify line numbers - the context helps locate the changes
   - Example:
     tool: edit_file
     reason: I need to add error handling to the file reading function
     params:
       target_file: utils/read_file.py
       instructions: Add try-except block around the file reading operation
       code_edit: |
            // ... existing file reading code ...
            function newEdit() {{
                // new code here
            }}
            // ... existing file reading code ...

3. delete_file: Remove a file
   - Parameters: target_file (path)
   - Example:
     tool: delete_file
     reason: The temporary file is no longer needed
     params:
       target_file: temp.txt

4. grep_search: Search for patterns in files
   - Parameters: query, case_sensitive (optional), include_pattern (optional), exclude_pattern (optional)
   - Example:
     tool: grep_search
     reason: I need to find all occurrences of 'logger' in Python files
     params:
       query: logger
       include_pattern: "*.py"
       case_sensitive: false

5. list_dir: List contents of a directory
   - Parameters: relative_workspace_path
   - Example:
     tool: list_dir
     reason: I need to see all files in the utils directory
     params:
       relative_workspace_path: utils
   - Result: Returns a tree visualization of the directory structure

6. run_command: Execute a shell command (requires user approval)
   - Parameters: command, reason
   - Use ONLY when other tools cannot satisfy the requirement
   - Requires explicit user approval before execution
   - Example:
     tool: run_command
     reason: I need to install a Python package that is required for the project
     params:
       command: pip install requests
       reason: The code requires the requests library but it's not installed

7. finish: End the process and provide final response
   - Parameters: final_response (required) - The complete final response to the user
   - Example:
     tool: finish
     reason: I have completed the requested task of finding all logger instances
     params: {{
       "final_response": "I found 3 logger instances in your codebase: one in main.py at line 15, one in utils/logging.py at line 8, and one in flow.py at line 28. All are properly configured."
     }}

Respond with a JSON object containing:
```json
{{
  "tool": "one of: read_file, edit_file, delete_file, grep_search, list_dir, run_command, finish",
  "reason": "detailed explanation of why you chose this tool and what you intend to do. If you chose finish, explain why no more actions are needed. If you chose run_command, explain why other tools cannot satisfy the requirement and what the command will accomplish.",
  "params": {{
    "parameter_name": "parameter_value"
  }}
}}
```

IMPORTANT: Ensure proper JSON indentation in your response. When including code examples in the reason field, maintain correct indentation within the JSON string. Consider the previous conversation context when making decisions.

If you believe no more actions are needed, use "finish" as the tool and explain why in the reason. For the finish tool, you MUST provide a comprehensive final_response parameter that summarizes what you accomplished, what was found or modified, and any next steps the user might want to take. This final_response should be written directly to the user as if you are speaking to them.

Use "run_command" ONLY as a last resort when other tools cannot accomplish the task.
"""
        
        # Call LLM to decide action
        response = call_llm(prompt, caller="MainDecisionAgent.exec")

        # Extract JSON from response using more robust parsing
        json_content = self._extract_json_from_response(response)
        
        if json_content:
            decision = json.loads(json_content)
            
            # Validate the required fields
            assert "tool" in decision, "Tool name is missing"
            assert "reason" in decision, "Reason is missing"
            
            # Validate parameters based on tool type
            if decision["tool"] == "finish":
                assert "params" in decision, "Parameters are missing for finish tool"
                assert "final_response" in decision["params"], "final_response parameter is required for finish tool"
            else:
                assert "params" in decision, "Parameters are missing"
            
            return decision
        else:
            raise ValueError("No JSON object found in response")
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response. The LLM typically wraps JSON in ```json blocks.
        Use greedy matching to get the longest/last ``` to handle nested backticks.
        """
        import re
        
        # Use greedy matching (.*) instead of lazy (.*?) to match to the LAST ```
        json_pattern = r'```json\s*(.*)\s*```'
        match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Fallback: try to find any JSON-like structure
        response_stripped = response.strip()
        if response_stripped.startswith('{') and response_stripped.endswith('}'):
            return response_stripped
        
        return ""
    
    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Dict[str, Any]) -> str:
        logger.info(f"MainDecisionAgent: Selected tool: {exec_res['tool']}")
        
        # Initialize history if not present
        if "history" not in shared:
            shared["history"] = []
        
        # Add this action to history
        shared["history"].append({
            "tool": exec_res["tool"],
            "reason": exec_res["reason"],
            "params": exec_res.get("params", {}),
            "result": None,  # Will be filled in by action nodes
            "timestamp": datetime.now().isoformat()
        })
        
        # Return the action to take
        return exec_res["tool"]

#############################################
# Read File Action Node
#############################################
class ReadFileAction(Node):
    def prep(self, shared: Dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        file_path = last_action["params"].get("target_file")
        
        if not file_path:
            raise ValueError("Missing target_file parameter")
        
        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, file_path) if working_dir else file_path
        
        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"ReadFileAction: {reason}")
        
        return full_path
    
    def exec(self, file_path: str) -> Tuple[str, bool]:
        # Call read_file utility which returns a tuple of (content, success)
        return read_file(file_path)
    
    def post(self, shared: Dict[str, Any], prep_res: str, exec_res: Tuple[str, bool]) -> str:
        # Unpack the tuple returned by read_file()
        content, success = exec_res
        
        # Add file content to context manager for deduplication
        if success and content:
            content_info = context_manager.add_file_content(prep_res, content)
            
            # Update the result in the last history entry
            history = shared.get("history", [])
            if history:
                history[-1]["result"] = {
                    "success": success,
                    "content_info": content_info
                }
        else:
            # Update the result in the last history entry
            history = shared.get("history", [])
            if history:
                history[-1]["result"] = {
                    "success": success,
                    # store error in message to surface clearly in summaries
                    "message": content
                }

#############################################
# Grep Search Action Node
#############################################
class GrepSearchAction(Node):
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        params = last_action["params"]
        
        if "query" not in params:
            raise ValueError("Missing query parameter")
        
        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"GrepSearchAction: {reason}")
        
        # Ensure paths are relative to working directory
        working_dir = shared.get("working_dir", "")
        
        return {
            "query": params["query"],
            "case_sensitive": params.get("case_sensitive", False),
            "include_pattern": params.get("include_pattern"),
            "exclude_pattern": params.get("exclude_pattern"),
            "working_dir": working_dir
        }
    
    def exec(self, params: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        # Use current directory if not specified
        working_dir = params.pop("working_dir", "")
        
        # Call grep_search utility which returns (success, matches)
        return grep_search(
            query=params["query"],
            case_sensitive=params.get("case_sensitive", False),
            include_pattern=params.get("include_pattern"),
            exclude_pattern=params.get("exclude_pattern"),
            working_dir=working_dir
        )
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Tuple[bool, List[Dict[str, Any]]]) -> str:
        matches, success = exec_res
        
        # Update the result in the last history entry
        history = shared.get("history", [])
        if history:
            history[-1]["result"] = {
                "success": success,
                "matches": matches
            }

#############################################
# List Directory Action Node
#############################################
class ListDirAction(Node):
    def prep(self, shared: Dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        path = last_action["params"].get("relative_workspace_path", ".")
        
        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"ListDirAction: {reason}")
        
        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, path) if working_dir else path
        
        return full_path
    
    def exec(self, path: str) -> Tuple[bool, str]:        
        # Call list_dir utility which now returns (success, tree_str)
        success, tree_str = list_dir(path)
        
        return success, tree_str
    
    def post(self, shared: Dict[str, Any], prep_res: str, exec_res: Tuple[bool, str]) -> str:
        success, tree_str = exec_res
        
        # Update the result in the last history entry with the new structure
        history = shared.get("history", [])
        if history:
            history[-1]["result"] = {
                "success": success,
                "tree_visualization": tree_str
            }

#############################################
# Delete File Action Node
#############################################
class DeleteFileAction(Node):
    def prep(self, shared: Dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        file_path = last_action["params"].get("target_file")
        
        if not file_path:
            raise ValueError("Missing target_file parameter")
        
        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"DeleteFileAction: {reason}")
        
        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, file_path) if working_dir else file_path
        
        return full_path
    
    def exec(self, file_path: str) -> Tuple[bool, str]:
        # Call delete_file utility which returns (success, message)
        return delete_file(file_path)
    
    def post(self, shared: Dict[str, Any], prep_res: str, exec_res: Tuple[bool, str]) -> str:
        success, message = exec_res

        # Update the result in the last history entry
        history = shared.get("history", [])
        if history:
            history[-1]["result"] = {
                "success": success,
                "message": message
            }

#############################################
# Run Command Action Node
#############################################
class RunCommandAction(Node):
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        command = last_action["params"].get("command")
        reason = last_action["params"].get("reason", last_action.get("reason", ""))
        
        if not command:
            raise ValueError("Missing command parameter")
        
        # Use the reason for logging
        logger.info(f"RunCommandAction: {reason}")
        
        # Get working directory
        working_dir = shared.get("working_dir", "")
        
        return {
            "command": command,
            "reason": reason,
            "working_dir": working_dir,
            "shared_data": shared  # Pass shared data for Streamlit detection
        }
    
    def exec(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        command = params["command"]
        reason = params["reason"]
        working_dir = params["working_dir"]
        shared_data = params.get("shared_data")  # Pass shared data for Streamlit mode
        
        # Detect if we're in CLI mode by checking the mode indicator
        mode = shared_data.get("mode", "streamlit") if shared_data else "streamlit"
        original_command = command
        
        if mode == "cli":
            # CLI mode - use console approval
            if not get_user_approval(command, reason):
                return False, "Command execution rejected by user"
        else:
            # Streamlit mode - use UI approval
            approved, final_command = get_streamlit_approval(command, reason, shared_data)
            if not approved:
                return False, "Command execution rejected by user"
            # Use the potentially modified command
            command = final_command
        
        # Store modification info in shared data if command was changed
        if command != original_command:
            shared_data["command_modification"] = {
                "original": original_command,
                "executed": command
            }
        
        # Execute the command
        return run_command(command, working_dir)
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Tuple[bool, str]) -> str:
        success, output = exec_res
        
        # Update the result in the last history entry
        history = shared.get("history", [])
        if history:
            # Check if command was modified
            modification_info = shared.get("command_modification")
            if modification_info:
                executed_command = modification_info["executed"]
                original_command = modification_info["original"]
            else:
                executed_command = prep_res["command"]
                original_command = None
            
            history[-1]["result"] = {
                "success": success,
                "output": output,
                "command": executed_command,
                "original_command": original_command
            }
        
        # If the command was successful and appears to be a long-running service (like streamlit run),
        # For server/streamlit commands, generate a completion response
        command = prep_res.get("command", "")
        if success and ("streamlit run" in command.lower() or "serve" in command.lower() or "server" in command.lower()):
            # Create a final response for the server startup
            final_response = f"✅ Successfully executed: `{command}`\n\nThe server should now be running. You can access your application in your web browser at the URL shown in the output above."
            shared["response"] = final_response
            return "done"
        
        # For other commands, continue normal flow
        return ""

#############################################
# Read Target File Node (Edit Agent)
#############################################
class ReadTargetFileNode(Node):
    def prep(self, shared: Dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        file_path = last_action["params"].get("target_file")
        
        if not file_path:
            raise ValueError("Missing target_file parameter")
        
        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, file_path) if working_dir else file_path
        
        return full_path
    
    def exec(self, file_path: str) -> Tuple[str, bool]:
        # Call read_file utility which returns (content, success)
        return read_file(file_path)
    
    def post(self, shared: Dict[str, Any], prep_res: str, exec_res: Tuple[str, bool]) -> str:
        content, success = exec_res
        logger.info("ReadTargetFileNode: File read completed for editing")
        
        # Store file content in the history entry
        history = shared.get("history", [])
        if history:
            history[-1]["file_content"] = content
        
#############################################
# Analyze and Plan Changes Node
#############################################
class AnalyzeAndPlanNode(Node):
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # Get history
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        file_content = last_action.get("file_content")
        instructions = last_action["params"].get("instructions")
        code_edit = last_action["params"].get("code_edit")
        
        if not file_content:
            raise ValueError("File content not found")
        if not instructions:
            raise ValueError("Missing instructions parameter")
        if not code_edit:
            raise ValueError("Missing code_edit parameter")
        
        return {
            "file_content": file_content,
            "instructions": instructions,
            "code_edit": code_edit
        }
    
    def exec(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        file_content = params["file_content"]
        instructions = params["instructions"]
        code_edit = params["code_edit"]
        
        # File content as lines
        file_lines = file_content.split('\n')
        total_lines = len(file_lines)
        
        # Generate a prompt for the LLM to analyze the edit using JSON format
        prompt = f"""
As a code editing assistant, I need to convert the following code edit instruction 
and code edit pattern into specific edit operations (start_line, end_line, replacement).

FILE CONTENT:
{file_content}

EDIT INSTRUCTIONS: 
{instructions}

CODE EDIT PATTERN (markers like "// ... existing code ..." indicate unchanged code):
{code_edit}

Analyze the file content and the edit pattern to determine exactly where changes should be made. 
Be very careful with start and end lines. They are 1-indexed and inclusive. These will be REPLACED, not APPENDED!
If you want APPEND, just copy that line as the first line of the replacement.
Return a JSON object with your reasoning and an array of edit operations:

```json
{{
  "reasoning": "First explain your thinking process about how you're interpreting the edit pattern. Explain how you identified where the edits should be made in the original file. Describe any assumptions or decisions you made when determining the edit locations. You need to be very precise with the start and end lines! Reason why not 1 line before or after the start and end lines.",
  "operations": [
    {{
      "start_line": 10,
      "end_line": 15,
      "replacement": "def process_file(filename):\\n    # New implementation with better error handling\\n    try:\\n        with open(filename, 'r') as f:\\n            return f.read()\\n    except FileNotFoundError:\\n        return None"
    }},
    {{
      "start_line": 25,
      "end_line": 25,
      "replacement": "logger.info(\\"File processing completed\\")"
    }}
  ]
}}
```

CRITICAL JSON FORMATTING REQUIREMENTS:
- Use \\n for newlines in the replacement string
- Use \\" for quotes within the replacement string
- Use \\t for tabs in the replacement string
- ALL quotes inside string values MUST be escaped as \\"
- Example: "replacement": "logger.info(\\"Starting process\\")\\nresult = process_data()"
- If you have complex code with many quotes, be extra careful with escaping
Maintain proper indentation in the replacement code by including the appropriate spaces and tabs in the replacement string.

For lines that include "// ... existing code ...", do not include them in the replacement.
Instead, identify the exact lines they represent in the original file and set the line 
numbers accordingly. Start_line and end_line are 1-indexed.

If the instruction indicates content should be appended to the file, set both start_line and end_line 
to the maximum line number + 1, which will add the content at the end of the file.
"""
        
        # Call LLM to analyze
        response = call_llm(prompt, caller="AnalyzeAndPlanNode.exec")

        # Look for JSON structure in the response
        json_content = ""
        if "```json" in response:
            json_blocks = response.split("```json")
            if len(json_blocks) > 1:
                json_content = json_blocks[1].split("```")[0].strip()
        elif "```" in response:
            # Try to extract from generic code block
            json_blocks = response.split("```")
            if len(json_blocks) > 1:
                json_content = json_blocks[1].strip()
        
        if json_content:
            decision = json.loads(json_content)
            
            # Validate the required fields
            assert "reasoning" in decision, "Reasoning is missing"
            assert "operations" in decision, "Operations are missing"
            
            # Ensure operations is a list
            if not isinstance(decision["operations"], list):
                raise ValueError("Operations are not a list")
            
            # Validate operations
            for op in decision["operations"]:
                assert "start_line" in op, "start_line is missing"
                assert "end_line" in op, "end_line is missing"
                assert "replacement" in op, "replacement is missing"
                assert 1 <= op["start_line"] <= total_lines, f"start_line out of range: {op['start_line']}"
                assert 1 <= op["end_line"] <= total_lines, f"end_line out of range: {op['end_line']}"
                assert op["start_line"] <= op["end_line"], f"start_line > end_line: {op['start_line']} > {op['end_line']}"
            
            return decision
        else:
            raise ValueError("No JSON object found in response")
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        # Store reasoning and edit operations in shared
        shared["edit_reasoning"] = exec_res.get("reasoning", "")
        shared["edit_operations"] = exec_res.get("operations", [])
        


#############################################
# Apply Changes Batch Node
#############################################
class ApplyChangesNode(BatchNode):
    def prep(self, shared: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Get edit operations
        edit_operations = shared.get("edit_operations", [])
        if not edit_operations:
            logger.warning("No edit operations found")
            return []
        
        # Sort edit operations in descending order by start_line
        # This ensures that line numbers remain valid as we edit from bottom to top
        sorted_ops = sorted(edit_operations, key=lambda op: op["start_line"], reverse=True)
        
        # Get target file from history
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        target_file = last_action["params"].get("target_file")
        
        if not target_file:
            raise ValueError("Missing target_file parameter")
        
        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, target_file) if working_dir else target_file
        
        # Attach file path to each operation
        for op in sorted_ops:
            op["target_file"] = full_path
        
        return sorted_ops
    
    def exec(self, op: Dict[str, Any]) -> Tuple[bool, str]:
        # Call replace_file utility which returns (success, message)
        return replace_file(
            target_file=op["target_file"],
            start_line=op["start_line"],
            end_line=op["end_line"],
            content=op["replacement"]
        )
    
    def post(self, shared: Dict[str, Any], prep_res: List[Dict[str, Any]], exec_res_list: List[Tuple[bool, str]]) -> str:
        # Check if all operations were successful
        all_successful = all(success for success, _ in exec_res_list)
        
        # Format results for history
        result_details = [
            {"success": success, "message": message} 
            for success, message in exec_res_list
        ]
        
        # Update edit result in history
        history = shared.get("history", [])
        if history:
            history[-1]["result"] = {
                "success": all_successful,
                "operations": len(exec_res_list),
                "details": result_details,
                "reasoning": shared.get("edit_reasoning", "")
            }
        
        # Clear edit operations and reasoning after processing
        shared.pop("edit_operations", None)
        shared.pop("edit_reasoning", None)
        


#############################################
# Finish Action Node
#############################################
class FinishAction(Node):
    def prep(self, shared: Dict[str, Any]) -> str:
        # Get the final_response from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")
        
        last_action = history[-1]
        final_response = last_action["params"].get("final_response")
        
        if not final_response:
            raise ValueError("Missing final_response parameter")
        
        # Use the reason for logging
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"FinishAction: {reason}")
        
        return final_response
    
    def exec(self, final_response: str) -> str:
        # Simply return the final response as provided
        return final_response
    
    def post(self, shared: Dict[str, Any], prep_res: str, exec_res: str) -> str:
        logger.info(f"###### Final Response ######\n{exec_res}\n###### End of Response ######")
        
        # Store response in shared
        shared["response"] = exec_res
        
        # Update the result in the last history entry
        history = shared.get("history", [])
        if history:
            history[-1]["result"] = {
                "success": True,
                "message": "Task completed successfully"
            }
        
        return "done"

#############################################
# Edit Agent Flow
#############################################
def create_edit_agent() -> Flow:
    # Create nodes
    read_target = ReadTargetFileNode()
    analyze_plan = AnalyzeAndPlanNode()
    apply_changes = ApplyChangesNode()
    
    # Connect nodes using default action (no named actions)
    read_target >> analyze_plan
    analyze_plan >> apply_changes
    
    # Create flow
    return Flow(start=read_target)

#############################################
# Main Flow
#############################################
def create_main_flow() -> Flow:
    # Create nodes
    main_agent = MainDecisionAgent()
    read_action = ReadFileAction()
    grep_action = GrepSearchAction()
    list_dir_action = ListDirAction()
    delete_action = DeleteFileAction()
    run_command_action = RunCommandAction()
    edit_agent = create_edit_agent()
    finish_action = FinishAction()
    
    # Connect main agent to action nodes
    main_agent - "read_file" >> read_action
    main_agent - "grep_search" >> grep_action
    main_agent - "list_dir" >> list_dir_action
    main_agent - "delete_file" >> delete_action
    main_agent - "run_command" >> run_command_action
    main_agent - "edit_file" >> edit_agent
    main_agent - "finish" >> finish_action
    
    # Connect action nodes back to main agent using default action
    read_action >> main_agent
    grep_action >> main_agent
    list_dir_action >> main_agent
    delete_action >> main_agent
    run_command_action >> main_agent
    # run_command_action handles server commands directly with "done" return
    edit_agent >> main_agent
    
    # Create flow
    return Flow(start=main_agent)

# Create the main flow
coding_agent_flow = create_main_flow()