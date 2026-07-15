# energy-demand-model
Energy demand scenario forecasting model

## Web app

A Streamlit dashboard (`app.py`) lets users pick a scenario (Base Case / Faster
Transition / Slower Transition) and view the scenario config plus the resulting
sales forecasts as tables or charts.

### Local setup

```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill in [auth] username/password
streamlit run app.py
```

If `input_data/globaldata_ldv_sales.csv` is present locally, the app uses it
directly and the `[github]` secrets section is unused. It's only needed when
that file is absent (i.e. in the deployed environment - see below).

### Deployment

The input CSV is GlobalData-licensed data and must **not** be committed to
this (public) repo - it lives in a separate private repo instead, and the
running app downloads it at startup via a scoped GitHub token.

1. Create a **private** GitHub repo, e.g. `carbon-tracker-initiative/energy-demand-model-data`,
   and push `globaldata_ldv_sales.csv` to it (update the `DATA_REPO`/`DATA_REPO_PATH`
   constants in `data_loader.py` if you use a different name/path).
2. Generate a fine-grained GitHub Personal Access Token scoped read-only to
   that one repo. Note its expiry - fine-grained tokens expire within a year
   and the app will fail once it lapses until someone rotates it.
3. Push this repo to GitHub. Double-check `git status` shows `input_data/`
   and `.streamlit/secrets.toml` as ignored before pushing.
4. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at this repo, branch `main`, entry point `app.py`.
5. In the app's Settings -> Secrets, paste in real values matching
   `.streamlit/secrets.toml.example`'s structure: `[auth]` username/password
   (the shared login for the dashboard) and `[github] data_repo_pat` (the
   token from step 2).
6. Deploy, then verify on the live URL: the login gate blocks unauthenticated
   access, the data downloads successfully from the private repo, and the
   numbers match a local run.
