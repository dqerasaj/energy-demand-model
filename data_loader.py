"""
Resolves local file paths to the model input data, so the rest of the app can
just call run_model(get_ldv_csv_path()) without caring where the data came
from.

Local dev: uses the files under input_data/ directly if present.
Deployed (no local file): downloads them from a private GitHub repo using a
PAT stored in Streamlit secrets, and caches each to a temp file for the life of
the running container.

Three files are needed: the LDV and HDV sales extracts, and the CSV of default
HDV scenario values (the LDV equivalent is hard-coded in scenario_config.py, so
it has no file here).
"""

import tempfile
from pathlib import Path

import requests
import streamlit as st

LOCAL_DATA_DIR = Path(__file__).parent / "input_data"
CACHE_DIR = Path(tempfile.gettempdir()) / "energy-demand-model-data"

LDV_CSV = "globaldata_ldv_sales.csv"
HDV_CSV = "globaldata_hdv_sales.csv"
HDV_SCHEMA_CSV = "hdv_default_schema.csv"

DATA_REPO = "dqerasaj/energy-demand-model-data"
DATA_REPO_REF = "main"


@st.cache_resource(show_spinner="Downloading sales data...")
def _resolve(filename: str) -> str:
    """The local copy if there is one, otherwise the downloaded-and-cached
    copy. Cached per filename, so each file is fetched at most once per
    container."""
    local = LOCAL_DATA_DIR / filename
    if local.exists():
        return str(local)

    cached = CACHE_DIR / filename
    if not cached.exists():
        _download_from_private_repo(filename, cached)
    return str(cached)


def get_ldv_csv_path() -> str:
    return _resolve(LDV_CSV)


def get_hdv_csv_path() -> str:
    return _resolve(HDV_CSV)


def get_hdv_schema_path() -> str:
    return _resolve(HDV_SCHEMA_CSV)


def _download_from_private_repo(repo_path: str, dest: Path) -> None:
    token = st.secrets["github"]["data_repo_pat"]
    url = f"https://api.github.com/repos/{DATA_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with requests.get(url, headers=headers, params={"ref": DATA_REPO_REF}, stream=True, timeout=60) as resp:
        if not resp.ok:
            _report_failure(repo_path, resp.status_code)
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def _report_failure(repo_path: str, status: int) -> None:
    """Say what actually went wrong, on the page.

    Streamlit redacts exception messages in deployed apps, so a failed download
    surfaces as a bare "requests.exceptions.HTTPError" with no status code and
    no filename - which can't distinguish a lapsed token from a missing file.
    This writes that detail out before the error propagates. The token itself
    is never included.
    """
    hints = {
        401: "the [github] data_repo_pat secret is missing, malformed or expired",
        403: "the token can't access this repo, or its rate limit is exhausted",
        404: (
            f"{repo_path} isn't on branch {DATA_REPO_REF} of {DATA_REPO} - or "
            "the token can't see that repo at all"
        ),
    }
    hint = hints.get(status, "unexpected response from the GitHub API")
    st.error(
        f"Couldn't download **{repo_path}** from `{DATA_REPO}`.\n\n"
        f"GitHub returned **{status}** - {hint}.\n\n"
        "If the token has lapsed, generate a new fine-grained PAT with read "
        "access to that repo and update this app's `[github] data_repo_pat` "
        "secret in Streamlit Cloud."
    )
