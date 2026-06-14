from pathlib import Path
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "skilleval.db"
IMPORT_DIR = DATA_DIR / "imports"
UPLOAD_DIR = DATA_DIR / "uploads"
RUN_DIR = DATA_DIR / "runs"
WORKSPACE_DIR = Path(tempfile.gettempdir()) / "skilleval-workspaces"


def ensure_data_dirs() -> None:
    for path in (DATA_DIR, IMPORT_DIR, UPLOAD_DIR, RUN_DIR, WORKSPACE_DIR):
        path.mkdir(parents=True, exist_ok=True)
