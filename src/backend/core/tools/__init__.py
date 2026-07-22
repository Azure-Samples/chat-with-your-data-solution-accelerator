"""Shared tool helpers used by orchestrators and pipelines.

Namespace package marker. Concrete tools live in sibling modules
(`citations`, `content_safety`, `post_prompt`, `qa`, `text_processing`)
and are imported directly by callers; this file intentionally does not
re-export them so adding a new tool does not require editing this file
(no central registry to keep in sync).
"""
