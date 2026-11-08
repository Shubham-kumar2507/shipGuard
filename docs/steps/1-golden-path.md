# Step 1: Golden-path service template

The Copier template lives in `templates/fastapi-service`. It asks for a service
name, description, and maintainer, and generates a small FastAPI app with:

- a tested `/health` endpoint;
- a multi-stage Dockerfile using a digest-pinned Python image and a non-root
  runtime user;
- pinned runtime and development dependencies;
- a GitHub Actions workflow for lint, tests, and an image build; and
- an `AGENTS.md` with build, test, lint, style, and security expectations.

Generate and check a project locally:

```powershell
copier copy --defaults `
  --data service_name=orders-api `
  --data service_description="Orders API" `
  --data maintainer="Platform team" `
  .\templates\fastapi-service .\orders-api
Set-Location .\orders-api
python -m pip install -e ".[dev]"
ruff check .
pytest -q
docker build --tag orders-api:local .
```

`tests/template/test_template.py` exercises Copier without network access.
GitHub-hosted CI itself still requires pushing the generated project to a
GitHub repository.
