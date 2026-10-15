pip install -r requirements.txt --user -q

# Install uv so the post-deployment step resolves its Python deps from the
# cloned repo's pyproject.toml (single source of truth) instead of a
# separate hand-maintained requirements list.
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

azd init -t Azure-Samples/chat-with-your-data-solution-accelerator

# azd init clones the template into a subdirectory; sync from inside it.
cd chat-with-your-data-solution-accelerator

# Install only the post-provision hook's deps (pyproject `provision` group),
# not the full runtime graph, so the sandbox sync stays fast.
uv sync --only-group provision
