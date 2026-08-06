# Override with: make push IMAGE=zot.yourdomain/redditwatch:latest
IMAGE ?= 100.81.89.62:5000/redditwatch:latest

ENV_FLAGS = \
	-e REDDIT_CLIENT_ID -e REDDIT_CLIENT_SECRET -e REDDIT_USER_AGENT \
	-e DISCORD_BOT_TOKEN -e DISCORD_CHANNEL_ID -e DISCORD_NOTIFY_USER_ID \
	-e SUPABASE_URL -e SUPABASE_SERVICE_KEY \
	-e POSTGRES_URL \
	-e LLAMA_CPP_BASE_URL -e LLAMA_CPP_MODEL -e LOG_LEVEL \
	--add-host=pedrogpt:100.121.229.114

.PHONY: build monitor suggest social cfp push

# Rebuild middleware-py wheel then build the Podman image
build:
	pixi run build-wheel
	podman build --platform linux/amd64 -t $(IMAGE) .

# Run the monitor agent locally (op injects secrets from .env)
monitor: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) -- agent --agent monitor

# Run the suggestion agent locally (op injects secrets from .env)
suggest: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) agent --agent suggest

# Run the social poster agent locally
social: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) agent --agent social-poster

# Run the CFP watch agent locally
cfp: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) agent --agent cfp

# Run CFP in dry-run mode (no Discord post)
cfp-dry: build
	op run --env-file=.env -- podman run --rm $(ENV_FLAGS) $(IMAGE) agent --agent cfp --dry-run

# Push to OCI registry
push:
	podman push $(IMAGE)