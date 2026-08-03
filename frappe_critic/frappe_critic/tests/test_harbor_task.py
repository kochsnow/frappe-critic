import py_compile
import tempfile
import unittest
from pathlib import Path

try:
	import tomllib
except ModuleNotFoundError:  # Python < 3.11; Frappe container validation uses tomllib.
	tomllib = None

from frappe_critic.harbor_task import (
	HARBOR_SCHEMA_VERSION,
	HarborFinding,
	HarborTaskError,
	build_harbor_task_package,
	sha256_file,
)


class HarborTaskBuilderTest(unittest.TestCase):
	def setUp(self):
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.root = Path(self.temporary_directory.name)
		self.source = self.root / "employee_master.py"
		self.source.write_text(
			'naming_method = frappe.db.get_value("HR Settings", None, "emp_created_by")\n',
			encoding="utf-8",
		)
		self.rules = self.root / "rules"
		self.rules.mkdir()
		(self.rules / "frappe.yml").write_text(
			"rules:\n  - id: frappe-single-value-type-safety\n"
			"    languages: [python]\n    message: use get_single_value\n"
			"    severity: WARNING\n    pattern: frappe.db.get_value(...)\n",
			encoding="utf-8",
		)

	def tearDown(self):
		self.temporary_directory.cleanup()

	def finding(self, **overrides):
		values = {
			"name": "abc123",
			"audit_log": "audit-1",
			"app": "hrms",
			"file_path": "hrms/hrms/overrides/employee_master.py",
			"line_start": 14,
			"line_end": 14,
			"rule_id": "frappe-single-value-type-safety",
			"severity": "High",
			"message": "Use get_single_value for Single DocTypes",
			"code_snippet": self.source.read_text(encoding="utf-8").strip(),
			"source_sha256": sha256_file(self.source),
			"base_commit": "deadbeef",
		}
		values.update(overrides)
		return HarborFinding(**values)

	def test_builds_current_harbor_task_structure(self):
		output = self.root / "task"
		result = build_harbor_task_package(output, self.finding(), self.source, self.rules)

		self.assertTrue((output / "instruction.md").is_file())
		self.assertTrue((output / "task.toml").is_file())
		self.assertTrue((output / "environment" / "Dockerfile").is_file())
		self.assertTrue((output / "tests" / "test.sh").is_file())
		self.assertTrue((output / "tests" / "verify.py").is_file())
		self.assertTrue(
			(output / "environment" / "workspace" / "hrms" / "hrms" / "overrides" / "employee_master.py").is_file()
		)

		toml_text = (output / "task.toml").read_text(encoding="utf-8")
		if tomllib:
			metadata = tomllib.loads(toml_text)
			self.assertEqual(metadata["schema_version"], HARBOR_SCHEMA_VERSION)
			self.assertEqual(metadata["task"]["name"], result.task_name)
			self.assertEqual(metadata["metadata"]["frappe_critic_finding"], "abc123")
		else:
			self.assertIn(f'schema_version = "{HARBOR_SCHEMA_VERSION}"', toml_text)
			self.assertIn(f'name = "{result.task_name}"', toml_text)
		self.assertEqual(len(result.task_sha256), 64)
		py_compile.compile(output / "tests" / "verify.py", doraise=True)
		verifier = (output / "tests" / "verify.py").read_text(encoding="utf-8")
		self.assertIn('RULE_BASENAME = RULE_ID.rsplit(".", 1)[-1]', verifier)

	def test_rejects_source_drift(self):
		finding = self.finding(source_sha256="0" * 64)
		with self.assertRaises(HarborTaskError):
			build_harbor_task_package(self.root / "task", finding, self.source, self.rules)

	def test_rejects_path_outside_app(self):
		finding = self.finding(file_path="../secrets.txt")
		with self.assertRaises(HarborTaskError):
			build_harbor_task_package(self.root / "task", finding, self.source, self.rules)


if __name__ == "__main__":
	unittest.main()
