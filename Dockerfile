FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    GAMCFGDIR=/var/lib/gam

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home-dir /home/app app \
    && mkdir -p /var/lib/gam /var/lib/gam-auth /var/lib/gam-work /home/app /run/gam-client \
    && chown -R app:app /var/lib/gam /var/lib/gam-auth /var/lib/gam-work /home/app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY media ./media
RUN uv sync --locked --no-dev --no-editable \
    && chown -R app:app /app /var/lib/gam /var/lib/gam-work /home/app

USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "gmail_forwarder_web.web:app", "--host", "0.0.0.0", "--port", "8000"]