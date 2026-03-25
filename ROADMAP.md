# Reddit Watcher Roadmap

## Current State
- Refactoring from Twitter/WhatsApp to Reddit/Discord
- Multi-agent architecture with core/agents/ structure
- Helm chart for Kubernetes deployment

## Phase 1: Core Refactoring (In Progress)
- [x] Discord notification integration (ADR 001)
- [x] Multi-agent architecture design (ADR 002)
- [x] Helm chart structure (ADR 003)
- [x] Update PRD/EDD documentation
- [x] Update README.md
- [ ] **Create ROADMAP.md** (current)
- [ ] **Commit all changes**

## Phase 2: Implementation
- [ ] Remove remaining Twilio/WhatsApp code from codebase
- [ ] Implement Discord tools in `core/tools/`
- [ ] Create Reddit tools in `core/tools/reddit.py`
- [ ] Refactor agents to use new tools
- [ ] Update database migrations (tw_ → rw_ tables)

## Phase 3: Kubernetes Deployment
- [ ] Complete Helm chart with all templates
- [ ] Add ConfigMap and Secret templates
- [ ] Create ingress for monitoring (optional)
- [ ] Set up CronJob schedules

## Phase 4: Testing & Polish
- [ ] Local Docker testing
- [ ] Integration tests
- [ ] Discord webhook validation
- [ ] LLM classification quality check

## Future Enhancements
- Multiple subreddit support
- Keyword filtering per subreddit
- Sentiment analysis
- User mention notifications
- Daily/weekly digest options