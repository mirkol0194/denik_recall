import json
import os
from pathlib import Path


class RecallConfig:
    def __init__(self):
        self.database_path = str(Path.home() / ".recall" / "recall_py.db")
        self.model_name = "all-MiniLM-L6-v2"
        self.system_prompt = ""
        self.auto_context_limit = 5
        self.search_result_limit = 10

    @classmethod
    def load(cls):
        config = cls()
        config_path = Path.home() / ".recall" / "config.json"

        if not config_path.exists():
            return config

        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return config

        if "autoContextLimit" in data:
            config.auto_context_limit = data["autoContextLimit"]
        if "searchResultLimit" in data:
            config.search_result_limit = data["searchResultLimit"]
        if "systemPrompt" in data:
            config.system_prompt = data["systemPrompt"]

        # Load prompt from external file if specified
        prompt_file = data.get("promptFile")
        if prompt_file:
            path = Path(prompt_file).expanduser()
            if path.exists():
                config.system_prompt = path.read_text()

        return config
