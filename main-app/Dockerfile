# Main Django app (ADR 0008). Images pinned by digest; runs as non-root.

# Frontend build (ADR 0031): theme.css from the Sass CLI and the <BrandList />
# bundle from Vite. Node stays in this stage, so the runtime image has none.
# 24.22.1 is the latest Node security release; its image is past the 7-day
# cooldown (24.22.2 fixed no vulnerabilities and its image was days old).
FROM node:24.22.1-trixie-slim@sha256:89c5244bc22a9bc3287d89ebc7e49b9cb5bb84cd40e6175ac3421d5a9f68b95a AS frontend
# Corepack fetches the pnpm version package.json pins and checks its npm
# signature; no prompt in a non-interactive build.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable pnpm
WORKDIR /frontend
# Dependencies first, so source changes don't reinstall them. The workspace
# file carries the cooldown, trust and build-script policies (ADR 0029).
COPY --from=frontend-src package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
# Only what the build reads: never the host's node_modules or dist.
COPY --from=frontend-src tsconfig.json vite.config.ts ./
COPY --from=frontend-src scss ./scss
COPY --from=frontend-src src ./src
# Type checking and tests belong to `pnpm test` and `pnpm typecheck`, which
# also need ../contracts; the image only needs the output.
RUN pnpm scss && pnpm exec vite build

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so code changes don't reinstall them. --locked installs
# exactly what uv.lock pins, with hashes. The shared library comes from the
# shared-lib build context, at the path uv.lock records (../shared-lib), and
# is installed as a copy (--no-editable), so the runtime stage needs no
# library source (ADR 0025).
COPY pyproject.toml uv.lock .python-version ./
COPY --from=shared-lib . /shared-lib
RUN uv sync --locked --no-dev --no-editable
COPY . .
# The build output where settings look for it (DJANGO_FRONTEND_DIR), then
# hashed and compressed into STATIC_ROOT. The manifest stays in frontend/dist
# for the vite_entry tag. collectstatic needs a key to import settings, never
# a real one.
COPY --from=frontend /frontend/dist-css ./frontend/dist-css
COPY --from=frontend /frontend/dist ./frontend/dist
ENV DJANGO_FRONTEND_DIR=/app/frontend
RUN DJANGO_SECRET_KEY=collectstatic-only .venv/bin/python manage.py collectstatic --noinput

FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
# Root owns the code; the app user can read it but not change it.
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_FRONTEND_DIR=/app/frontend
USER 10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi"]
