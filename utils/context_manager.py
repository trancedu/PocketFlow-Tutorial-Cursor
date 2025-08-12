"""
Context Manager for AI History and File Content Deduplication
Manages conversation history to avoid redundant content and token waste.
"""

import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime


class ContextManager:
    def __init__(self, max_context_chars: int = 400000):
        """
        Initialize context manager.
        
        Args:
            max_context_chars: Maximum characters to include in context (default: 400k chars)
        """
        self.max_context_chars = max_context_chars
        self.file_cache = {}  # file_path -> {hash, content, first_seen}
        self.content_hashes = {}  # hash -> file_path
        
    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    
    def add_file_content(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Add file content to cache with deduplication.
        
        Returns:
            Dict with content info for history storage
        """
        content_hash = self._calculate_content_hash(content)
        
        # Check if we've seen this exact content before
        if content_hash in self.content_hashes:
            existing_path = self.content_hashes[content_hash]
            # Update access time for cache management
            if file_path in self.file_cache:
                self.file_cache[file_path]["last_accessed"] = datetime.now().isoformat()
            
            return {
                "type": "file_reference",
                "file_path": file_path,
                "content_hash": content_hash,
                "duplicate_of": existing_path,
                "size": len(content),
                "lines": content.count('\n') + 1,
            }
        
        # Check if this file path already exists but with different content
        if file_path in self.file_cache:
            old_hash = self.file_cache[file_path]["hash"]
            # Remove old hash mapping
            if old_hash in self.content_hashes:
                del self.content_hashes[old_hash]
        
        # New content - add to cache
        self.file_cache[file_path] = {
            "hash": content_hash,
            "content": content,
            "first_seen": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "size": len(content),
            "lines": content.count('\n') + 1
        }
        self.content_hashes[content_hash] = file_path
        
        return {
            "type": "file_content",
            "file_path": file_path, 
            "content_hash": content_hash,
            "content": content,
            "size": len(content),
            "lines": content.count('\n') + 1
        }
    
    def get_contextual_history(self, full_history: List[Dict[str, Any]], 
                             current_query: str) -> str:
        """
        Generate smart contextual history for AI with 400k character limit.
        
        Args:
            full_history: Complete conversation history
            current_query: Current user request
            
        Returns:
            Formatted history string optimized for context within character limits
        """
        if not full_history:
            return "No previous actions."
        
        # Build contextual summary with intelligent prioritization
        context_parts = []
        total_chars = 0
        
        # Reserve 10% of chars for current query context
        available_chars = int(self.max_context_chars * 0.9)
        
        # Priority 1: Recent actions (last 5 for larger context window)
        recent_actions = full_history[-5:] if len(full_history) >= 5 else full_history
        
        for i, action in enumerate(recent_actions, 1):
            action_summary = self._format_action_for_context(action, is_recent=True)
            action_chars = len(action_summary)
            
            if total_chars + action_chars <= available_chars:
                context_parts.append(f"Recent Action {i}:\n{action_summary}")
                total_chars += action_chars + 20  # +20 for formatting
            else:
                # Try truncated version
                truncated_summary = self._truncate_content_intelligently(action_summary, available_chars - total_chars)
                if truncated_summary:
                    context_parts.append(f"Recent Action {i}:\n{truncated_summary}")
                    total_chars += len(truncated_summary) + 20
                break
        
        # Priority 2: File state summary if relevant
        if self.file_cache and total_chars < available_chars * 0.8:
            file_summary = self._get_file_state_summary()
            file_chars = len(file_summary)
            
            if total_chars + file_chars <= available_chars:
                context_parts.insert(0, file_summary)
                total_chars += file_chars + 2
        
        # Priority 3: Relevant older actions with remaining space
        remaining_chars = available_chars - total_chars
        if remaining_chars > 5000:  # Only if significant space remains
            older_actions = full_history[:-5] if len(full_history) > 5 else []
            if older_actions:
                relevant_older = self._get_relevant_older_actions(older_actions, current_query, remaining_chars)
                for action_summary in relevant_older:
                    action_chars = len(action_summary)
                    if total_chars + action_chars <= available_chars:
                        context_parts.append(action_summary)
                        total_chars += action_chars + 2
                    else:
                        break
        
        final_context = "\n\n".join(context_parts)
        
        # Final safety check and truncation
        if len(final_context) > self.max_context_chars:
            final_context = self._truncate_context_to_limit(final_context)
            
        return final_context
    
    def _format_action_for_context(self, action: Dict[str, Any], is_recent: bool = False) -> str:
        """Format a single action for contextual display."""
        result = []
        result.append(f"- Tool: {action['tool']}")
        result.append(f"- Reason: {action['reason']}")
        
        # Add parameters
        params = action.get("params", {})
        if params:
            result.append("- Parameters:")
            for k, v in params.items():
                result.append(f"  - {k}: {v}")
        
        # Handle results with smart content management
        action_result = action.get("result")
        if action_result and isinstance(action_result, dict):
            success = action_result.get("success", False)
            if success:
                result.append(f"- Result: Success")
            else:
                # Show failure reason for better debugging
                if action['tool'] == 'run_command':
                    output = action_result.get("output", "Unknown error")
                    # Extract the first line of error for brevity
                    error_summary = output.split('\n')[0] if output else "Command failed"
                    result.append(f"- Result: Failed - {error_summary}")
                else:
                    # For other tools, try to get error message (fallback to content)
                    error_msg = action_result.get("message") or action_result.get("error") or action_result.get("content") or "Unknown error"
                    result.append(f"- Result: Failed - {error_msg}")
            
            if action['tool'] == 'read_file' and success:
                content_info = action_result.get("content_info", {})
                if content_info.get("type") == "file_reference":
                    # Show reference instead of full content
                    result.append(f"- File: {content_info['file_path']} ({content_info['lines']} lines)")
                    result.append(f"- Content: [Duplicate of {content_info['duplicate_of']}]")
                elif is_recent and content_info.get("type") == "file_content":
                    # Show content for recent actions
                    content = content_info.get("content", "")
                    if len(content) > 1000:  # Truncate very large content
                        result.append(f"- Content: {content[:1000]}... [truncated, {content_info['lines']} total lines]")
                    else:
                        result.append(f"- Content: {content}")
                else:
                    # Older actions - just show summary
                    result.append(f"- File: {content_info.get('file_path', 'unknown')} ({content_info.get('lines', 0)} lines)")
            
            elif action['tool'] == 'grep_search' and success:
                matches = action_result.get("matches", [])
                result.append(f"- Found {len(matches)} matches")
                if is_recent and matches:
                    # Show first few matches for recent searches
                    for i, match in enumerate(matches[:3]):
                        result.append(f"  {i+1}. {match.get('file')}:{match.get('line')}: {match.get('content')}")
                    if len(matches) > 3:
                        result.append(f"  ... and {len(matches) - 3} more matches")
            
            elif action['tool'] == 'edit_file' and success:
                operations = action_result.get("operations", 0)
                result.append(f"- Applied {operations} edit operations")
            
            elif action['tool'] == 'run_command' and success:
                command = action_result.get("command", "Unknown command")
                original_command = action_result.get("original_command")
                
                if original_command:
                    # Command was modified - make this VERY clear to AI
                    result.append("- ⚠️ COMMAND MODIFIED BY USER:")
                    result.append(f"  • You requested: {original_command}")
                    result.append(f"  • User executed: {command}")
                    result.append("- IMPORTANT: Reference the executed command in responses")
                else:
                    # Command executed as originally requested
                    result.append(f"- Executed Command: {command}")
                
                output = action_result.get("output", "")
                if output:
                    # Show first 200 chars of output for context
                    display_output = output[:200] + "..." if len(output) > 200 else output
                    result.append(f"- Output: {display_output}")
                
                reasoning = action_result.get("reasoning", "")
                if reasoning and is_recent:
                    result.append(f"- Edit reasoning: {reasoning[:200]}...")
            
            elif action['tool'] == 'run_command' and not success:
                # Handle failed commands clearly - show full error details
                command = action_result.get("command", "Unknown command")
                output = action_result.get("output", "No error details")
                original_command = action_result.get("original_command")
                
                result.append(f"- ❌ COMMAND FAILED: {command}")
                if original_command:
                    result.append(f"- Original Command: {original_command}")
                
                # Show error details with appropriate truncation
                if output:
                    if is_recent:
                        # Show more details for recent failures (up to 400 chars)
                        display_output = output[:400] + "..." if len(output) > 400 else output
                    else:
                        # Show less for older failures (up to 150 chars)
                        display_output = output[:150] + "..." if len(output) > 150 else output
                    result.append(f"- Error Details: {display_output}")
            
            elif action['tool'] == 'list_dir' and success:
                tree = action_result.get("tree_visualization", "")
                if tree:
                    # Show full tree (no preview truncation)
                    result.append(f"- Directory structure:\n  {tree.replace(chr(10), chr(10) + '  ')}")
        
        return '\n'.join(result)
    
    def _get_file_state_summary(self) -> str:
        """Generate summary of current file state."""
        if not self.file_cache:
            return ""
        
        summary = ["File State Summary:"]
        for file_path, info in self.file_cache.items():
            summary.append(f"- {file_path}: {info['lines']} lines (hash: {info['hash'][:8]}...)")
        
        return '\n'.join(summary)
    
    def _get_relevant_older_actions(self, older_actions: List[Dict[str, Any]], 
                                  current_query: str, char_budget: int) -> List[str]:
        """Get relevant older actions based on current query with character budget."""
        # Simple relevance scoring - could be enhanced with embeddings
        relevant = []
        query_words = set(current_query.lower().split())
        used_chars = 0
        
        # Score actions by relevance
        scored_actions = []
        for action in older_actions:
            action_text = f"{action.get('reason', '')} {action.get('params', {}).get('target_file', '')}"
            action_words = set(action_text.lower().split())
            
            # Simple word overlap scoring
            overlap = len(query_words.intersection(action_words))
            if overlap > 0:
                scored_actions.append((overlap, action))
        
        # Sort by relevance score (highest first)
        scored_actions.sort(key=lambda x: x[0], reverse=True)
        
        # Add actions within character budget
        for score, action in scored_actions:
            action_summary = self._format_action_for_context(action, is_recent=False)
            action_chars = len(action_summary)
            
            if used_chars + action_chars <= char_budget:
                relevant.append(action_summary)
                used_chars += action_chars
            else:
                # Try truncated version
                remaining_budget = char_budget - used_chars
                if remaining_budget > 500:  # Only if meaningful space remains
                    truncated = self._truncate_content_intelligently(action_summary, remaining_budget)
                    if truncated:
                        relevant.append(truncated)
                break
                
            if len(relevant) >= 5:  # Max 5 older actions
                break
        
        return relevant
    
    def _truncate_content_intelligently(self, content: str, char_limit: int) -> Optional[str]:
        """Intelligently truncate content to fit within character limit."""
        if char_limit <= 0:
            return None
            
        if len(content) <= char_limit:
            return content
        
        # Try to truncate at sentence boundaries first
        sentences = content.split('. ')
        if len(sentences) > 1:
            truncated = ""
            for sentence in sentences:
                test_content = truncated + sentence + ". "
                if len(test_content) > char_limit:
                    break
                truncated = test_content
            if truncated.strip():
                return truncated.strip() + "... [truncated]"
        
        # Fallback: character-based truncation
        truncated = content[:char_limit-20]  # Leave space for truncation marker
        # Try to cut at word boundary
        last_space = truncated.rfind(' ')
        if last_space > char_limit * 0.8:  # Only if we don't lose too much
            truncated = truncated[:last_space]
        
        return truncated + "... [truncated]"
    
    def _truncate_context_to_limit(self, context: str) -> str:
        """Final safety truncation to ensure we stay within limits."""
        if len(context) <= self.max_context_chars:
            return context
        
        # Split into sections and keep the most important ones
        sections = context.split('\n\n')
        
        # Prioritize: File State Summary, Recent Actions, then older actions
        important_sections = []
        other_sections = []
        
        for section in sections:
            if any(keyword in section for keyword in ['File State Summary', 'Recent Action']):
                important_sections.append(section)
            else:
                other_sections.append(section)
        
        # Build final context
        result_sections = []
        current_length = 0
        
        # Add important sections first
        for section in important_sections:
            if current_length + len(section) + 2 < self.max_context_chars:  # +2 for \n\n
                result_sections.append(section)
                current_length += len(section) + 2
            else:
                # Truncate this section if possible
                remaining_chars = self.max_context_chars - current_length - 20  # Buffer for truncation marker
                if remaining_chars > 500:
                    truncated_section = self._truncate_content_intelligently(section, remaining_chars)
                    if truncated_section:
                        result_sections.append(truncated_section)
                break
        
        # Add other sections if space remains
        for section in other_sections:
            if current_length + len(section) + 2 < self.max_context_chars:
                result_sections.append(section)
                current_length += len(section) + 2
            else:
                break
        
        return '\n\n'.join(result_sections)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the content cache."""
        total_files = len(self.file_cache)
        total_size = sum(info['size'] for info in self.file_cache.values())
        total_lines = sum(info['lines'] for info in self.file_cache.values())
        return {
            "cached_files": total_files,
            "unique_content_hashes": len(self.content_hashes),
            "total_content_size": total_size,
            "total_lines": total_lines,
            "deduplication_ratio": len(self.content_hashes) / max(total_files, 1)
        }
    
    def clear_cache(self):
        """Clear all cached content."""
        self.file_cache.clear()
        self.content_hashes.clear()