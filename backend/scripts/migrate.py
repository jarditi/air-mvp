#!/usr/bin/env python3
"""
Database migration management script.

This script provides convenient commands for managing database migrations
using Alembic. It can be run directly or through Docker.

Usage:
    python scripts/migrate.py upgrade head    # Apply all migrations
    python scripts/migrate.py downgrade -1   # Rollback one migration
    python scripts/migrate.py revision --autogenerate -m "Add users table"
    python scripts/migrate.py current        # Show current revision
    python scripts/migrate.py history        # Show migration history
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def run_alembic_command(args):
    """Run an Alembic command with proper environment setup."""
    # Change to the backend directory
    os.chdir(backend_dir)
    
    # Construct the alembic command
    cmd = ["alembic"] + args
    
    try:
        # Run the command
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error running alembic command: {e}", file=sys.stderr)
        print(f"stdout: {e.stdout}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        return e.returncode
    except FileNotFoundError:
        print("Error: alembic command not found. Make sure Alembic is installed.", file=sys.stderr)
        return 1

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    # Pass all arguments except the script name to alembic
    alembic_args = sys.argv[1:]
    
    return run_alembic_command(alembic_args)

if __name__ == "__main__":
    sys.exit(main()) 