# Repository guidance

- Python 3.14 is managed with uv. Use `uv sync --locked` and run Python commands with `uv run`.
- Preserve existing CLI, scraper, configuration, and output behavior unless the task explicitly changes it.
- Keep credentials, local configuration, caches, generated data, and virtual environments out of Git.
- Verification must not contact real targets unless the user explicitly requests and authorizes it.
- Ask before every commit. Ask separately before any push or PR.
