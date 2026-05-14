# SonarQube and CI Tutorial

## What SonarQube Does
SonarQube is a code quality platform. It analyzes source code, imports test coverage, and reports issues such as bugs, code smells, duplicated code, and missing coverage. In this repository it is used to scan:

- `gateway/` for the Flask API gateway
- `qr-service/` for the QR worker
- `frontend/` for the static UI

The scan configuration lives in `sonar-project.properties`.

## How the GitHub Actions Workflow Works
The CI pipeline is defined in `.github/workflows/ci-sonarqube.yml`.

It performs these steps:

1. Checks out the repository.
2. Installs Python 3.11.
3. Installs dependencies for `gateway/` and runs `pytest` with coverage.
4. Installs dependencies for `qr-service/` and runs `pytest` with coverage.
5. Uploads analysis results to SonarQube using:
   - `SONAR_HOST_URL`
   - `SONAR_TOKEN`

Coverage reports are generated as:

- `gateway/coverage.xml`
- `qr-service/coverage.xml`

SonarQube reads those files through `sonar.python.coverage.reportPaths`.

## How to Run Tests Manually
From the repository root:

```powershell
pip install -r gateway\requirements.txt
pip install -r qr-service\requirements.txt
pip install pytest-cov
pytest gateway\test_app.py --cov=gateway\app --cov-report=xml:gateway\coverage.xml
pytest qr-service\test_app.py --cov=qr-service\app --cov-report=xml:qr-service\coverage.xml
```

These commands reproduce the coverage artifacts used by CI.

## How to Start SonarQube Locally
The local SonarQube container definition is in `sonarqube/docker-compose.yaml`.

Start it with:

```powershell
docker compose -f sonarqube/docker-compose.yaml up -d
```

Then open:

```text
http://localhost:9000
```

On first startup, SonarQube may take a minute to become ready.

## Optional: Expose Local SonarQube with ngrok
Yes. You can use `ngrok` to give GitHub Actions temporary access to a SonarQube instance running on your machine. This is useful for testing, but it is less stable than hosting SonarQube on a public server or using a self-hosted runner.

Start SonarQube first, then expose port `9000`:

```powershell
ngrok http 9000
```

`ngrok` will print a public `https://...` forwarding URL. Use that URL as the value of the GitHub secret `SONAR_HOST_URL`.

Example:

```text
SONAR_HOST_URL=https://abcd-1234.ngrok-free.app
```

## How to Use SonarQube
After SonarQube is running:

1. Sign in to the web UI.
2. Create a project or use the project key from `sonar-project.properties`:
   `qr_gen`
3. Generate a token in SonarQube.
4. Store that token as the GitHub secret `SONAR_TOKEN`.
5. Store your SonarQube server URL as `SONAR_HOST_URL`.
6. Push a branch or open a pull request to trigger the workflow.

After the workflow finishes, open the project in SonarQube and review:

- Overall quality status
- Coverage percentages
- Bugs and code smells
- Files with the most issues

## Typical Workflow for Contributors
- Make code changes in `gateway/`, `qr-service/`, or `frontend/`.
- Run local tests before pushing.
- Push the branch and open a pull request.
- Wait for GitHub Actions to publish the analysis.
- Review issues in SonarQube and fix anything significant before merging.

## Notes
- The GitHub Action sends results to a SonarQube server reachable from GitHub Actions. `localhost:9000` only works for local manual use, not for GitHub-hosted runners.
- `ngrok` can bridge that gap for testing: run `ngrok http 9000` and set `SONAR_HOST_URL` to the generated public URL.
- Keep the `ngrok` process running while the GitHub Action executes, or the SonarQube upload will fail.
- Free `ngrok` URLs usually change between runs, so you may need to update `SONAR_HOST_URL` each time unless you use a reserved domain.
- If you run SonarQube only on your machine, you will need a separate public or self-hosted runner setup for CI uploads.
