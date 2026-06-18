"""MARS internal deployment tool — a Streamlit wrapper around the existing
multi-agent research pipeline. See MARS_BUILD_SPEC.md and README.md.

This package is self-contained: it ports the agent prompts and pipeline
semantics from the v2.1 `backend/` app, but routes all inference through a
single per-agent routing layer (mars.models) configured by config.yaml.
"""

__version__ = "1.0.0"
