import frappe
from frappe import _
import json
import os
import requests  # 新增：用于调用 AI 接口

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
        fields=["name", "app", "file_path", "line_start", "line_end", "rule_id", "severity", "message", "code_snippet", "ai_status"],
        start=start,
        limit=limit
    )
    return findings

@frappe.whitelist()
def get_ai_fix(finding_name):
    """调用 AI 获取修复建议"""
    # 1. 获取 Finding 详情
    finding = frappe.get_doc("Critic Finding", finding_name)

    # 2. 获取 AI 配置 (需预先创建 Critic Settings DocType)
    try:
        settings = frappe.get_single("Critic Settings")
    except frappe.DoesNotExistError:
        frappe.throw(_("Please create 'Critic Settings' DocType first."))

    if not settings.api_key:
        frappe.throw(_("Please configure API Key in 'Critic Settings' first."))

    # 3. 构造 Prompt (这里可以根据需要进行脱敏处理)
    prompt = f"""
    You are an expert Frappe Framework developer.
    Analyze the following code issue detected by Semgrep and provide a fix.

    Issue: {finding.message}
    Severity: {finding.severity}

    Code Snippet:
    ```python
    {finding.code_snippet}
    ```

    Please provide:
    1. A short explanation of the vulnerability.
    2. The corrected code snippet using Frappe v15 best practices.
    """

    # 4. 发送 API 请求
    try:
        api_key = settings.get_password("api_key")
        base_url = settings.base_url or "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.model or "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a Frappe Security Expert."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        response = requests.post(base_url, headers=headers, json=payload, timeout=40)
        response.raise_for_status()

        ai_response = response.json()
        suggestion = ai_response['choices'][0]['message']['content']

        # 更新 Finding 状态
        finding.ai_status = "Done"
        finding.save()

        return suggestion

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Critic AI Fix Error")
        frappe.throw(_("AI Fix failed: {0}").format(str(e)))

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
