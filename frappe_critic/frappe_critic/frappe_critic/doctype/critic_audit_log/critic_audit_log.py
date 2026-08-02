import frappe
from frappe.model.document import Document


class CriticAuditLog(Document):
    def before_save(self):
        if self.status == "Queued" and not self.started_at:
            self.started_at = frappe.utils.now()

    def on_update(self):
        if self.status == "Done" and not self.finished_at:
            self.finished_at = frappe.utils.now()
