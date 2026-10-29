# Deployment: Streamlit Community Cloud (free)

These are instructions for the project owner. **Nothing has been pushed or deployed.** Creating the public repository and deploying are owner actions.

## Before deploying

1. Read the privacy section below and decide whether Community Cloud's forced usage statistics are acceptable (decision D24). If platform telemetry is prohibited, use self-hosting instead.
2. Run the tests locally: `.\.venv\Scripts\python.exe -m pytest` (all must pass).
3. Confirm the repository contains only application code, public templates, demo data, docs and the bundled DejaVu fonts (with `wellnesspop/fonts/LICENSE_DEJAVU`). No user files, `.venv`, or secrets.

## Steps (free tier)

1. Create a free GitHub account if needed and a **public** repository named `wellnesspop`.
2. Push this folder's contents to the repository's default branch:
   ```powershell
   git init
   git add .
   git commit -m "WellnessPop MVP"
   git branch -M main
   git remote add origin https://github.com/<owner>/wellnesspop.git
   git push -u origin main
   ```
3. Sign in at https://share.streamlit.io with GitHub (free Community Cloud).
4. Choose **Create app → Deploy a public app from GitHub**. Repository: `<owner>/wellnesspop`; branch `main`; main file `app.py`.
5. Under **Advanced settings**, select Python **3.12** (the tested runtime). No secrets are needed.
6. Deploy. Dependencies install from the pinned `requirements.txt`.
7. On the deployed app: load each demo, run the simulation, download the workbook and PDF, and record the simulation time shown on the Simulation page (requirement: 10,000 runs in under 5 seconds on the deployment host). Record results in `docs/project-plan/gate-reviews.md`.

The app uses the free `*.streamlit.app` address. Do not buy a custom domain or paid hosting without a new explicit decision.

## Privacy limitations of Community Cloud

- **Usage statistics:** Community Cloud overrides `browser.gatherUsageStats` to `true`. The `false` setting in `.streamlit/config.toml` only takes effect where you control hosting. This means the free host is **not** telemetry-free. Disclose this in the app (the About page already says so) or self-host.
- **Platform logs:** the platform keeps its own technical logs. WellnessPop's code never logs plan contents, but platform logging is outside the app's control.
- **Server-side processing:** inputs are processed in server memory per session. The app has no database and writes no user files. Sessions can be lost on refresh, disconnection or when the free app sleeps after inactivity.
- **Shared resources:** free apps have resource limits and can sleep; there is no capacity guarantee.
- **Public app:** anyone with the URL can use it; each visitor gets an isolated session.

## Self-hosting alternative (telemetry under your control)

On any machine with Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`browser.gatherUsageStats = false` and `browser.serverAddress = "localhost"` (which stops Streamlit's startup public-IP lookup) apply here. For access from other devices, put the app behind your own reverse proxy and change `serverAddress` to the public host name.
