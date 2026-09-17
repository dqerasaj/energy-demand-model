# energy-demand-model
Energy demand scenario forecasting model

## Web app

A Streamlit dashboard (`app.py`) covers two vehicle classes - LDV (light duty)
and HDV (heavy duty trucks and buses) - each with its own sidebar section. For
either, users pick a scenario (Base Case / Faster Transition / Slower
Transition) and view the scenario config plus the resulting sales forecasts as
charts or tables.

Both models share one forecasting engine (`forecast_model.py`) and one set of
pages; `vehicle_models.py` holds the per-class differences - regions,
powertrains, input files and labels. LDV models BEV, PHEV and IC Only across
North America / Europe / APAC / RoW; HDV models BEV and IC Only across China /
USA / RoW. In both, IC Only is the residual that reconciles the modelled
powertrains with the region's all-vehicle total.

### Local setup

```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill in [auth] username/password
streamlit run app.py
```

Three input files are read from `input_data/`:

| File | Used by |
| --- | --- |
| `globaldata_ldv_sales.csv` | LDV sales actuals |
| `globaldata_hdv_sales.csv` | HDV sales actuals |
| `hdv_default_schema.csv` | HDV default scenario values (the LDV equivalent is hard-coded in `scenario_config.py`) |

Any of them present locally is used directly, and the `[github]` secrets
section is unused for it. That section is only needed for files that are absent
(i.e. in the deployed environment - see below).

### Deployment

The sales extracts are GlobalData-licensed data and must **not** be committed
to this (public) repo - they live in a separate private repo instead, and the
running app downloads them at startup via a scoped GitHub token.

1. Create a **private** GitHub repo (e.g.`{repo_owner}/energy-demand-model-data`) and push
   the three input files listed above to it.
   (update the `DATA_REPO` constant and the filename constants in `data_loader.py` if you use different names/paths)
2. Generate a fine-grained GitHub Personal Access Token scoped read-only to that one repo.
   Note its expiry - the app will fail once it lapses until someone restarts it.
3. Push this repo to GitHub. Double-check `git status` shows `input_data/` and
   `.streamlit/secrets.toml` as ignored before pushing.
4. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at this repo,
   branch `main`, entry point `app.py`.
5. In the app's Settings -> Secrets, paste in real values matching
   `.streamlit/secrets.toml.example`'s structure: `[auth]` username/password
   (the chosen shared login for the dashboard) and `[github] data_repo_pat`
   (the token from step 2).
6. Deploy, then verify on the live URL: the login gate blocks unauthenticated access,
   the data downloads successfully from the private repo, and the numbers match a local run.
