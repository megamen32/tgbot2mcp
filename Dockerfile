FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN mkdir -p /data/sessions

ENV TGBOT2MCP_HOME=/data

VOLUME ["/data"]

ENTRYPOINT ["tgbot2mcp"]
CMD ["--help"]
