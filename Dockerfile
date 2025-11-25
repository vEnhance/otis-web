# This is a development dockerfile, that's made in 5 minutes by Amol Rama
# If it seems bad, feel free to let him know :)
FROM python:3.13-bookworm

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY . .

RUN SETUP=1 ./start.sh

CMD ./start.sh
