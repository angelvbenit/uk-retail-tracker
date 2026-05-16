import os

# 1. Dynamically find the absolute path of the Project Root directory
# This looks at where config.py lives and anchors the whole project there.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 2. Define standard absolute paths into the root data directory
RAW_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed")

# Ensure the root directories exist automatically
os.makedirs(RAW_DATA_PATH, exist_ok=True)
os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)