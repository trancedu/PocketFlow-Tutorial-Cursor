import streamlit as st
import os
import logging
import threading
import queue
import time
import io
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
    
    st.title("🤖 AI Coding Agent")
    st.markdown("*AI-powered coding assistant with real-time logging*")
    
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
            st.success(f"✅ Directory exists: `{working_dir}`")
            
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
    
    # Main interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("💬 Your Request")
        
        # Query input
        user_query = st.text_area(
            "What would you like me to help you with?",
            placeholder="e.g., 'Find all TODO comments in Python files', 'Add error handling to main.py', 'Show me the project structure'",
            height=100
        )
        
        # Submit button
        submit_button = st.button("🚀 Run Agent", type="primary", use_container_width=True)
    
    with col2:
        st.header("📊 Agent Status")
    
    # Initialize session state (moved outside columns)
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    if 'response' not in st.session_state:
        st.session_state.response = None
    if 'error' not in st.session_state:
        st.session_state.error = None
    
    # Process request
    if submit_button and user_query.strip():
        if not working_dir or not os.path.exists(working_dir):
            st.error("❌ Please specify a valid working directory")
            return
            
        # Reset state
        st.session_state.processing = True
        st.session_state.logs = []
        st.session_state.response = None
        
        # Create shared data
        shared_data = {
            "user_query": user_query.strip(),
            "working_dir": working_dir,
            "history": [],
            "response": None,
            "error": None
        }
        
        # Create log queue and start processing
        log_queue = queue.Queue()
        
        # Start agent in separate thread
        agent_thread = threading.Thread(
            target=run_agent_flow, 
            args=(shared_data, log_queue),
            daemon=True
        )
        agent_thread.start()
        
        # Real-time log display
        log_container = st.container()
        status_placeholder = st.empty()
        
        with log_container:
            st.subheader("📝 Live Logs")
            log_placeholder = st.empty()
        
        # Monitor logs and thread
        start_time = time.time()
        max_wait_time = 120  # 2 minutes timeout
        
        while agent_thread.is_alive() or not log_queue.empty():
            # Check timeout
            if time.time() - start_time > max_wait_time:
                st.error("⏰ Process timed out after 2 minutes")
                break
            
            # Get new log entries
            new_logs = []
            try:
                while True:
                    log_entry = log_queue.get_nowait()
                    new_logs.append(log_entry)
                    st.session_state.logs.append(log_entry)
            except queue.Empty:
                pass
            
            # Update log display
            if st.session_state.logs:
                with log_placeholder.container():
                    # Show recent logs in a code block
                    recent_logs = st.session_state.logs[-20:]  # Show last 20 entries
                    log_text = "\n".join(recent_logs)
                    st.code(log_text, language="text")
            
            # Update status
            if agent_thread.is_alive():
                status_placeholder.info(f"🔄 Processing... ({len(st.session_state.logs)} log entries)")
            else:
                status_placeholder.success(f"✅ Processing complete! ({len(st.session_state.logs)} log entries)")
            
            time.sleep(0.5)  # Update every 500ms
        
        # Get final response
        st.session_state.response = shared_data.get("response")
        st.session_state.error = shared_data.get("error")
        st.session_state.processing = False
    
    # Display results
    if st.session_state.response or st.session_state.error:
        st.header("📋 Response")
        
        if st.session_state.error:
            st.error(f"❌ Error: {st.session_state.error}")
        elif st.session_state.response:
            # Display response in a nice format
            with st.container():
                st.markdown("### 🎯 Agent Response")
                
                # Parse and display response nicely
                response_text = st.session_state.response
                
                # Check if response contains code blocks
                if "```" in response_text:
                    parts = response_text.split("```")
                    for i, part in enumerate(parts):
                        if i % 2 == 0:  # Regular text
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
    
    # Show logs below response
    if st.session_state.logs and not st.session_state.processing:
        st.header("📜 Complete Logs")
        
        with st.expander("View All Logs", expanded=False):
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