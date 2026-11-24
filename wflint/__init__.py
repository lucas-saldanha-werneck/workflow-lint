"""workflow-lint: static checks for n8n-style workflow JSON exports."""
from .lint import lint_workflow, Finding

__all__ = ["lint_workflow", "Finding"]
