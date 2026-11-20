# How to run the Energy Demand Model

Running the dashboard on your own computer, and putting it online on Streamlit Community Cloud. Slides:
[running.html](../decks/running.html).

## What you need

1. **Python 3.11** and the code from this repository.
2. **The five input files** (below), or a GitHub token that can read the private data repository they live in.
3. **A secrets file**, `.streamlit/secrets.toml`, with the dashboard's login.
4. **The packages** in `requirements.txt`: streamlit 1.55.0, pandas 2.3.3, numpy 2.3.5, requests 2.32.5, plotly 6.9.0.
   Keep Streamlit at 1.55.0 unless you test the sidebar: `nav.py` relies on Streamlit internals.

## The input data

The data is licensed, so it is never stored in this repository.

| File | What it holds | Used by |
| --- | --- | --- |
| `globaldata_ldv_sales.csv` | GlobalData light vehicle extract | LDV actuals |
| `globaldata_hdv_sales.csv` | GlobalData medium and heavy commercial vehicle extract | HDV actuals |
| `hdv_default_schema.csv` | HDV Default Scenario assumptions | HDV defaults |
| `weo_other_oil_consumption.csv` | World Energy Outlook extract | Other Oil actuals |
| `other_oil_default_schema.csv` | Other Oil Default Scenario assumptions | Other Oil defaults |

The LDV default assumptions have no file: they are in `ldv_scenario_config.py`.

`data_loader.py` looks for each file in this order:

1. **`input_data/<file>`** in the repository folder. If it is there, it is used. This is how you run it locally.
2. **The private data repository** named by `DATA_REPO` in `data_loader.py` (branch `main`), downloaded with the token
   in `[github] data_repo_pat`. The download is kept in a temporary folder while the app runs.

## The secrets file

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it in:

```toml
[auth]
username = "choose-a-username"
password = "choose-a-password"

[github]
data_repo_pat = "github_pat_..."
```

- `[auth]` is the one login everyone uses to open the dashboard. You choose it.
- `[github]` is needed only when a file is missing from `input_data/`: a fine-grained GitHub token with read access to
  the data repository only.
- The file is ignored by git. Never commit it. Online, the same keys go in the app's **Settings → Secrets**.

## Run it on your computer

```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill it in
streamlit run app.py
```

Put the five files in `input_data/` first (the folder is ignored by git). The dashboard opens at
`http://localhost:8501`; sign in with the username and password from your secrets file.

**Dev container / Codespaces:** `.devcontainer/` sets up Python 3.11, installs the packages and starts the app on port
8501.

**One model on its own:** each model runs from the command line and prints its results. Give the file path, because the
LDV and HDV defaults point at file names that don't exist:

```
python ldv_forecast_model.py input_data/globaldata_ldv_sales.csv
python hdv_forecast_model.py input_data/globaldata_hdv_sales.csv
python other_oil_forecast_model.py
```

## Put it online (Streamlit Community Cloud)

1. Keep the five files in a **private** GitHub repository, and set `DATA_REPO` in `data_loader.py` to its name.
2. Create a fine-grained token with read-only access to that repository. Note its expiry date: when it lapses, the
   online app can no longer download the data.
3. On [share.streamlit.io](https://share.streamlit.io), create an app from the code repository: branch `main`, file
   `app.py`.
4. In the app's **Settings → Secrets**, paste the `[auth]` and `[github] data_repo_pat` values.
5. Deploy, then check: the login blocks strangers, the data downloads, and the numbers match a local run.

If the code repository is private: the app is private by default (only people you invite can open it, on top of the
login; you can make it public in its sharing settings), Community Cloud allows one private app at a time, and you need
admin rights on the repository to deploy from it.

The app follows `main`. A redeploy or restart wipes the scenarios users have saved online.

## Updating the data

- Replace the file in the data repository (or in `input_data/`) with a newer extract that keeps the **same file name
  and column layout**, then restart the app.
- Newer years move the forecast start only if `FORECAST_START` in `forecast_model.py` (now 2025) is changed too. Until
  then, extra years are treated as the source's own forecast and ignored.
- Columns the code reads: `REGION` and `HYBRID & EV TYPE` (LDV), `COUNTRY` and `POWERTRAIN TYPE` (HDV), plus one
  column per year.
- Editing a schema file changes that model's Default Scenario.

## When something goes wrong

| What you see | Why | What to do |
| --- | --- | --- |
| An error when you press **Log in** | No `.streamlit/secrets.toml`, or no `[auth]` section | Create the secrets file |
| "Couldn't download … GitHub returned **401**" | Token missing, malformed or expired | Make a new token; update `data_repo_pat` |
| "… returned **403**" | Token can't access the repository, or rate limit reached | Check the token's repository access |
| "… returned **404**" | File not on `main` of `DATA_REPO`, or the token can't see the repository | Check the file name and `DATA_REPO` |
| Saved scenarios are gone online | The app restarted or redeployed; its storage is temporary | Record important scenarios elsewhere |

**Never commit `input_data/` or `.streamlit/secrets.toml`.** Both are in `.gitignore`; check `git status` before
every push.

Next: [How to use it](using.md)
