# Use the official Python 3.11 image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy application files (.env is NOT copied: see .dockerignore.
# Secrets are passed at run time with --env-file, see the Makefile.)
COPY . /app

# Install pip and uv
RUN pip install --no-cache-dir uv

# install dependencies
RUN uv pip install --requirement pyproject.toml --system

# Expose the Streamlit port
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
