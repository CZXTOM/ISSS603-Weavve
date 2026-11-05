"""Synthetic safety checks: no sponsor data is read or embedded here."""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


REPO = Path(__file__).resolve().parents[1]
GUARD = REPO / 'scripts' / 'check_no_data.py'
sys.path.insert(0, str(REPO / 'src'))
from weavve import clean
from weavve.sources import SourceCatalog


class DatasetTableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def dataset(self, rows):
        entry = clean._write_table(self.bundle / 'example.csv', rows)
        return clean.Dataset(self.bundle, {'tables': {'example': entry}})

    def test_types_and_leading_zero_ids_survive_roundtrip(self):
        records = [{'id': '0007', 'net': Decimal('-1.25'), 'flag': False,
                    'when': date(2001, 2, 3), 'stamp': datetime(2001, 2, 3, 4, 5),
                    'values': ['alpha', 'beta'], 'quantity': 2},
                   {'id': '0008', 'net': Decimal('0.10'), 'flag': True,
                    'when': None, 'stamp': None, 'values': [], 'quantity': None}]
        dataset = self.dataset(records)
        self.assertEqual(dataset.table('example'), records)
        self.assertIs(dataset.verify(), dataset)

    def test_empty_table_roundtrip(self):
        dataset = self.dataset([])
        self.assertEqual(dataset.table('example'), [])
        dataset.verify()

    def test_content_tampering_and_missing_table_are_detected(self):
        dataset = self.dataset([{'id': 'synthetic'}])
        (self.bundle / 'example.csv').write_text('id\naltered\n', encoding='utf-8')
        with self.assertRaises(ValueError): dataset.verify()
        with self.assertRaises(ValueError): dataset.table('example')
        (self.bundle / 'example.csv').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)): dataset.verify()

    def test_row_count_and_schema_metadata_are_verified(self):
        dataset = self.dataset([{'id': 'synthetic'}])
        dataset.manifest['tables']['example']['rows'] = 2
        with self.assertRaises(ValueError): dataset.verify()
        dataset.manifest['tables']['example']['rows'] = 1
        dataset.manifest['tables']['example']['columns'] = {'different': 'str'}
        with self.assertRaises(ValueError): dataset.verify()

    def test_table_reader_rejects_escape_without_prior_verify(self):
        entry = clean._write_table(self.root / 'outside.csv', [{'id': 'synthetic'}])
        entry['file'] = '../outside.csv'
        dataset = clean.Dataset(self.bundle, {'tables': {'example': entry}})
        with self.assertRaises(ValueError): dataset.verify()
        with self.assertRaises(ValueError): dataset.table('example')

    def test_unknown_table_and_column_type_fail(self):
        dataset = self.dataset([{'id': 'synthetic'}])
        with self.assertRaises(KeyError): dataset.table('missing')
        dataset.manifest['tables']['example']['columns']['id'] = 'unknown'
        with self.assertRaises(ValueError): dataset.table('example')

    def test_duplicate_csv_headers_are_rejected(self):
        dataset = self.dataset([{'id': 'synthetic'}])
        path = self.bundle / 'example.csv'
        path.write_text('id,id\nalpha,beta\n', encoding='utf-8')
        dataset.manifest['tables']['example']['sha256'] = sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError): dataset.table('example')


class SourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_extracted_and_archived_copies_have_one_logical_identity(self):
        extracted, archived = self.root / 'extracted', self.root / 'archived'
        extracted.mkdir(); archived.mkdir()
        content = b'synthetic source bytes'
        (extracted / 'C.synthetic.xlsx').write_bytes(content)
        with ZipFile(archived / 'sources.zip', 'w') as z:
            z.writestr('nested/C.synthetic.xlsx', content)
            z.writestr('__MACOSX/._C.synthetic.xlsx', b'ignored')
            z.writestr('~$C.synthetic.xlsx', b'ignored')
        first, second = SourceCatalog(extracted), SourceCatalog(archived)
        self.assertEqual(first.inventory(), second.inventory())
        with ZipFile(extracted / 'duplicate.zip', 'w') as z:
            z.writestr('nested/C.synthetic.xlsx', content)
        self.assertEqual(first.inventory(), SourceCatalog(extracted).inventory())

    def test_conflicting_copies_and_multiple_versions_fail(self):
        (self.root / 'C.synthetic.xlsx').write_bytes(b'first synthetic version')
        with ZipFile(self.root / 'sources.zip', 'w') as z:
            z.writestr('C.synthetic.xlsx', b'different synthetic version')
        with self.assertRaises(ValueError): SourceCatalog(self.root)
        (self.root / 'sources.zip').unlink()
        (self.root / 'C.other.xlsx').write_bytes(b'first synthetic version')
        with self.assertRaises(ValueError): SourceCatalog(self.root)

    def test_missing_required_sources_fail(self):
        with self.assertRaises(FileNotFoundError): SourceCatalog(self.root).require(['C'])


class BundleBuildTests(unittest.TestCase):
    """Exercise build/load orchestration with synthetic cleaners and source hashes."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw, self.output, self.repo = self.root / 'raw', self.root / 'private', self.root / 'code'
        self.raw.mkdir(); self.repo.mkdir()
        (self.raw / 'source.txt').write_text('synthetic input', encoding='utf-8')

        class FakeCatalog:
            def __init__(self, path): self.path = Path(path)
            def require(self, groups): pass
            def rows(self, *args): return []
            def inventory(self):
                payload = (self.path / 'source.txt').read_bytes()
                return [{'source': 'synthetic', 'file': 'synthetic/source.txt',
                         'bytes': len(payload), 'sha256': sha256(payload).hexdigest()}]

        transaction = {'tables': {'orders': [{'order_id': '0001', 'order_date': date(2001, 2, 3),
                                             'net': Decimal('1.25')}]}, 'warnings': [], 'checks': {}}
        other = {'tables': {}, 'warnings': [], 'checks': {}}
        self.patches = [patch.object(clean, 'ROOT', self.repo), patch.object(clean, 'SourceCatalog', FakeCatalog),
                        patch.object(clean, '_code_inventory', return_value=[{'file': 'synthetic.py', 'sha256': 'synthetic-code'}]),
                        patch('weavve.clean_transactions.clean_transactions', return_value=transaction),
                        patch('weavve.clean_support.build_support_tables', return_value=other),
                        patch('weavve.clean_search.build_search_tables', return_value=other)]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_repeated_build_and_zip_are_deterministic(self):
        first = clean.build_dataset(self.raw, self.output, make_zip=True)
        zip_path = next((self.output / 'clean').glob('*.zip'))
        zip_bytes = zip_path.read_bytes()
        manifest_bytes = (first.path / 'manifest.json').read_bytes()
        second = clean.build_dataset(self.raw, self.output, make_zip=True)
        self.assertEqual(first.path, second.path)
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(zip_bytes, zip_path.read_bytes())
        self.assertEqual(manifest_bytes, (second.path / 'manifest.json').read_bytes())
        loaded = clean.load_dataset(data_dir=self.raw, out_dir=self.output)
        self.assertEqual(loaded.table('orders'), first.table('orders'))

    def test_changed_inputs_are_stale_and_rebuild_has_new_identity(self):
        first = clean.build_dataset(self.raw, self.output)
        (self.raw / 'source.txt').write_text('changed synthetic input', encoding='utf-8')
        with self.assertRaises(ValueError): clean.load_dataset(first.path, data_dir=self.raw)
        second = clean.build_dataset(self.raw, self.output)
        self.assertNotEqual(first.manifest['dataset_id'], second.manifest['dataset_id'])
        self.assertTrue(first.path.is_dir())

    def test_changed_code_or_rules_make_bundle_stale(self):
        first = clean.build_dataset(self.raw, self.output)
        with patch.object(clean, '_code_inventory', return_value=[{'file': 'synthetic.py', 'sha256': 'changed-code'}]):
            with self.assertRaises(ValueError): clean.load_dataset(first.path, data_dir=self.raw)
        with patch.dict(clean.RULES, {'version': 'synthetic-new-rule'}):
            with self.assertRaises(ValueError): clean.load_dataset(first.path, data_dir=self.raw)

    def test_modified_existing_bundle_is_not_overwritten(self):
        dataset = clean.build_dataset(self.raw, self.output)
        path = dataset.path / 'orders.csv'
        original = path.read_bytes()
        path.write_bytes(original + b'changed')
        with self.assertRaises(ValueError): clean.build_dataset(self.raw, self.output)
        self.assertEqual(path.read_bytes(), original + b'changed')

    def test_outputs_cannot_overlap_inputs_or_code(self):
        for destination in (self.raw, self.raw / 'nested', self.root, self.repo, self.repo / 'nested'):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError): clean.build_dataset(self.raw, destination)
        self.assertEqual((self.raw / 'source.txt').read_text(encoding='utf-8'), 'synthetic input')

    def test_packaged_zip_does_not_include_unregistered_files(self):
        dataset = clean.build_dataset(self.raw, self.output)
        (dataset.path / 'private-note.txt').write_text('synthetic private note', encoding='utf-8')
        try:
            clean.build_dataset(self.raw, self.output, make_zip=True)
        except ValueError:
            return  # Refusing an unexpected file is also an acceptable closed failure.
        with ZipFile(next((self.output / 'clean').glob('*.zip'))) as archive:
            self.assertNotIn('private-note.txt', archive.namelist())

    def test_redirected_clean_directory_cannot_write_into_code(self):
        self.output.mkdir()
        try:
            os.symlink(self.repo, self.output / 'clean', target_is_directory=True)
        except OSError as exc:
            self.skipTest(f'This host cannot create directory symlinks: {exc}')
        with self.assertRaises(ValueError): clean.build_dataset(self.raw, self.output)
        self.assertEqual(list(self.repo.iterdir()), [])


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git('init', '-q')

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, capture_output=True, check=True)

    def stage(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        self.git('add', '--', name)
        return target

    def guard(self, *args):
        return subprocess.run([sys.executable, str(GUARD), *args], cwd=self.root, capture_output=True, text=True)

    @staticmethod
    def notebook(**cell_updates):
        cell = {'cell_type': 'code', 'metadata': {}, 'source': ['x = 1\n'], 'outputs': [], 'execution_count': None}
        cell.update(cell_updates)
        return json.dumps({'nbformat': 4, 'nbformat_minor': 5, 'metadata': {}, 'cells': [cell]})

    def test_staged_outputs_are_not_hidden_by_clean_working_copy(self):
        target = self.stage('example.ipynb', self.notebook(outputs=[{'output_type': 'stream', 'name': 'stdout', 'text': 'synthetic'}]))
        target.write_text(self.notebook(), encoding='utf-8')
        result = self.guard('example.ipynb')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('outputs', result.stdout)

    def test_clean_index_is_not_rejected_for_unstaged_execution(self):
        target = self.stage('example.ipynb', self.notebook())
        target.write_text(self.notebook(execution_count=1), encoding='utf-8')
        self.assertEqual(self.guard('--tracked').returncode, 0)

    def test_execution_counts_attachments_and_metadata_are_rejected(self):
        variants = [
            self.notebook(execution_count=1),
            self.notebook(attachments={'image': {'image/png': 'synthetic'}}),
            self.notebook(metadata={'execution': {'iopub.status.busy': 'synthetic'}}),
            self.notebook(source=['![image](data:image/png;base64,synthetic)']),
        ]
        for content in variants:
            with self.subTest(content=content):
                self.stage('example.ipynb', content)
                self.assertEqual(self.guard('example.ipynb').returncode, 1)

    def test_widget_state_and_malformed_notebook_are_rejected(self):
        nb = json.loads(self.notebook())
        nb['metadata']['widgets'] = {'state': 'synthetic'}
        for content in (json.dumps(nb), '{}', '{broken'):
            with self.subTest(content=content):
                self.stage('example.ipynb', content)
                self.assertEqual(self.guard('example.ipynb').returncode, 1)

    def test_data_report_extensions_and_generated_directories_are_blocked(self):
        for name in ('sample.tsv', 'sample.pickle', 'report.PDF', 'report.docx', 'report.html',
                     'data/hidden.txt', 'outputs/hidden.py', 'audit_private/hidden.md'):
            with self.subTest(name=name):
                self.stage(name, 'synthetic')
                self.assertEqual(self.guard(name).returncode, 1)

    def test_only_explicit_editor_json_paths_are_allowed(self):
        self.stage('.vscode/settings.json', '{}')
        self.stage('.vscode/private.json', '{}')
        self.stage('.vscode/nested/settings.json', '{}')
        self.assertEqual(self.guard('.vscode/settings.json').returncode, 0)
        self.assertEqual(self.guard('.vscode/private.json').returncode, 1)
        self.assertEqual(self.guard('.vscode/nested/settings.json').returncode, 1)

    def test_tracked_scan_finds_a_file_missing_from_explicit_list(self):
        self.stage('safe.py', 'x = 1\n')
        self.stage('hidden.csv', 'synthetic\n')
        self.assertEqual(self.guard('safe.py').returncode, 0)
        self.assertEqual(self.guard('--tracked').returncode, 1)

    def test_deleted_data_file_is_not_published(self):
        self.stage('gone.csv', 'synthetic\n')
        self.git('rm', '-q', '-f', '--', 'gone.csv')
        self.assertEqual(self.guard('gone.csv').returncode, 0)

    def test_safe_code_and_data_readme_pass_default_staged_scan(self):
        self.stage('safe.py', 'x = 1\n')
        self.stage('data/README.md', 'Place authorized source files here locally.\n')
        self.stage('example.ipynb', self.notebook())
        self.assertEqual(self.guard().returncode, 0)

    def test_oversized_allowed_extension_is_rejected(self):
        self.stage('oversized.txt', 'x' * 1_000_001)
        self.assertEqual(self.guard('--tracked').returncode, 1)


if __name__ == '__main__':
    unittest.main()
