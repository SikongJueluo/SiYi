set windows-powershell := true

[parallel]
dev: dev-backend dev-frontend

dev-frontend:
    pnpm dev

dev-backend:
    uv run fastapi dev backend/src/main.py

update-requirements:
    uv export --project listener/mcdr-plugin --format requirements.txt --output-file listener/mcdr-plugin/requirements.txt

test-py-protocol:
    uv --project shared\py-protocol run --extra dev pytest shared\py-protocol\tests\ -v
