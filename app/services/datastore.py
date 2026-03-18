import json
from pathlib import Path

from app.models import Incident


class DataStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]", encoding="utf-8")

    def list_incidents(self) -> list[Incident]:
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        return [Incident(**row) for row in rows]

    def save_incidents(self, incidents: list[Incident]) -> None:
        payload = [item.model_dump() for item in incidents]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
