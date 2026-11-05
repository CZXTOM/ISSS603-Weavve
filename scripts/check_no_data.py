"""Reject data artifacts and executed notebooks from the Git index.

pre-commit supplies filenames. With no filenames, check staged additions/changes.
Use --tracked to audit every tracked index blob. Files are always read from the
index, never from an unstaged working copy. This is a publication guard, not a
substitute for reviewing source text for confidential material.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

BLOCKED = {
    '.csv', '.tsv', '.xlsx', '.xls', '.zip', '.parquet', '.pkl', '.pickle',
    '.json', '.png', '.jpg', '.jpeg', '.pdf', '.docx', '.html',
}
ALLOWED_JSON = {
    '.vscode/settings.json', '.vscode/extensions.json',
    '.vscode/launch.json', '.vscode/tasks.json',
}
GENERATED_DIRS = {'outputs', 'output', 'weavve_outputs', 'cache', '.cache', 'artifacts'}
MAX_BYTES = 1_000_000


def git(*args: str, cwd: Path | None = None) -> bytes:
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'git {args[0]} failed (exit {result.returncode})')
    return result.stdout


def notebook_problems(blob: bytes) -> list[str]:
    try:
        nb = json.loads(blob.decode('utf-8-sig'))
    except (UnicodeError, ValueError):
        return ['notebook is not valid UTF-8 JSON']
    if not isinstance(nb, dict) or not isinstance(nb.get('cells'), list):
        return ['notebook has an invalid structure']
    bad = []
    if set(nb) - {'nbformat', 'nbformat_minor', 'metadata', 'cells'}:
        bad.append('notebook has unexpected top-level content')
    metadata = nb.get('metadata', {})
    if not isinstance(metadata, dict) or set(metadata) - {'kernelspec', 'language_info', 'orig_nbformat'}:
        bad.append('notebook has nonstandard metadata; remove widget state, execution metadata and private paths')
    else:
        allowed = {
            'kernelspec': {'display_name', 'language', 'name'},
            'language_info': {'name', 'version', 'mimetype', 'file_extension', 'pygments_lexer',
                              'codemirror_mode', 'nbconvert_exporter'},
        }
        for key, fields in allowed.items():
            value = metadata.get(key, {})
            if not isinstance(value, dict) or set(value) - fields:
                bad.append(f'notebook has nonstandard {key} metadata')
    for i, cell in enumerate(nb['cells'], 1):
        if not isinstance(cell, dict):
            bad.append(f'cell {i} has an invalid structure')
            continue
        if set(cell) - {'id', 'cell_type', 'metadata', 'source', 'outputs', 'execution_count', 'attachments'}:
            bad.append(f'cell {i} has unexpected content')
        if cell.get('outputs'):
            bad.append(f'cell {i} still has outputs; clear and stage the notebook again')
        if cell.get('execution_count') is not None:
            bad.append(f'cell {i} still has an execution count')
        if cell.get('attachments'):
            bad.append(f'cell {i} has embedded attachments')
        cm = cell.get('metadata', {})
        if not isinstance(cm, dict) or set(cm) - {'tags', 'collapsed', 'scrolled', 'jupyter'}:
            bad.append(f'cell {i} has nonstandard metadata; clear execution metadata and private paths')
        elif 'jupyter' in cm:
            jm = cm['jupyter']
            if not isinstance(jm, dict) or set(jm) - {'source_hidden', 'outputs_hidden'}:
                bad.append(f'cell {i} has nonstandard jupyter metadata')
        source = cell.get('source', '')
        if isinstance(source, list) and all(isinstance(v, str) for v in source):
            source = ''.join(source)
        if not isinstance(source, str):
            bad.append(f'cell {i} has invalid source text')
        elif 'data:image/' in source.lower() or 'data:application/' in source.lower():
            bad.append(f'cell {i} embeds an artifact as a data URI')
    return list(dict.fromkeys(bad))


def path_problem(name: str) -> str | None:
    path = PurePosixPath(name)
    parts = [part.lower() for part in path.parts]
    if any(part in GENERATED_DIRS or part.startswith('audit_') for part in parts[:-1]):
        return 'generated output directories do not go in this repo'
    if parts and parts[0] == 'data' and name != 'data/README.md':
        return 'only data/README.md may be tracked under data/'
    if path.suffix.lower() in BLOCKED and name not in ALLOWED_JSON:
        return 'data, report and image artifacts do not go in this repo'
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracked', action='store_true', help='check all tracked index blobs')
    parser.add_argument('filenames', nargs='*')
    args = parser.parse_args(argv)
    try:
        root = Path(git('rev-parse', '--show-toplevel').decode('utf-8').strip())
        entries: dict[str, list[tuple[str, str, str]]] = {}
        for entry in git('ls-files', '--stage', '-z', cwd=root).split(b'\0'):
            if not entry:
                continue
            info, rawname = entry.split(b'\t', 1)
            mode, oid, stage = info.decode('ascii').split()
            name = rawname.decode('utf-8', errors='surrogateescape')
            entries.setdefault(name, []).append((mode, oid, stage))
        if args.tracked:
            names = set(entries)
        elif args.filenames:
            names = set()
            for name in args.filenames:
                candidate = Path(name)
                if candidate.is_absolute():
                    try:
                        name = candidate.resolve().relative_to(root.resolve()).as_posix()
                    except ValueError:
                        raise RuntimeError('a supplied filename is outside the repository') from None
                name = name.replace('\\', '/')
                if '..' in PurePosixPath(name).parts:
                    raise RuntimeError('a supplied filename contains parent traversal')
                names.add(name.removeprefix('./'))
        else:
            names = {
                name.decode('utf-8', errors='surrogateescape')
                for name in git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z', cwd=root).split(b'\0')
                if name
            }
        bad = []
        for name in sorted(names):
            staged = entries.get(name)
            if not staged:
                continue
            label = repr(name)
            if len(staged) != 1 or staged[0][2] != '0':
                bad.append(f'{label}: unresolved index stages')
                continue
            mode, oid, _ = staged[0]
            if mode not in {'100644', '100755'}:
                bad.append(f'{label}: symlinks and submodules require explicit review and are not allowed')
                continue
            problem = path_problem(name)
            if problem:
                bad.append(f'{label}: {problem}')
                continue
            size = int(git('cat-file', '-s', oid, cwd=root))
            if size > MAX_BYTES:
                bad.append(f'{label}: over 1 MB, possibly a data artifact')
                continue
            blob = git('cat-file', 'blob', oid, cwd=root)
            if b'\0' in blob:
                bad.append(f'{label}: binary content in an unapproved file type')
            elif PurePosixPath(name).suffix.lower() == '.ipynb':
                bad.extend(f'{label}: {p}' for p in notebook_problems(blob))
        if bad:
            print('Commit blocked:\n  ' + '\n  '.join(bad))
            return 1
        print(f'Publication check passed for {len(names)} index paths.')
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Publication check failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
