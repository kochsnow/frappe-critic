import unittest
from types import SimpleNamespace

from frappe_critic.ai_fix import AIResponseError, build_patch, build_preview, parse_fix_response


class AIFixPreviewTest(unittest.TestCase):
	def setUp(self):
		self.finding = SimpleNamespace(
			app="hrms",
			file_path="hrms/hrms/overrides/employee_master.py",
			line_start=14,
			line_end=14,
			rule_id="frappe-single-value-type-safety",
			severity="High",
			message="Use get_single_value for Single DocTypes",
			code_snippet='naming_method = frappe.db.get_value("HR Settings", None, "emp_created_by")',
		)

	def test_builds_unified_diff_preview(self):
		response = {
			"choices": [
				{
					"message": {
						"content": (
							'{"explanation":"Use the Single DocType API.",'
							'"corrected_code":"naming_method = frappe.db.get_single_value('
							'\\"HR Settings\\", \\"emp_created_by\\")"}'
						)
					}
				}
			]
		}

		preview = build_preview(self.finding, response, "test-model")

		self.assertIn("--- a/hrms/hrms/overrides/employee_master.py", preview["patch"])
		self.assertIn("+naming_method = frappe.db.get_single_value", preview["patch"])
		self.assertEqual(preview["model"], "test-model")

	def test_accepts_json_fence_but_strips_code_fence(self):
		parsed = parse_fix_response(
			'```json\n{"explanation":"Safer", "corrected_code":"```python\\nfixed()\\n```"}\n```'
		)
		self.assertEqual(parsed["corrected_code"], "fixed()")

	def test_rejects_non_json_provider_output(self):
		with self.assertRaises(AIResponseError):
			parse_fix_response("Here is a suggested fix")

	def test_rejects_noop_patch(self):
		with self.assertRaises(AIResponseError):
			build_patch("example.py", "same()", "same()")


if __name__ == "__main__":
	unittest.main()
