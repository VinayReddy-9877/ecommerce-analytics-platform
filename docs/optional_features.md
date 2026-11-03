# Optional features

The core project is the historical weekly operating review.

Dataset upload is available through Workspace > Upload data. It profiles CSV/XLSX
files and computes sales metrics after explicit column mapping; it does not infer
arbitrary business semantics or joins. See new_data.md.

The default report is deterministic. For an optional AI draft, install
`pip install -e ".[ai]"`, configure OPENAI_MODEL and OPENAI_API_KEY locally, and
run `olist report --llm`. API costs apply. Drafts are numerically constrained but
still require review; no live API output is bundled or claimed as verified.
