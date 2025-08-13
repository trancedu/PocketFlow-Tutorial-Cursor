from anthropic import Anthropic
import os
import logging
import json
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global logger variable and initialization flag
logger = None
_logger_initialized = False

def _ensure_logger_initialized():
    """Initialize logger only when first needed (lazy initialization)."""
    global logger, _logger_initialized
    
    if _logger_initialized:
        return
    
    # Configure logging directory
    log_directory = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_directory, exist_ok=True)
    
    # Use per-run timestamped file (to seconds) - only when actually needed
    log_file = os.path.join(log_directory, f"llm_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    # Set up logger
    logger = logging.getLogger("llm_logger")
    logger.setLevel(logging.DEBUG)  # Allow all levels
    logger.propagate = False  # Prevent propagation to root logger to avoid duplicates
    
    # Only add handlers if they don't already exist
    if not logger.handlers:
        # Console handler - show INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)
        
        # File handler - save DEBUG and above
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    _logger_initialized = True

# Simple cache configuration
cache_file = "llm_cache.json"

# Learn more about calling the LLM: https://the-pocket.github.io/PocketFlow/utility_function/llm.html
def call_llm(
    prompt: str,
    use_cache: bool = True,
    use_thinking: bool = False,
    caller: Optional[str] = None,
) -> str:
    """Call the LLM and log prompt/response with optional caller context."""
    # Ensure logger is initialized before use
    _ensure_logger_initialized()
    
    caller_tag = caller or "unknown"
    # Log the prompt with caller context
    logger.debug(f"PROMPT [{caller_tag}]: {prompt}")
    
    # Check cache if enabled
    if use_cache:
        # Load cache from disk
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
            except:
                logger.warning(f"Failed to load cache, starting with empty cache")
        
        # Return from cache if exists
        if prompt in cache:
            logger.debug(f"Cache hit [{caller_tag}] for prompt: {prompt[:50]}...")
            return cache[prompt]
    
    # Call the LLM if not in cache or cache disabled
    client = Anthropic(
        api_key=os.getenv("CLAUDE_API_KEY")
    )
    # Prepare message parameters
    message_params = {
        "max_tokens": 20000,
        "messages": [{"role": "user", "content": prompt}],
        "model": "claude-sonnet-4-20250514"
    }
    
    # Add thinking if enabled
    if use_thinking:
        message_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": 16000
        }
    
    response = client.messages.create(**message_params)
    
    # Extract response text based on whether thinking is enabled
    if use_thinking:
        response_text = response.content[1].text  # With thinking, response is at index 1
    else:
        response_text = response.content[0].text  # Without thinking, response is at index 0
    
    # Log the response
    logger.info(f"RESPONSE [{caller_tag}]: {response_text}")
    
    # Update cache if enabled
    if use_cache:
        # Load cache again to avoid overwrites
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
            except:
                pass
        
        # Add to cache and save
        cache[prompt] = response_text
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache, f)
            logger.info(f"Added to cache [{caller_tag}]")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    return response_text

def clear_cache() -> None:
    """Clear the cache file if it exists."""
    # Ensure logger is initialized before use
    _ensure_logger_initialized()
    
    if os.path.exists(cache_file):
        os.remove(cache_file)
        logger.info("Cache cleared")

if __name__ == "__main__":
    test_prompt = "Hello, how are you?"
    
    # First call - should hit the API with thinking enabled
    print("Making first call with thinking...")
    response1 = call_llm(test_prompt, use_cache=False, use_thinking=True)
    print(f"Response: {response1}")
    
    # Second call - without thinking
    print("\nMaking second call without thinking...")
    response2 = call_llm(test_prompt, use_cache=False, use_thinking=False)
    print(f"Response: {response2}")
    
    # Third call - should hit cache (default: no thinking)
    print("\nMaking third call with cache (default behavior)...")
    response3 = call_llm(test_prompt, use_cache=True)
    print(f"Response: {response3}")
