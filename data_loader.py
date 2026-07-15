"""
Resolves a local file path to the LDV sales CSV, so the rest of the app can
just call run_model(get_csv_path()) without caring where the data came from.

Local dev: uses input_data/globaldata_ldv_sales.csv directly if present.
Deployed (no local file): downloads it from a private GitHub repo using a
PAT stored in Streamlit secrets, and caches it to a temp file for the life
of the running container.
"""

import tempfile
from pathlib import Path

import requests
import streamlit as st

LOCAL_CSV_PATH = Path(__file__).parent / "input_data" / "globaldata_ldv_sales.csv"
CACHED_CSV_PATH = Path(tempfile.gettempdir()) / "energy-demand-model-data" / "globaldata_ldv_sales.csv"

DATA_REPO = "carbon-tracker-initiative/energy-demand-model-data"
DATA_REPO_PATH = "globaldata_ldv_sales.csv"
DATA_REPO_REF = "main"


@st.cache_resource(show_spinner="Downloading sales data...")
def get_csv_path() -> str:
    if LOCAL_CSV_PATH.exists():
        return str(LOCAL_CSV_PATH)
    if not CACHED_CSV_PATH.exists():
        _download_csv_from_private_repo(CACHED_CSV_PATH)
    return str(CACHED_CSV_PATH)


def _download_csv_from_private_repo(dest: Path) -> None:
    token = st.secrets["github"]["data_repo_pat"]
    url = f"https://api.github.com/repos/{DATA_REPO}/contents/{DATA_REPO_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with requests.get(url, headers=headers, params={"ref": DATA_REPO_REF}, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.replace(dest)
