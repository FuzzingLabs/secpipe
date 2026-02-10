FROM docker.io/debian:trixie as base

COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /uvx /bin/

FROM base as builder

WORKDIR /sdk

COPY ./src /sdk/src
COPY ./pyproject.toml /sdk/pyproject.toml

RUN uv build --wheel -o /sdk/distributions

FROM base as final

COPY --from=builder /sdk/distributions /wheels

WORKDIR /app

CMD [ "/usr/bin/sleep", "infinity" ]
