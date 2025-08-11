import os
import argparse
import logging
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
    
    # CLI mode - existing functionality
    # If no query provided via command line, ask for it
    user_query = args.query
    if not user_query:
        user_query = input("What would you like me to help you with? ")
    
    # Initialize shared memory
    shared = {
        "user_query": user_query,
        "working_dir": args.working_dir,
        "history": [],
        "response": None
    }
    
    logger.info(f"Working directory: {args.working_dir}")
    
    # Run the flow
    coding_agent_flow.run(shared)

if __name__ == "__main__":
    main()