import streamlit as st
import os
import logging
import threading
import queue
import time
import io
import json
from typing import Dict, Any, List
from datetime import datetime

# Custom logging handler to capture logs
class StreamlitLogHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.log_queue.put(log_entry)
        except Exception:
            self.handleError(record)

# Mock flow system for when pocketflow isn't available
class MockFlow:
    def run(self, shared):
        logger = logging.getLogger('coding_agent')
        logger.info("Starting mock coding agent flow...")
        
        # Simulate some processing
        time.sleep(1)
        logger.info(f"Processing query: {shared['user_query']}")
        
        time.sleep(0.5)
        logger.info(f"Working directory: {shared['working_dir']}")
        
        time.sleep(1)
        logger.info("Analyzing request...")
        
        time.sleep(1.5)
        logger.info("Generating response...")
        
        # Mock response
        shared["response"] = f"""I've analyzed your request: "{shared['user_query']}"

Based on the working directory: {shared['working_dir']}

This is a mock response since the pocketflow module is not available. 
The actual system would:
1. Analyze your code request
2. Use appropriate tools (read_file, grep_search, etc.)
3. Make necessary changes
4. Provide detailed feedback

Mock processing completed successfully!"""
        
        time.sleep(0.5)
        logger.info("✅ Response generated successfully")

def get_flow():
    """Get the coding agent flow, with fallback to mock"""
    try:
        from flow import coding_agent_flow
        return coding_agent_flow
    except ImportError:
        st.warning("⚠️ PocketFlow not available - using mock mode for demonstration")
        return MockFlow()

def setup_logging(log_queue):
    """Setup logging to capture both console and streamlit logs"""
    # Clear existing handlers
    logging.getLogger().handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create custom handler for Streamlit
    streamlit_handler = StreamlitLogHandler(log_queue)
    streamlit_handler.setLevel(logging.INFO)
    streamlit_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(streamlit_handler)
    
    # Suppress third-party library logs
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)

def run_agent_flow(shared_data, log_queue):
    """Run the agent flow in a separate thread"""
    try:
        setup_logging(log_queue)
        flow = get_flow()
        flow.run(shared_data)
    except Exception as e:
        logger = logging.getLogger('coding_agent')
        logger.error(f"❌ Error running flow: {str(e)}")
        shared_data["error"] = str(e)

def main():
    st.set_page_config(
        page_title="🤖 AI Coding Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🤖 AI Coding Agent - Chat Interface")
    st.markdown("*AI-powered coding assistant with persistent conversation memory*")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Working directory selection
        default_dir = os.getcwd()
        working_dir = st.text_input(
            "📁 Working Directory",
            value=default_dir,
            help="Directory where the agent will operate"
        )
        
        # Validate directory
        if working_dir and os.path.exists(working_dir):
            st.success(f"✅ Directory exists")
            
            # Show directory contents
            try:
                contents = os.listdir(working_dir)
                st.write(f"📋 **Contents ({len(contents)} items):**")
                for item in contents[:10]:  # Show first 10 items
                    if os.path.isdir(os.path.join(working_dir, item)):
                        st.write(f"📁 {item}")
                    else:
                        st.write(f"📄 {item}")
                if len(contents) > 10:
                    st.write(f"... and {len(contents) - 10} more items")
            except PermissionError:
                st.warning("⚠️ Permission denied reading directory")
        elif working_dir:
            st.error(f"❌ Directory not found: `{working_dir}`")
        
        st.divider()
        
        # Chat controls
        st.header("💬 Chat Controls")
        
        # New chat button
        if st.button("🆕 New Chat", type="primary", use_container_width=True, help="Start a new conversation and clear history"):
            st.session_state.conversation_history = []
            st.session_state.logs = []
            st.session_state.response = None
            st.session_state.error = None
            st.session_state.processing = False
            st.session_state.input_key_counter += 1  # Force new input widget
            st.rerun()
        
        # Show conversation stats
        if 'conversation_history' in st.session_state and st.session_state.conversation_history:
            st.write(f"📊 **Current Chat:**")
            st.write(f"• {len(st.session_state.conversation_history)} exchanges")
            st.write(f"• Started: {st.session_state.conversation_history[0]['timestamp'][:19]}")
            
            # Export chat option
            if st.button("💾 Export Chat", help="Download chat history as JSON"):
                chat_export = {
                    "working_directory": working_dir,
                    "chat_history": st.session_state.conversation_history,
                    "exported_at": datetime.now().isoformat()
                }
                st.download_button(
                    "📥 Download Chat History",
                    data=json.dumps(chat_export, indent=2),
                    file_name=f"ai_chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    # Initialize session state
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    if 'response' not in st.session_state:
        st.session_state.response = None
    if 'error' not in st.session_state:
        st.session_state.error = None
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    if 'current_query' not in st.session_state:
        st.session_state.current_query = ""
    if 'input_key_counter' not in st.session_state:
        st.session_state.input_key_counter = 0
    if 'command_approval_counter' not in st.session_state:
        st.session_state.command_approval_counter = 0
    
    # Main chat interface
    st.header("💬 Conversation")
    
    # Display conversation history
    if st.session_state.conversation_history:
        for i, exchange in enumerate(st.session_state.conversation_history):
            # User message
            with st.container():
                st.markdown(f"**🙋 You:** {exchange['user_query']}")
                
                # AI response  
                with st.container():
                    st.markdown(f"**🤖 Assistant:**")
                    # Parse and display response nicely
                    response_text = exchange['response']
                    
                    if "```" in response_text:
                        parts = response_text.split("```")
                        for j, part in enumerate(parts):
                            if j % 2 == 0:  # Regular text
                                if part.strip():
                                    st.markdown(part.strip())
                            else:  # Code block
                                # Try to detect language
                                lines = part.strip().split('\n')
                                if lines and not lines[0].strip().startswith('{'):
                                    # First line might be language
                                    lang = lines[0].strip()
                                    code = '\n'.join(lines[1:])
                                    st.code(code, language=lang if lang in ['python', 'json', 'bash', 'javascript'] else 'text')
                                else:
                                    st.code(part.strip())
                    else:
                        st.markdown(response_text)
                
                # Metadata
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"⏰ {exchange['timestamp'][:19]} • 🔧 {exchange['actions_taken']} actions")
                with col2:
                    if st.button("🗑️", key=f"delete_{i}", help="Remove this exchange"):
                        st.session_state.conversation_history.pop(i)
                        st.rerun()
                
                st.divider()
    else:
        st.info("👋 Welcome! Ask me anything about your codebase. I can read files, search code, make edits, and more!")
    
    # Current processing status
    if st.session_state.processing:
        st.container(border=True).info("🤔 AI is thinking... Please wait.")
    
    # Input area - only show when NOT processing
    if not st.session_state.processing:
        # Use a form to enable proper keyboard shortcuts
        with st.form(key=f"chat_form_{st.session_state.input_key_counter}", clear_on_submit=True):
            st.markdown("### 💭 Ask the AI Assistant")
            
            # Query input with dynamic key to force refresh
            user_query = st.text_area(
                "What would you like me to help you with?",
                placeholder="e.g., 'Find all TODO comments in Python files', 'Add error handling to main.py', 'Show me the project structure'",
                help="💡 Tip: Use Cmd+Enter (Mac) or Ctrl+Enter (PC) to submit",
                height=80,
                key=f"query_input_{st.session_state.input_key_counter}"  # Dynamic key
            )
            
            # Submit button
            col1, col2 = st.columns([3, 1])
            with col2:
                submit_button = st.form_submit_button(
                    "🚀 Send", 
                    type="primary", 
                    use_container_width=True
                )
            with col1:
                if not working_dir or not os.path.exists(working_dir):
                    st.error("❌ Please specify a valid working directory in the sidebar")
                elif not user_query.strip():
                    st.caption("💡 Enter your question above and click Send or press Cmd/Ctrl+Enter")
                else:
                    st.caption("💡 Press Cmd+Enter (Mac) or Ctrl+Enter (PC) to send")
    else:
        # Define variables for processing section
        user_query = ""
        submit_button = False
    
    # Process request
    if submit_button and user_query.strip():
        if not working_dir or not os.path.exists(working_dir):
            st.error("❌ Please specify a valid working directory in the sidebar")
            st.stop()
            
        # Store the query and start processing
        st.session_state.current_query = user_query.strip()
        st.session_state.processing = True
        st.session_state.logs = []
        st.session_state.response = None
        st.session_state.error = None
        st.rerun()
    
    # Show processing interface if currently processing
    if st.session_state.processing:
        # Initialize shared data and thread if not exists
        if 'processing_thread' not in st.session_state:
            # Create shared data for the current processing
            st.session_state.shared_data = {
                "user_query": st.session_state.current_query,
                "working_dir": working_dir,
                "history": [],
                "conversation_history": st.session_state.conversation_history,
                "response": None,
                "error": None,
                "mode": "streamlit"  # Indicate Streamlit mode
            }
            
            # Create log queue and start processing  
            st.session_state.log_queue = queue.Queue()
            
            # Start agent in separate thread
            st.session_state.processing_thread = threading.Thread(
                target=run_agent_flow,
                args=(st.session_state.shared_data, st.session_state.log_queue),
                daemon=True
            )
            st.session_state.processing_thread.start()
            st.session_state.processing_start_time = time.time()
        
        # Get current thread and data
        agent_thread = st.session_state.processing_thread
        shared_data = st.session_state.shared_data
        log_queue = st.session_state.log_queue
        
        # Check for timeout
        if time.time() - st.session_state.processing_start_time > 120:  # 2 minutes timeout
            st.error("⏰ Process timed out after 2 minutes")
            st.session_state.processing = False
            st.rerun()
        
        # Check for pending command approval (BEFORE processing logs)
        pending_command = shared_data.get("pending_command")
        if pending_command:
            st.warning(f"🤖 AI wants to run: `{pending_command['command']}`")
            
            with st.container(border=True):
                st.markdown("### 🔧 Command Approval Required")
                st.markdown(f"**Command:** `{pending_command['command']}`")
                st.markdown(f"**Reason:** {pending_command['reason']}")
                st.markdown(f"**Working Directory:** {working_dir}")
                
                # Approval buttons 
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("✅ Approve", type="primary", use_container_width=True, key="approve_cmd"):
                        command = pending_command['command']
                        
                        # Special handling for Streamlit commands to prevent conflicts
                        if "streamlit run" in command.lower():
                            # Clear pending command first
                            shared_data.pop("pending_command", None)
                            
                            # Extract the file path from the streamlit command
                            parts = command.split("streamlit run", 1)
                            if len(parts) > 1:
                                file_path = parts[1].strip()
                                full_path = os.path.join(working_dir, file_path) if not os.path.isabs(file_path) else file_path
                                
                                # Show special message for Streamlit apps
                                st.success("✅ Streamlit command approved!")
                                st.info(f"📋 **Instructions:**")
                                st.markdown(f"""
                                To run your Streamlit app, please open a **new terminal** and run:
                                ```bash
                                cd {working_dir}
                                {command}
                                ```
                                
                                Or run it directly:
                                ```bash
                                streamlit run {full_path}
                                ```
                                
                                ⚠️ **Note:** Running Streamlit from within this interface would conflict with the current session.
                                The app will open in your browser at `http://localhost:8501` (or the next available port).
                                """)
                            else:
                                st.warning("⚠️ Could not parse Streamlit command properly")
                        else:
                            # Execute non-Streamlit commands normally
                            from utils.run_command import execute_approved_command
                            success, output = execute_approved_command(command, working_dir)
                            
                            # Clear pending command
                            shared_data.pop("pending_command", None)
                            
                            # Show result
                            if success:
                                st.success(f"✅ Command executed successfully!")
                                if output:
                                    st.code(output, language="text")
                            else:
                                st.error(f"❌ Command failed: {output}")
                        
                        # Don't rerun immediately - let the processing continue
                        return
                
                with col2:
                    if st.button("❌ Reject", type="secondary", use_container_width=True, key="reject_cmd"):
                        # Clear pending command
                        shared_data.pop("pending_command", None)
                        st.error("❌ Command rejected!")
                        # Don't rerun immediately - let the processing continue
                        return
                
                with col3:
                    st.caption("⚠️ Only approve commands you understand and trust")
            
            # Show processing status while waiting for approval
            st.info("⏳ Waiting for command approval...")
            return
        
        # Process new log entries (only if no pending command)
        new_logs = []
        try:
            while True:
                log_entry = log_queue.get_nowait()
                new_logs.append(log_entry)
                st.session_state.logs.append(log_entry)
        except queue.Empty:
            pass
        
        # Show processing logs
        with st.expander("📝 Processing Logs", expanded=True):
            if st.session_state.logs:
                # Show recent logs in a code block
                recent_logs = st.session_state.logs[-15:]  # Show last 15 entries
                log_text = "\n".join(recent_logs)
                st.code(log_text, language="text")
            
            # Show status
            if agent_thread.is_alive():
                st.info(f"🔄 Processing... ({len(st.session_state.logs)} log entries)")
                # Auto-refresh every 2 seconds instead of 0.5 seconds
                time.sleep(2)
                st.rerun()
            else:
                st.success(f"✅ Processing complete!")
                
                # Get final response
                final_response = shared_data.get("response")
                st.session_state.response = final_response
                st.session_state.error = shared_data.get("error")
                st.session_state.processing = False
                
                # Clean up processing state
                del st.session_state.processing_thread
                del st.session_state.shared_data
                del st.session_state.log_queue
                del st.session_state.processing_start_time
                
                # Add to conversation history if we got a response
                if final_response:
                    st.session_state.conversation_history.append({
                        "user_query": st.session_state.current_query,
                        "response": final_response,
                        "timestamp": datetime.now().isoformat(),
                        "actions_taken": len(shared_data.get("history", []))
                    })
                
                # Clear the current query and increment input counter
                st.session_state.current_query = ""
                st.session_state.input_key_counter += 1
                
                # Final rerun to show the updated conversation
                st.rerun()
    
    # Show detailed logs if available
    if st.session_state.logs and not st.session_state.processing:
        with st.expander("📜 View Processing Logs", expanded=False):
            # Option to download logs
            log_text = "\n".join(st.session_state.logs)
            st.download_button(
                "📥 Download Logs",
                log_text,
                file_name=f"coding_agent_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
            
            st.code(log_text, language="text")
    
    # Footer
    st.markdown("---")
    st.markdown("*Built with ❤️ using Streamlit and AI*")

if __name__ == "__main__":
    main()