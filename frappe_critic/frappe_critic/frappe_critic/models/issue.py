"""Data models for code analysis issues.

This module defines the core data structures used throughout the scanner:
- IssueCandidate: Raw issue detected by static analysis tools
- Issue: Structured issue format for agents and terminal-bench
"""

from dataclasses import dataclass, field


@dataclass
class IssueCandidate:
    """Represents a candidate issue detected by static analysis tools.

    This is the raw output from scanners like Semgrep before further processing.
    Contains minimal structured information about the potential issue.

    Attributes:
        file_path: Path to the file containing the issue
        line_start: Starting line number of the issue (1-indexed)
        line_end: Ending line number of the issue (1-indexed)
        code_snippet: The relevant code snippet
        raw_reason: Initial reason provided by the static analysis tool
        rule_id: Optional identifier of the rule that triggered this issue
        extra: Additional metadata from the scanner (e.g., severity, fix hints)
    """
    file_path: str
    line_start: int
    line_end: int
    code_snippet: str
    raw_reason: str
    rule_id: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class Issue:
    """Represents a structured issue for consumption by agents or terminal-bench.

    This is the processed format that provides comprehensive context for
    automated or human review. Issues are created from IssueCandidate objects
    after enrichment and validation.

    Attributes:
        id: Unique identifier for this issue
        title: Brief, actionable title describing the issue
        description: Detailed description for agents/terminal-bench, including
                    context, impact, and suggested remediation
        file_path: Path to the file containing the issue
        line_start: Starting line number (1-indexed)
        line_end: Ending line number (1-indexed)
        severity: Issue severity level (e.g., "critical", "high", "medium", "low")
        tags: List of tags for categorization (e.g., ["security", "performance"])
        metadata: Additional structured information (e.g., CWE IDs, references)
    """
    id: str
    title: str
    description: str
    file_path: str
    line_start: int
    line_end: int
    severity: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
