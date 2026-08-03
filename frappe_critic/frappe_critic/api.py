import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse
import zipfile

import frappe
from frappe import _
import requests

from frappe_critic.ai_fix import AIResponseError, build_fix_prompt, build_preview
from frappe_critic.harbor_task import (
    HARBOR_SCHEMA_VERSION,
    HarborFinding,
    build_harbor_task_package,
    sha256_file,
)

@frappe.whitelist()
def get_scan_options():
    """返回扫描选项，包括已安装的应用"""
    installed_apps = frappe.get_installed_apps()

    # 过滤掉不需要扫描的系统基础应用
    system_apps = ["frappe", "payments"]
    user_apps = [app for app in installed_apps if app not in system_apps]

    # 如果安装了 hrms，将其作为首选建议
    primary_apps = []
    if "hrms" in installed_apps:
        primary_apps.append("hrms")

    return {
        "installed_apps": installed_apps,
        "user_apps": user_apps,
        "primary_apps": primary_apps,
        "scopes": ["Installed", "Bench"]
    }

@frappe.whitelist()
def start_scan(selected_apps, scope="Installed"):
    """开始扫描任务并返回审计日志名称"""
    if isinstance(selected_apps, str):
        selected_apps = json.loads(selected_apps)

    # 创建审计日志记录
    audit_log = frappe.get_doc({
        "doctype": "Critic Audit Log",
        "status": "Queued",
        "scope": scope,
        "selected_apps_json": json.dumps(selected_apps),
        "ruleset": "bundled"
    })
    audit_log.insert()

    # 核心修复：确保 enqueue 指向正确的 API 路径 (L2层)
    frappe.enqueue(
        "frappe_critic.api.run_scan_job",
        audit_log_name=audit_log.name,
        selected_apps=selected_apps,
        queue="long"
    )

    return {"audit_log_name": audit_log.name}

@frappe.whitelist()
def get_scan_status(audit_log_name):
    """获取当前扫描状态（供前端轮询）"""
    audit_log = frappe.get_doc("Critic Audit Log", audit_log_name)
    return {
        "status": audit_log.status,
        "total_findings": audit_log.total_findings or 0,
        "risk_score": audit_log.risk_score or 0,
        "started_at": audit_log.started_at,
        "finished_at": audit_log.finished_at,
        "error": audit_log.error
    }

@frappe.whitelist()
def get_findings(audit_log_name, start=0, limit=100):
    """获取扫描发现的问题列表"""
    findings = frappe.db.get_all(
        "Critic Finding",
        filters={"audit_log": audit_log_name},
        fields=[
            "name", "app", "file_path", "line_start", "line_end", "rule_id",
            "severity", "message", "code_snippet", "ai_status",
            "remediation_status", "latest_remediation_task",
        ],
        start=start,
        limit=limit
    )
    return findings


@frappe.whitelist()
def prepare_harbor_task(finding_name, regenerate=False):
    """Convert one finding into a private, runnable Harbor task package."""
    frappe.only_for("System Manager")
    finding = frappe.get_doc("Critic Finding", finding_name)
    if not frappe.has_permission("Critic Finding", "read", doc=finding):
        frappe.throw(_("Not permitted to view this finding."), frappe.PermissionError)

    regenerate = str(regenerate).lower() in {"1", "true", "yes"}
    if not regenerate and finding.latest_remediation_task:
        existing = frappe.get_doc("Critic Remediation Task", finding.latest_remediation_task)
        if existing.status == "Ready":
            return _harbor_task_response(existing, cached=True)

    task_doc = frappe.get_doc({
        "doctype": "Critic Remediation Task",
        "finding": finding.name,
        "status": "Preparing",
        "harbor_schema_version": HARBOR_SCHEMA_VERSION,
    }).insert()

    finding.remediation_status = "Preparing"
    finding.latest_remediation_task = task_doc.name
    finding.save()

    task_root = Path(
        frappe.get_site_path("private", "frappe_critic", "harbor_tasks")
    )
    task_root.mkdir(parents=True, exist_ok=True)
    final_path = task_root / task_doc.name.lower()
    temporary_path = task_root / f".{task_doc.name.lower()}.tmp"

    try:
        source_path, app_root = _resolve_finding_source(finding)
        source_hash = finding.source_sha256 or sha256_file(source_path)
        result = build_harbor_task_package(
            output_dir=temporary_path,
            finding=HarborFinding(
                name=finding.name,
                audit_log=finding.audit_log,
                app=finding.app,
                file_path=finding.file_path,
                line_start=finding.line_start,
                line_end=finding.line_end,
                rule_id=finding.rule_id or "unknown-rule",
                severity=finding.severity or "Info",
                message=finding.message or "",
                code_snippet=finding.code_snippet or "",
                source_sha256=source_hash,
                base_commit=_git_commit(app_root),
            ),
            source_file=source_path,
            rules_dir=Path(frappe.get_app_path("frappe_critic", "..", "rules", "rules")),
        )
        temporary_path.rename(final_path)

        from frappe.utils.file_manager import save_file

        archive = save_file(
            f"{task_doc.name.lower()}-harbor-task.zip",
            _zip_task(final_path),
            "Critic Remediation Task",
            task_doc.name,
            is_private=1,
        )

        task_doc.status = "Ready"
        task_doc.task_name = result.task_name
        task_doc.task_path = str(final_path.relative_to(Path(frappe.get_site_path())))
        task_doc.task_archive = archive.file_url
        task_doc.task_sha256 = result.task_sha256
        task_doc.source_sha256 = result.source_sha256
        task_doc.error = None
        task_doc.save()

        finding.remediation_status = "Ready"
        finding.latest_remediation_task = task_doc.name
        finding.save()
        return _harbor_task_response(task_doc, cached=False)

    except Exception as exc:
        shutil.rmtree(temporary_path, ignore_errors=True)
        shutil.rmtree(final_path, ignore_errors=True)
        frappe.log_error(frappe.get_traceback(), "Critic Harbor Task Error")
        task_doc.status = "Failed"
        task_doc.error = str(exc)[:2000]
        task_doc.save()
        finding.remediation_status = "Failed"
        finding.latest_remediation_task = task_doc.name
        finding.save()
        return {
            "ok": False,
            "status": "Failed",
            "remediation_task": task_doc.name,
            "error": task_doc.error,
        }


def _harbor_task_response(task_doc, cached):
    return {
        "ok": True,
        "status": task_doc.status,
        "cached": cached,
        "remediation_task": task_doc.name,
        "harbor_schema_version": task_doc.harbor_schema_version,
        "task_name": task_doc.task_name,
        "task_path": task_doc.task_path,
        "task_archive": task_doc.task_archive,
        "task_sha256": task_doc.task_sha256,
        "source_sha256": task_doc.source_sha256,
    }


def _resolve_finding_source(finding):
    apps_root = Path(frappe.get_app_path("frappe", "..", "..")).resolve()
    app_root = (apps_root / finding.app).resolve()
    source_path = (apps_root / finding.file_path).resolve()
    if not source_path.is_relative_to(app_root):
        raise ValueError(_("Finding path is outside the selected app."))
    if not source_path.is_file():
        raise FileNotFoundError(_("Finding source file no longer exists: {0}").format(finding.file_path))
    return source_path, app_root


def _git_commit(app_root):
    result = subprocess.run(
        ["git", "-C", str(app_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _zip_task(task_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in task_path.rglob("*") if item.is_file()):
            archive.write(path, Path(task_path.name) / path.relative_to(task_path))
    return buffer.getvalue()

@frappe.whitelist()
def get_ai_fix(finding_name, regenerate=False):
    """Generate or return a review-only AI fix preview.

    This endpoint never modifies scanned source files. A successful preview is
    deliberately stored as ``Previewed``; ``Done`` is reserved for a future,
    explicitly confirmed apply-and-verify workflow.
    """
    frappe.only_for("System Manager")
    finding = frappe.get_doc("Critic Finding", finding_name)
    if not frappe.has_permission("Critic Finding", "read", doc=finding):
        frappe.throw(_("Not permitted to view this finding."), frappe.PermissionError)

    regenerate = str(regenerate).lower() in {"1", "true", "yes"}
    if finding.ai_status == "Previewed" and finding.ai_fix and not regenerate:
        return _preview_response(finding, cached=True)

    if not frappe.db.exists("DocType", "Critic Settings"):
        return _record_ai_failure(
            finding,
            _("Critic Settings is not installed. Run bench migrate and try again."),
        )

    settings = frappe.get_single("Critic Settings")
    api_key = settings.get_password("api_key", raise_exception=False)
    if not api_key:
        return _record_ai_failure(
            finding,
            _("AI Fix is not configured. Add an API key in Critic Settings."),
        )

    endpoint = settings.base_url or "https://api.openai.com/v1/chat/completions"
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
        return _record_ai_failure(
            finding,
            _("Critic Settings contains an invalid Chat Completions URL."),
        )

    model = settings.model or "gpt-4o"
    finding.ai_status = "Requested"
    finding.ai_error = None
    finding.save()

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You create minimal, reviewable Frappe security patches.",
                    },
                    {"role": "user", "content": build_fix_prompt(finding)},
                ],
                "temperature": 0.1,
            },
            timeout=(10, 60),
        )
        if not response.ok:
            raise AIResponseError(_provider_error(response))

        preview = build_preview(finding, response.json(), model)
        finding.ai_status = "Previewed"
        finding.ai_model = preview["model"]
        finding.ai_explanation = preview["explanation"]
        finding.ai_fix = preview["corrected_code"]
        finding.ai_patch = preview["patch"]
        finding.ai_response = preview["raw_response"]
        finding.ai_error = None
        finding.save()
        return _preview_response(finding, cached=False)

    except (requests.RequestException, ValueError) as exc:
        frappe.log_error(frappe.get_traceback(), "Critic AI Fix Preview Error")
        return _record_ai_failure(finding, _("AI Fix preview failed: {0}").format(str(exc)))


def _preview_response(finding, cached):
    return {
        "ok": True,
        "status": finding.ai_status,
        "cached": cached,
        "preview_only": True,
        "finding_name": finding.name,
        "file_path": finding.file_path,
        "model": finding.ai_model,
        "explanation": finding.ai_explanation,
        "corrected_code": finding.ai_fix,
        "patch": finding.ai_patch,
    }


def _record_ai_failure(finding, message):
    finding.ai_status = "Failed"
    finding.ai_error = str(message)[:2000]
    finding.save()
    return {
        "ok": False,
        "status": "Failed",
        "preview_only": True,
        "finding_name": finding.name,
        "error": finding.ai_error,
    }


def _provider_error(response):
    try:
        data = response.json()
        error = data.get("error", {}) if isinstance(data, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else None
    except ValueError:
        detail = None
    return _("AI provider returned HTTP {0}: {1}").format(
        response.status_code,
        (detail or response.reason or _("Unknown provider error"))[:500],
    )

def run_scan_job(audit_log_name, selected_apps):
    """后台执行 Semgrep 扫描的任务"""
    audit_log = frappe.get_doc("Critic Audit Log", audit_log_name)

    try:
        audit_log.status = "Running"
        audit_log.save()

        # 导入扫描器类 (注意套娃路径)
        from frappe_critic.frappe_critic.scanner.code_analyzer import CodeAnalyzer

        # 推导规则路径 (L2 -> L1/rules/rules)
        rules_path = os.path.join(frappe.get_app_path("frappe_critic"), "..", "rules", "rules")

        analyzer = CodeAnalyzer(rules_path=rules_path)

        all_findings = []
        for app_name in selected_apps:
            app_path = frappe.get_app_path(app_name)
            candidates = analyzer.analyze(app_path)

            severity_map = {
                "ERROR": "High",
                "WARNING": "Medium",
                "INFO": "Info"
            }

            for candidate in candidates:
                raw_severity = candidate.extra.get("severity", "INFO").upper()
                mapped_severity = severity_map.get(raw_severity, "Info")

                raw_path = candidate.file_path

                # Store paths relative to the bench apps directory when possible.
                apps_base_dir = os.path.abspath(frappe.get_app_path("frappe", "..", ".."))

                try:
                    display_path = os.path.relpath(raw_path, apps_base_dir)
                except ValueError:
                    display_path = raw_path.split("apps/")[-1] if "apps/" in raw_path else raw_path


                finding_doc = frappe.get_doc({
                    "doctype": "Critic Finding",
                    "audit_log": audit_log_name,
                    "app": app_name,
                    "file_path": display_path,
                    "line_start": candidate.line_start,
                    "line_end": candidate.line_end,
                    "rule_id": candidate.rule_id,
                    "severity": mapped_severity,
                    "message": candidate.raw_reason,
                    "code_snippet": candidate.code_snippet,
                    "source_sha256": sha256_file(Path(raw_path)),
                    "ai_status": "NotRequested"
                })
                finding_doc.insert()
                all_findings.append(finding_doc)

        total_findings = len(all_findings)
        severity_counts = {}
        for f in all_findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        # 计算风险分数
        risk_score = max(0, 100 - (total_findings * 2))

        audit_log.total_findings = total_findings
        audit_log.risk_score = risk_score
        audit_log.summary_json = json.dumps({
            "severity_counts": severity_counts,
            "total_findings": total_findings
        })
        audit_log.status = "Done"
        audit_log.save()

    except Exception as e:
        audit_log.status = "Failed"
        audit_log.error = str(e)
        audit_log.save()
        # 记录详细错误日志到 Frappe Error Log
        frappe.log_error(frappe.get_traceback(), "Critic Scan Error")
