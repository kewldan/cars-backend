FROM ghcr.io/astral-sh/uv:python3.14-alpine

WORKDIR /usr/app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked

COPY ./src src

ENV TZ="Europe/Moscow"

CMD [ "uv", "run", "src/main.py" ]
