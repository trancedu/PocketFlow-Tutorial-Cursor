import os
from typing import List, Dict, Any, Tuple

# Default maximum characters to return in the tree visualization
DEFAULT_MAX_OUTPUT_CHARS = 4000

def _build_tree_str(items: List[Dict[str, Any]], prefix: str = "") -> str:
    """
    Build a tree-style string representation of the directory structure.
    - Shows one level of recursion (root + each directory's children)
    - Lists all files (no fixed count limit); overall output is capped later by char count
    """
    tree_str = ""

    # Split items into directories and files
    dirs = [item for item in items if item["type"] == "directory"]
    files = [item for item in items if item["type"] == "file"]

    # Process directories first, then files
    for i, item in enumerate(dirs):
        is_last_dir = (i == len(dirs) - 1) and (len(files) == 0)
        connector = "└──" if is_last_dir else "├──"
        tree_str += f"{prefix}{connector} {item['name']}/\n"

        # Show children (one level deeper only, as provided by the recursive lister)
        next_prefix = prefix + ("    " if is_last_dir else "│   ")
        if "children" in item and item["children"]:
            # Recursively render children of this directory
            tree_str += _build_tree_str(item["children"], next_prefix)

    # Then process files (list all files; truncation handled by outer cap)
    for i, item in enumerate(files):
        is_last_file = (i == len(files) - 1)
        connector = "└──" if is_last_file else "├──"
        size_str = f" ({item['size'] / 1024:.1f} KB)" if item.get("size", 0) > 0 else ""
        tree_str += f"{prefix}{connector} {item['name']}{size_str}\n"

    return tree_str

def list_dir(relative_workspace_path: str) -> Tuple[bool, str]:
    """
    List contents of a directory (one level only).
    
    Args:
        relative_workspace_path: Path to list contents of, relative to the workspace root
        
    Returns:
        Tuple of (success status, tree visualization string)
    """
    def _list_dir_recursive(path: str, depth: int = 0) -> List[Dict[str, Any]]:
        items = []
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                
                item_info = {
                    "name": item,
                    "path": item_path,
                    "type": "directory" if is_dir else "file"
                }
                
                if not is_dir:
                    try:
                        item_info["size"] = os.path.getsize(item_path)
                    except:
                        item_info["size"] = 0
                elif depth < 1:  # Only recurse one level
                    # Recursively list directory contents
                    item_info["children"] = _list_dir_recursive(item_path, depth + 1)
                    
                items.append(item_info)
                
            # Sort: directories first, then files (alphabetically within each group)
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
        except Exception as e:
            pass
        return items

    try:
        path = os.path.normpath(relative_workspace_path)
        
        if not os.path.exists(path):
            return False, ""
            
        if not os.path.isdir(path):
            return False, ""
            
        items = _list_dir_recursive(path)
        tree_str = _build_tree_str(items)

        # Apply a global character cap to keep output manageable
        max_chars = int(os.environ.get("LIST_DIR_MAX_CHARS", DEFAULT_MAX_OUTPUT_CHARS))
        if len(tree_str) > max_chars:
            tree_str = tree_str[:max_chars].rstrip() + f"\n... (output truncated to first {max_chars} characters)\n"
        
        return True, tree_str
        
    except Exception as e:
        return False, ""

if __name__ == "__main__":
    # Test the list_dir function
    success, tree_str = list_dir("..")
    print(f"Directory listing success: {success}")
    
    # Print tree visualization
    print("\nDirectory Tree:")
    print(tree_str) 