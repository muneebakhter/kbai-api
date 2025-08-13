#!/usr/bin/env python3
"""
Cleanup script for KBAI API - removes generated data and indexes
"""

import os
import shutil
from pathlib import Path

def cleanup_kbai_data():
    """Clean up all generated data and indexes"""
    print("🧹 Starting KBAI cleanup...")
    
    # Directories and files to clean
    cleanup_targets = [
        "./data",
        "./app/kbai_api.db",
        "./ASPCATest.docx",
        "./__pycache__",
        "./app/__pycache__"
    ]
    
    cleaned = 0
    
    for target in cleanup_targets:
        target_path = Path(target)
        
        if target_path.exists():
            try:
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                    print(f"✅ Removed directory: {target}")
                else:
                    target_path.unlink()
                    print(f"✅ Removed file: {target}")
                cleaned += 1
            except Exception as e:
                print(f"❌ Failed to remove {target}: {e}")
        else:
            print(f"ℹ️  {target} does not exist")
    
    # Clean any .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        try:
            pyc_file.unlink()
            cleaned += 1
        except Exception:
            pass
    
    print(f"\n🎉 Cleanup completed! Removed {cleaned} items.")
    print("Ready for fresh setup.")

if __name__ == "__main__":
    cleanup_kbai_data()