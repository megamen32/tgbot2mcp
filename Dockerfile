FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/
COPY README.md .

# Install the package
RUN pip install --no-cache-dir .

# Create session directory
RUN mkdir -p /root/.tgbot2mcp/sessions

# Default entrypoint
ENTRYPOINT ["tgbot2mcp"]
CMD ["--help"]
