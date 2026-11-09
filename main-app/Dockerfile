# Main Django app (ADR 0008). Images pinned by digest; runs as non-root.

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so code changes don't reinstall them. --locked installs
# exactly what uv.lock pins, with hashes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev
COPY . .

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
# Root owns the code; the app user can read it but not change it.
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi"]
