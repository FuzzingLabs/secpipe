FROM docker.io/debian:trixie

ARG PACKAGE

COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /bin/

WORKDIR /app

RUN /bin/uv venv && /bin/uv pip install --find-links /wheels $PACKAGE

CMD [ "/bin/uv", "run", "uvicorn", "fuzzforge_mcp.application:app"]
