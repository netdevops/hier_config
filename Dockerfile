FROM python:3.12-slim AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

WORKDIR /app

# Dependency metadata only, so the dependency layer caches across source edits
COPY pyproject.toml poetry.lock README.md ./

RUN poetry install --no-root --with dev

COPY . .

RUN poetry install --with dev

CMD ["python", "scripts/build.py", "lint-and-test"]
