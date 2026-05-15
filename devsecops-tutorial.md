# DevSecOps Tutorial for This QR Project

## 1. What each tool does

- `Bandit` scans Python source code for common security issues.
- `Gitleaks` scans for hardcoded secrets such as tokens, passwords, and API keys.
- `Trivy` scans the repository for dependency vulnerabilities and infrastructure misconfigurations.

For this project:

- Run `Bandit` against `gateway/` and `qr-service/`.
- Run `Gitleaks` against the whole Git repository.
- Run `Trivy` against the whole repository so it can inspect Python dependencies, Dockerfiles, and Compose files.

## 2. Local setup

Install the project dependencies plus Bandit:

```powershell
pip install -r gateway\requirements.txt -r qr-service\requirements.txt "bandit[toml]"
```

## 3. Run the automated tests locally

Run the tests before security tools. This matches the CI pipeline order:

```powershell
pytest gateway qr-service
```

If the tests fail because packages are missing, it usually means the virtual environment is not active or the requirements were not installed in that environment.

## 4. Run Bandit locally

Bandit's official docs show the basic recursive pattern `bandit -r path/to/your/code`.

Run it on both Python services:

```powershell
bandit -r gateway qr-service -ll
```

Useful options:

- `-r` scans recursively
- `-l` means low severity and above
- `-ll` means medium severity and above
- `-lll` means high severity only

Recommended learning flow:

1. Start with medium and high findings:

```powershell
bandit -r gateway qr-service -ll
```

3. If you want a machine-readable report:

```powershell
bandit -r gateway qr-service -f json -o bandit-report.json
```

## 5. Run Gitleaks locally

Gitleaks has two useful modes:

- `gitleaks git` scans Git history
- `gitleaks dir` scans the current working tree

### Option A: Run Gitleaks with Docker

This is the simplest path if you already use Docker Desktop:

```powershell
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:latest git /repo --verbose
```

To scan only the current files instead of Git history:

```powershell
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:latest dir /repo --verbose
```

To save a SARIF report:

```powershell
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:latest git /repo --report-format sarif --report-path /repo/gitleaks-report.sarif --verbose
```

## 6. Run Trivy locally

Trivy's official filesystem mode is `trivy fs /path/to/project`.

### Option A: Run Trivy with Docker

```powershell
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/aquasecurity/trivy:latest fs --scanners vuln,misconfig . 
```

To fail only on high and critical issues:

```powershell
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/aquasecurity/trivy:latest fs --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 .
```

To save a SARIF report:

```powershell
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/aquasecurity/trivy:latest fs --scanners vuln,misconfig --format sarif --output trivy-report.sarif .
```

### Option B: Install the native binary

Trivy publishes Windows binaries on its official releases page. After extracting `trivy.exe`, add it to your `PATH` and run:

```powershell
trivy fs --scanners vuln,misconfig .
```

Why `vuln,misconfig` is a good fit here:

- `vuln` checks Python dependency risk where lock and dependency files exist
- `misconfig` checks Dockerfiles and Compose configuration

## 8. Suggested local workflow

Use this order every time:

```powershell
pytest gateway qr-service
bandit -r gateway qr-service -ll
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:latest git /repo --verbose
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/aquasecurity/trivy:latest fs --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 .
```

## 9. GitHub Actions pipeline design

The workflow added to this repo does the following:

1. checks out the code
2. installs Python 3.11
3. installs dependencies from both Python services
4. runs `pytest gateway qr-service`
5. only if tests pass, runs:
   - `Bandit`
   - `Gitleaks`
   - `Trivy`

Why `fetch-depth: 0` matters:

- `Gitleaks git` needs the full repository history, not a shallow clone

## 10. How to read failures

If `Bandit` fails:

- inspect the reported file and line
- decide whether it is a real issue or a false positive
- fix the code first instead of suppressing immediately

If `Gitleaks` fails:

- assume it is serious until proven otherwise
- remove and rotate the secret
- only ignore a result if you are certain it is a safe false positive

If `Trivy` fails:

- for dependency findings, upgrade the vulnerable package if possible
- for configuration findings, harden the Dockerfile or Compose settings
- if a vulnerability is unfixed upstream, document the risk and decide whether to temporarily allow it

## 11. Optional next improvements

After this first pipeline is working, useful next steps are:

- add a `.bandit` config file if you want custom thresholds or excludes
- add a `gitleaks.toml` only if you need custom secret rules
- add a `trivy.yaml` if you want to standardize scanners and severity settings
- upload SARIF reports into GitHub code scanning for Bandit and Trivy
- add image scanning with `trivy image` after Docker builds

## 12. Source references

I based this setup on the current official docs and release pages:

- Bandit getting started: https://bandit.readthedocs.io/en/1.8.3/start.html
- Bandit GitHub Actions guide: https://bandit.readthedocs.io/en/latest/ci-cd/github-actions.html
- Gitleaks repo and usage docs: https://github.com/gitleaks/gitleaks
- Gitleaks latest release page checked: `v8.30.1` on March 21, 2026
- Trivy installation docs: https://trivy.dev/latest/getting-started/installation/
- Trivy filesystem scan docs: https://trivy.dev/docs/latest/target/filesystem/
- Trivy Action docs: https://github.com/aquasecurity/trivy-action

The workflow pins `aquasecurity/trivy-action` to `v0.36.0`, which the upstream project currently lists as the latest release.
