# Makefile

# --- Configurable variables ---
IMAGE_NAME=interview-prep:main-latest
PORT=8501
ENV_FILE=.env
VENV_DIR=.venv

.PHONY: build run rebuild clean help

# ================================
# === Docker Commands ============
# ================================
# NOTE: the interviewer's voice is played with pygame on the machine that runs the
# server. Inside Docker there is no sound device, so the voice cannot be heard.
# Run the app locally for the full experience (see README.md).
# NOTE: docker --env-file does not strip quotes, so write KEY=value (no quotes)
# in .env when you use these targets.

build:
	sudo docker build -t $(IMAGE_NAME) .

run:
	sudo docker run --env-file $(ENV_FILE) -p $(PORT):$(PORT) $(IMAGE_NAME)

rebuild: clean build run

clean:
	- sudo docker rm -f $(IMAGE_NAME)-container
	# Optional: remove image
	# - sudo docker rmi $(IMAGE_NAME)

# ================================
# === Helper =====================
# ================================

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Docker targets:"
	@echo "  build         Build Docker image"
	@echo "  run           Run Docker container with env"
	@echo "  rebuild       Clean and rebuild Docker image"
	@echo "  clean         Stop and remove Docker container"
