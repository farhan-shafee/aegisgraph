"""Unit/integration tests never consume workstation provider credentials."""

import os

os.environ["AEGISGRAPH_LOAD_ENV"] = "false"
os.environ["AI_PROVIDER"] = "deterministic"
