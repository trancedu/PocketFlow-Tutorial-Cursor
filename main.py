import os
import argparse
import logging
from datetime import datetime
from flow import coding_agent_flow

# Set up logging with separate console and file handlers
logger_root = logging.getLogger()
logger_root.setLevel(logging.DEBUG)  # Allow all levels

# Clear any existing handlers to avoid duplicates
logger_root.handlers.clear()

# Console handler - show INFO and above
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# File handler - save DEBUG and above  
file_handler = logging.FileHandler('coding_agent.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Add handlers to root logger
logger_root.addHandler(console_handler)
logger_root.addHandler(file_handler)

# Suppress debug messages from third-party libraries
logging.getLogger("anthropic").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)
# Ensure run_command logger shows all INFO and ERROR messages
logging.getLogger("run_command").setLevel(logging.INFO)

logger = logging.getLogger('main')

def main():
    """
    Run the coding agent to help with code operations
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Coding Agent - AI-powered coding assistant')
    parser.add_argument('--query', '-q', type=str, help='User query to process', required=False)
    parser.add_argument('--working-dir', '-d', type=str, default=os.getcwd(), 
                        help='Working directory for file operations (default: current directory)')
    parser.add_argument('--cli', action='store_true', help='Use command-line interface instead of Streamlit')
    args = parser.parse_args()
    
    # Default to Streamlit interface unless --cli is specified
    if not args.cli:
        import subprocess
        import sys
        print("🚀 Starting Streamlit interface...")
        print("💡 Use --cli flag to use command-line interface instead")
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])
        except KeyboardInterrupt:
            print("\n👋 Streamlit interface closed")
        return
    
    # CLI mode - continuous conversation
    logger.info(f"Working directory: {args.working_dir}")
    print(f"🤖 AI Coding Agent - CLI Mode")
    print(f"📁 Working directory: {args.working_dir}")
    print(f"💡 Type 'quit', 'exit', or 'bye' to end the session")
    print(f"=" * 50)
    
    # Initialize persistent shared memory for conversation
    conversation_history = []
    
    # If query provided via command line, use it for first question
    initial_query = args.query
    
    while True:
        try:
            # Get user query
            if initial_query:
                user_query = initial_query
                initial_query = None  # Only use once
                print(f"User: {user_query}")
            else:
                user_query = input("\n💬 You: ").strip()
            
            # Check for exit commands
            if user_query.lower() in ['quit', 'exit', 'bye', 'q']:
                print("👋 Goodbye!")
                break
            
            if not user_query:
                print("❓ Please enter a question or request.")
                continue
            
            print(f"🤔 Processing your request...")
            
            # Initialize shared memory for this query (but preserve conversation history)
            shared = {
                "user_query": user_query,
                "working_dir": args.working_dir,
                "history": [],  # Fresh history for current query processing
                "conversation_history": conversation_history,  # Persistent conversation history
                "response": None,
                "mode": "cli"  # Indicate CLI mode
            }
            
            # Run the flow
            coding_agent_flow.run(shared)
            
            # Display the response
            response = shared.get("response", "No response generated.")
            print(f"\n🤖 Assistant: {response}")
            
            # Add this exchange to conversation history
            conversation_history.append({
                "user_query": user_query,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "actions_taken": len(shared.get("history", []))
            })
            
        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(f"Error in main loop: {e}")
            continue

if __name__ == "__main__":
    main()