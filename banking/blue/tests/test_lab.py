import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import lab


class LabTests(unittest.TestCase):
    def test_export_normalizes_only_audit_fields_and_preserves_compose_options(self):
        args = SimpleNamespace(project_name='existing-bank', env_file=[Path('.env.local')],
                               compose_file=[Path('compose.existing.yaml')])
        compose = lab.compose_args(args)
        self.assertEqual(compose[:5], ['docker', 'compose', '-p', 'existing-bank', '--env-file'])
        self.assertEqual(compose[-3:], ['compose.yaml', '-f', str(Path('compose.existing.yaml').resolve())])
        row = {'path': '/api/staff/customers', 'method': 'GET', 'status': 200, 'actor_id': 7,
               'auth_role': 'STAFF', 'required_role': 'STAFF_OR_ADMIN', 'authz_decision': 'allowed'}
        with TemporaryDirectory() as temp:
            destination = Path(temp) / 'logs' / 'security.jsonl'
            with patch.object(lab, 'EXPORT', destination), patch.object(lab.subprocess, 'run') as run:
                run.return_value.stdout = json.dumps(row) + '\n'
                self.assertEqual(lab.export_audit(compose), destination)
            exported = json.loads(destination.read_text(encoding='utf-8'))
            self.assertEqual(exported['required_role'], 'STAFF_OR_ADMIN')
            self.assertNotIn('actor_id', exported)
            self.assertEqual(run.call_args.args[0][:len(compose)], compose)

    def test_fixture_path_does_not_contact_docker(self):
        with patch.object(lab, 'export_audit') as export, patch.object(lab.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(lab.main(['run', '--scenario', 'staff_access', '--baseline-only']), 0)
            export.assert_not_called()
            self.assertIn(str(lab.FIXTURE), run.call_args.args[0])
            self.assertIn(str(lab.LOGS), run.call_args.args[0])
