from pathlib import Path

class PathManager:
    """Manages project-wide path resolution and directory access."""

    def __init__(self, marker: str = ".git"):
        self._project_root = self._resolve_root(marker)

    def _resolve_root(self, marker: str) -> Path:
        """Finds the project root based on a filesystem marker."""
        current_path = Path(__file__).resolve()

        for parent in current_path.parents:
            if (parent / marker).exists():
                return parent

        return current_path.parent

    @property
    def root(self) -> Path:
        return self._project_root

    def get_logs_dir(self) -> Path:
        """Returns the absolute path to the root logs directory."""

        return self.root / "logs"

    def get_data_dir(self) -> Path:
        """Returns the absolute path to the data directory."""
        return self.root / "data"


# Create a singleton instance for global access
paths = PathManager(marker="README.md")