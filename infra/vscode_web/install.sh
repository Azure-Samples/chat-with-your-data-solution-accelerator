pip install -r requirements.txt --user -q

# Install uv so the post-deployment step resolves its Python deps from the
# cloned repo's pyproject.toml (single source of truth) instead of a
# separate hand-maintained requirements list.
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

azd init -t Azure-Samples/chat-with-your-data-solution-accelerator

# Sync the cloned repo's environment from pyproject.toml so the
# post-deployment step runs against the same dependency versions as the app.
uv sync
