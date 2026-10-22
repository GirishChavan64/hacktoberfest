"""
Global pytest configuration.

Forces MOCK_LLM=1 for the entire test session so tests are fully
deterministic and never touch a real LLM API, regardless of what the
local .env file says.

This file is auto-loaded by pytest before any test module is imported.
Setting os.environ here is the only reliable way to override the class-level
attribute that config.py evaluates at import time.
"""

import os

# Must be set BEFORE config.py / llm.py are imported by any test module.
os.environ["MOCK_LLM"] = "1"

# Re-evaluate Config.MOCK_LLM in case config was already imported by a
# previous import chain (e.g. via app.py at collection time).
try:
    from config import Config
    Config.MOCK_LLM = True
except ImportError:
    pass
