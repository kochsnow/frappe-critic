frappe.pages["critic-dashboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Critic Dashboard",
    single_column: true,
  });

  let selected_apps = [];
  let current_audit_log = null;
  let status_check_interval = null;

  function escape_html(value) {
    return $("<div>").text(value == null ? "" : String(value)).html();
  }

  // Load scan options
  frappe.call({
    method: "frappe_critic.api.get_scan_options",
    callback: function (r) {
      if (r.message) {
        render_dashboard(page, r.message);
      }
    },
  });

  function render_dashboard(page, options) {
    $(page.body).empty();

    // Header section
    const header = $(`
      <div class="row" style="padding: 20px;">
        <div class="col-md-12">
          <div class="card">
            <div class="card-body">
              <h5>Scan Configuration</h5>
              <div class="row" style="margin-top: 15px;">
                <div class="col-md-6">
                  <label><b>Select Apps to Scan:</b></label>
                  <select id="app-select" multiple="multiple" style="width: 100%; height: 150px;">
                  </select>
                  <small class="text-muted">Default: hrms (if installed)</small>
                </div>
                <div class="col-md-6">
                  <label><b>Scan Scope:</b></label>
                  <select id="scope-select" class="form-control">
                    <option value="Installed">Installed Apps</option>
                    <option value="Bench">All Bench Apps (Slow)</option>
                  </select>
                </div>
              </div>
              <div style="margin-top: 15px;">
                <button id="start-scan-btn" class="btn btn-primary">Start Scan</button>
                <button id="refresh-btn" class="btn btn-default">Refresh Findings</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `).appendTo(page.body);

    // Populate app select
    const app_select = header.find("#app-select");
    options.installed_apps.forEach((app) => {
      const option = $("<option></option>").val(app).text(app);
      if (options.primary_apps.includes(app)) {
        option.prop("selected", true);
      }
      app_select.append(option);
    });

    // Status section
    const status_section = $(`
      <div class="row" style="padding: 0 20px;">
        <div class="col-md-12">
          <div class="card">
            <div class="card-body">
              <h5>Scan Status</h5>
              <div id="scan-status" class="text-muted">No scan initiated</div>
              <div id="scan-stats" style="margin-top: 10px;"></div>
            </div>
          </div>
        </div>
      </div>
    `).appendTo(page.body);

    // Findings section
    const findings_section = $(`
      <div class="row" style="padding: 0 20px 20px 20px;">
        <div class="col-md-12">
          <div class="card">
            <div class="card-body">
              <h5>Findings</h5>
              <div id="findings-container"></div>
            </div>
          </div>
        </div>
      </div>
    `).appendTo(page.body);

    // Event handlers
    header.find("#start-scan-btn").on("click", function () {
      const $btn = $(this);
      const selected = app_select.val() || [];
      const scope = header.find("#scope-select").val();

      if (selected.length === 0) {
        frappe.msgprint("Please select at least one app to scan");
        return;
      }

      $btn.prop("disabled", true).text(__("Scanning..."));

      start_scan(selected, scope, $btn);
    });

    header.find("#refresh-btn").on("click", function () {
      if (current_audit_log) {
        load_findings(current_audit_log);
      }
    });
  }

  function start_scan(apps, scope, $btn) {
    frappe.call({
      method: "frappe_critic.api.start_scan",
      args: {
        selected_apps: JSON.stringify(apps),
        scope: scope,
      },
      callback: function (r) {
        if (r.message && r.message.audit_log_name) {
          current_audit_log = r.message.audit_log_name;
          check_scan_status($btn);
        } else {
          $btn.prop("disabled", false).text(__("Start Scan"));
        }
      },
    });
  }

  function check_scan_status($btn) {
    if (!current_audit_log) return;

    frappe.call({
      method: "frappe_critic.api.get_scan_status",
      args: {
        audit_log_name: current_audit_log,
      },
      callback: function (r) {
        if (r.message) {
          update_status_display(r.message);

          if (r.message.status === "Running" || r.message.status === "Queued") {
            if (status_check_interval) clearTimeout(status_check_interval);

            status_check_interval = setTimeout(function() {
              check_scan_status($btn);
            }, 3000);
          } else if (r.message.status === "Done") {
            if (status_check_interval) clearTimeout(status_check_interval);

            if ($btn) {
              $btn.prop("disabled", false).text(__("Start Scan"));
            }

            frappe.show_alert({
              message: __("Scan Complete! Found {0} issues.", [r.message.total_findings]),
              indicator: 'orange'
            });

            load_findings(current_audit_log);
          } else if (r.message.status === "Failed") {
            if (status_check_interval) clearTimeout(status_check_interval);

            if ($btn) {
              $btn.prop("disabled", false).text(__("Start Scan"));
            }

            frappe.msgprint({
              title: __('Scan Failed'),
              indicator: 'red',
              message: r.message.error || __("Unknown error occurred during scan.")
            });
          }
        }
      },
      error: function() {
        if (status_check_interval) clearTimeout(status_check_interval);
        if ($btn) $btn.prop("disabled", false).text(__("Start Scan"));
      }
    });
  }

  function update_status_display(status_data) {
    const status_div = $("#scan-status");
    const stats_div = $("#scan-stats");

    const status_colors = {
      Queued: "text-warning",
      Running: "text-info",
      Done: "text-success",
      Failed: "text-danger",
    };

    status_div.html(
      `<span class="${status_colors[status_data.status]}"><b>Status:</b> ${status_data.status}</span>`
    );

    if (status_data.status === "Done") {
      stats_div.html(`
        <div>
          <span><b>Total Findings:</b> ${status_data.total_findings}</span> |
          <span><b>Risk Score:</b> ${status_data.risk_score}/100</span>
        </div>
      `);
    }
  }

  function load_findings(audit_log_name) {
    frappe.call({
      method: "frappe_critic.api.get_findings",
      args: {
        audit_log_name: audit_log_name,
      },
      callback: function (r) {
        if (r.message) {
          render_findings(r.message);
        }
      },
    });
  }

  function render_findings(findings) {
    const container = $("#findings-container");
    container.empty();

    if (!findings || findings.length === 0) {
      container.html(`
        <div class="text-center text-muted" style="padding: 40px;">
            <i class="fa fa-check-circle fa-3x" style="color: #28a745; margin-bottom: 10px;"></i>
            <p>${__("No issues found! Your codebase looks clean.")}</p>
        </div>
      `);
      return;
    }

    const table = $(`
      <div class="table-responsive">
      <table class="table table-bordered">
        <thead>
          <tr>
            <th>App</th>
            <th>File</th>
            <th>Line</th>
            <th>Severity</th>
            <th>Message</th>
            <th>AI Fix</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
      </div>
    `).appendTo(container);

    const tbody = table.find("tbody");

    findings.forEach((finding) => {
      const severity_colors = {
        Critical: "danger",
        High: "warning",
        Medium: "info",
        Low: "default",
        Info: "secondary",
      };

      const is_prepared = finding.remediation_status === "Ready";
      const button_label = is_prepared ? __("View Harbor Task") : __("Prepare AI Fix");
      const row = $(`
        <tr>
          <td>${escape_html(finding.app)}</td>
          <td>${escape_html(finding.file_path)}</td>
          <td>${escape_html(finding.line_start)}</td>
          <td><span class="label label-${severity_colors[finding.severity] || "default"}">${escape_html(finding.severity)}</span></td>
          <td>${escape_html(finding.message)}</td>
          <td>
            <button class="btn btn-xs btn-primary ai-fix-btn" data-finding="${escape_html(finding.name)}">
              ${escape_html(button_label)}
            </button>
            <div class="text-muted" style="margin-top: 4px; font-size: 11px;">${escape_html(finding.remediation_status || "NotPrepared")}</div>
          </td>
        </tr>
      `).appendTo(tbody);
    });

    tbody.find(".ai-fix-btn").on("click", function () {
      const $button = $(this);
      const finding_name = $(this).data("finding");
      const original_label = $button.text().trim();

      const d = new frappe.ui.Dialog({
        title: __('Harbor Remediation Task'),
        size: 'extra-large',
        fields: [
          { fieldname: 'preview_body', fieldtype: 'HTML' }
        ]
      });

      d.show();
      d.fields_dict.preview_body.$wrapper.html(`
        <div class="alert alert-blue">
          <b>${escape_html(__("Prepare only"))}</b>: ${escape_html(__("No Agent will run and no source files will be changed."))}
        </div>
        <div class="text-muted">${escape_html(__("Converting the finding into a private Harbor task package..."))}</div>
      `);
      $button.prop("disabled", true).text(__("Preparing..."));

      frappe.call({
        method: "frappe_critic.api.prepare_harbor_task",
        args: { finding_name: finding_name },
        callback: function (r) {
          const result = r.message;
          if (result && result.ok) {
            render_harbor_task(d, result);
            $button.text(__("View Harbor Task"));
            $button.siblings(".text-muted").text(result.status);
          } else {
            const message = (result && result.error) || __("Harbor task preparation returned no artifact.");
            render_harbor_error(d, message);
            $button.text(original_label);
            $button.siblings(".text-muted").text("Failed");
          }
        },
        error: function () {
          render_harbor_error(d, __("Harbor task preparation failed. Check the server error log for details."));
          $button.text(original_label);
          $button.siblings(".text-muted").text("Failed");
        },
        always: function () {
          $button.prop("disabled", false);
        }
      });
    });
  }

  function render_harbor_task(dialog, task) {
    const cached_note = task.cached
      ? `<span class="text-muted">${escape_html(__("Loaded saved task"))}</span>`
      : `<span class="text-success">${escape_html(__("New Harbor task saved"))}</span>`;
    const download_link = task.task_archive
      ? `<a class="btn btn-sm btn-default" href="${escape_html(task.task_archive)}" target="_blank">${escape_html(__("Download Task Package"))}</a>`
      : "";

    dialog.fields_dict.preview_body.$wrapper.html(`
      <div class="alert alert-blue">
        <b>${escape_html(__("Harbor task ready"))}</b>: ${escape_html(__("No Agent ran and no source files were changed."))}
      </div>
      <div style="margin-bottom: 16px;">
        ${cached_note}<br>
        <span class="text-muted">${escape_html(task.task_name)} · Harbor schema ${escape_html(task.harbor_schema_version)}</span>
      </div>
      <h5>${escape_html(__("Private task path"))}</h5>
      <pre>${escape_html(task.task_path)}</pre>
      <h5>${escape_html(__("Artifact SHA-256"))}</h5>
      <pre>${escape_html(task.task_sha256)}</pre>
      <div style="margin-top: 16px;">${download_link}</div>
    `);
  }

  function render_harbor_error(dialog, message) {
    dialog.fields_dict.preview_body.$wrapper.html(`
      <div class="alert alert-danger">
        <b>${escape_html(__("Harbor task preparation failed"))}</b><br>
        <span style="white-space: pre-wrap;">${escape_html(message)}</span>
      </div>
      <p class="text-muted">${escape_html(__("No Agent ran and no source files were changed."))}</p>
    `);
  }
};
