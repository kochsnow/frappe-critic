"""Code analyzer using Semgrep for static analysis."""

import json
import subprocess
import os
import frappe
from pathlib import Path

try:
    from frappe_critic.frappe_critic.models.issue import IssueCandidate
except ImportError:
    from frappe_critic.models.issue import IssueCandidate


class CodeAnalyzer:
    def __init__(self, rules_path: str = None, semgrep_bin: str = "semgrep") -> None:
        """
        Initialize the Semgrep code analyzer.

        Args:
            rules_path: Path to the Semgrep rules directory. If omitted, the
                bundled rules directory is inferred automatically.
            semgrep_bin: Semgrep executable path.
        """
        self.semgrep_bin = semgrep_bin

        if not rules_path:
            self.rules_path = frappe.get_app_path("frappe_critic", "..", "rules", "rules")
        else:
            self.rules_path = rules_path

    def analyze(self, directory: str) -> list[IssueCandidate]:
        print(f"--- [Critic] Starting scan ---")
        print(f"--- Target Dir: {directory}")
        print(f"--- Rules Path: {self.rules_path}")

        if not os.path.exists(self.rules_path):
            raise FileNotFoundError(f"Critic Rules not found at: {os.path.abspath(self.rules_path)}")

        if not os.path.exists(directory):
            raise FileNotFoundError(f"Scan target directory not found: {directory}")

        cmd = [
            self.semgrep_bin,
            "--config", self.rules_path,
            "--json",
            directory
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False, # Semgrep 发现漏洞会返回 1，所以不能 check=True
                timeout=300  # 5分钟超时
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Semgrep binary '{self.semgrep_bin}' not found. Run 'pip install semgrep' in container.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Semgrep scan timed out.")

        # Semgrep 返回码处理：0 (无结果), 1 (有结果), 其他 (错误)
        if result.returncode not in [0, 1]:
            raise RuntimeError(f"Semgrep Error (Code {result.returncode}): {result.stderr}")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            # 如果 stdout 为空，可能是没装好或规则有错
            if not result.stdout and result.stderr:
                raise RuntimeError(f"Semgrep stderr: {result.stderr}")
            return []

        candidates = []
        for finding in data.get("results", []):
            code_snippet = finding.get("extra", {}).get("lines", "")

            candidate = IssueCandidate(
                file_path=finding["path"],
                line_start=finding["start"]["line"],
                line_end=finding["end"]["line"],
                code_snippet=code_snippet,
                raw_reason=finding.get("extra", {}).get("message", ""),
                rule_id=finding.get("check_id"),
                extra={
                    "severity": finding.get("extra", {}).get("severity", "INFO"),
                    "metadata": finding.get("extra", {}).get("metadata", {}),
                    "fix": finding.get("extra", {}).get("fix"),
                }
            )
            candidates.append(candidate)

        print(f"--- [Critic] Scan completed. Found {len(candidates)} issues. ---")
        return candidates
