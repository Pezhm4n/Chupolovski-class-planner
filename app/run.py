#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chupolovski Class Planner Launcher
Simple launcher script for the Chupolovski Class Planner - University Course Schedule Planner
"""

import sys
import os

def main():
    print("🎓 Chupolovski Class Planner v3.0 | چوپولوفسکی کلاس پلنر")
    print("=" * 70)
    print("🚀 Starting smart university course scheduling application...")
    print("📚 Loading courses and optimizing your schedule...")
    
    try:
        # Import and run the main application
        from chupolovski_class_planner import main as run_app
        return run_app()
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("🛠️  Please ensure PyQt5 is installed: pip install PyQt5")
        print("📦 Or install all requirements: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())