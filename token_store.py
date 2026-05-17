import json
from pathlib import Path


class TokenStore:
    """Stores OAuth tokens in a file in the user's home directory (never in the git repo)."""

    def __init__(self):
        self.path = Path.home() / ".fitness_dashboard_tokens.json"

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data):
        self.path.touch(mode=0o600)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, service):
        return self._load().get(service)

    def set(self, service, tokens):
        data = self._load()
        data[service] = tokens
        self._save(data)

    def delete(self, service):
        data = self._load()
        data.pop(service, None)
        self._save(data)
