# Publishing tgbot2mcp

Pushes to `main` and manual runs execute the mocked test suite and build both
Python distributions. They do not publish a package or contact Telegram.

Releases use a PyPI API token scoped to the existing `tgbot2mcp` project,
installed as the GitHub repository secret `PYPI_API_TOKEN`. `uv` receives it
only through the masked Actions secret `UV_PUBLISH_TOKEN`. Trusted Publishing
is explicitly disabled for this token-based configuration; a PyPI OIDC
publisher registration is not required. Never place the token in source,
issues, command arguments, or chat.

For a release, update `project.version` in `pyproject.toml`, commit and push
`main`, then create its matching new `v<version>` tag. Tag publication requires
successful tests and build. Existing version `0.1.0` and tag `v0.1.0` are
immutable; do not overwrite or delete them to repair publisher settings.
`--check-url` skips files that already exist; a skipped upload does not prove a
new release or verify an API token. A real publication is accepted only after
PyPI shows the new version and its uploaded distribution hashes.

API token help: https://pypi.org/help/#apitoken
uv publishing: https://docs.astral.sh/uv/guides/publish/
