import os
from typing import List, Dict, Any, Tuple

def _build_tree_str(items: List[Dict[str, Any]], prefix: str = "", is_last: bool = True) -> str:
    """
    Helper function to build a tree-style string representation of the directory structure.
    """
    tree_str = ""
    for i, item in enumerate(items):
        is_last_item = i == len(items) - 1
        connector = "└──" if is_last_item else "├──"
        tree_str += f"{prefix}{connector} {item['name']}\n"
        
        if item["type"] == "directory" and "children" in item:
            next_prefix = prefix + ("    " if is_last_item else "│   ")
            tree_str += _build_tree_str(item["children"], next_prefix, is_last_item)
    return tree_str

def list_dir(relative_workspace_path: str) -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    Recursively list contents of a directory.
    
    Args:
        relative_workspace_path: Path to list contents of, relative to the workspace root
        
    Returns:
        Tuple of (list of items, success status, tree visualization string)
        Each item contains:
        {
            "name": file/directory name,
            "path": relative path,
            "type": "file" or "directory",
            "size": size in bytes (for files only),
            "children": list of items (for directories only)
        }
    """
    def _list_dir_recursive(path: str) -> List[Dict[str, Any]]:
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
                else:
                    # Recursively list directory contents
                    item_info["children"] = _list_dir_recursive(item_path)
                    
                items.append(item_info)
                
            # Sort: directories first, then files (alphabetically within each group)
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
        except Exception as e:
            pass
        return items

    try:
        path = os.path.normpath(relative_workspace_path)
        
        if not os.path.exists(path):
            return [], False, ""
            
        if not os.path.isdir(path):
            return [], False, ""
            
        items = _list_dir_recursive(path)
        tree_str = _build_tree_str(items)
        
        return items, True, tree_str
        
    except Exception as e:
        return [], False, ""

if __name__ == "__main__":
    # Test the list_dir function
    items, success, tree_str = list_dir("..")
    print(f"Directory listing success: {success}")
    print(f"Found {len(items)} items")
    
    # Print tree visualization
    print("\nDirectory Tree:")
    print(tree_str)
    
    # Print statistics
    dir_count = sum(1 for item in items if item["type"] == "directory")
    file_count = sum(1 for item in items if item["type"] == "file")
    print(f"\nStatistics:")
    print(f"- {dir_count} directories")
    print(f"- {file_count} files") 