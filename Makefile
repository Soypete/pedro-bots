# Override with: make push IMAGE=zot.yourdomain/tweetwatch:latest
IMAGE ?= zot.local/tweetwatch:latest

ENV_FLAGS = \
	-e REDDIT_CLIENT_ID -e REDDIT_CLIENT_SECRET -e REDDIT_USER_AGENT \
	-e TWILIO_ACCOUNT_SID -e TWILIO_AUTH_TOKEN -e TWILIO_FROM_NUMBER -e TWILIO_TO_NUMBER \
	-e POSTGRES_URL \
	-e LLAMA_CPP_BASE_URL -e LLAMA_CPP_MODEL -e LOG_LEVEL \
	--add-host=pedrogpt:100.121.229.114

.PHONY: build monitor suggest push

# Rebuild middleware-py wheel then build the Podman image
build:
	pixi run build-wheel
	podman build -t $(IMAGE) .

# Run the monitor agent locally (op injects secrets from .env)
monitor: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) --agent monitor

# Run the suggestion agent locally (op injects secrets from .env)
suggest: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) --agent suggest

# Push to OCI registry
push:
	podman push $(IMAGE)
