"""PowerShell entry point for the Docker bank and the FinLab Blue results."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile

BANKING = Path(__file__).resolve().parent
BLUE = BANKING / 'blue'
LOGS = BANKING / 'logs'
EXPORT = LOGS / 'security.jsonl'
FIXTURE = BLUE / 'examples' / 'staff_access.jsonl'
AUDIT_QUERY = """
SELECT json_build_object(
    'timestamp', created_at, 'method', http_method, 'path', request_path, 'status', http_status,
    'auth_role', actor_type, 'required_role', details ->> 'required_role',
    'authz_decision', details ->> 'authz_decision')
FROM (
    SELECT id, created_at, http_method, request_path, http_status, actor_type, details
    FROM audit_logs
    WHERE action = 'API_REQUEST' AND http_status IS NOT NULL
    ORDER BY id DESC LIMIT 100
) AS recent
ORDER BY id
"""


def compose_args(args):
    command = ['docker', 'compose']
    if args.project_name:
        command += ['-p', args.project_name]
    for env_file in args.env_file:
        command += ['--env-file', str(env_file.resolve())]
    command += ['-f', 'compose.yaml']
    for config in args.compose_file:
        command += ['-f', str(config.resolve())]
    return command


def export_audit(compose):
    sys.path.insert(0, str(BLUE))
    from run_blue import clean_event

    postgres = ('PGPASSWORD="$POSTGRES_PASSWORD" exec psql -XqAt -v ON_ERROR_STOP=1 '
                '-h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"')
    args = ['exec', '-T', 'database', 'sh', '-c', postgres, 'finlab-audit', AUDIT_QUERY]
    result = subprocess.run(compose + args, cwd=BANKING, check=True,
                            stdout=subprocess.PIPE, encoding='utf-8')
    events = []
    for index, line in enumerate(result.stdout.splitlines(), 1):
        if not line:
            continue
        event = clean_event(json.loads(line), index)
        if event is not None:
            event.pop('event_id')
            events.append(event)
    if not events:
        raise ValueError('수집한 은행 로그가 없습니다. 로그인 또는 계좌 조회 후 다시 실행하세요.')

    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    output = NamedTemporaryFile(mode='w', encoding='utf-8', dir=EXPORT.parent, delete=False)
    temp = Path(output.name)
    try:
        with output:
            for event in events:
                output.write(json.dumps(event, ensure_ascii=False) + '\n')
        temp.replace(EXPORT)
    finally:
        temp.unlink(missing_ok=True)
    print(f'감사 로그 {len(events)}건: {EXPORT}', flush=True)
    return EXPORT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-p', '--project-name')
    parser.add_argument('--env-file', type=Path, action='append', default=[])
    parser.add_argument('-f', '--compose-file', action='append', default=[], type=Path,
                        help='compose.yaml 뒤에 적용할 기존 Compose 파일')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('start', help='기존 Docker Compose 구성 시작')
    sub.add_parser('stop', help='은행 컨테이너 중지')
    sub.add_parser('logs', help='Docker 은행 감사 로그 JSONL로 저장')
    run = sub.add_parser('run', help='권한 판정 기록 분석 및 결과 저장')
    source = run.add_mutually_exclusive_group()
    source.add_argument('--scenario', choices=('staff_access',), help='직원 권한 검사의 합성 로그 재생')
    source.add_argument('--log', type=Path, help='보유한 감사 로그 JSONL 경로')
    run.add_argument('--baseline-only', action='store_true')
    run.add_argument('--limit', type=int, default=24)
    run.add_argument('--batch-size', type=int, default=8)
    args = parser.parse_args(argv)
    compose = compose_args(args)
    try:
        if args.operation == 'start':
            return subprocess.run(compose + ['up', '-d', '--build', '--wait'], cwd=BANKING).returncode
        if args.operation == 'stop':
            return subprocess.run(compose + ['stop'], cwd=BANKING).returncode
        if args.operation == 'logs':
            export_audit(compose)
            return 0

        if args.scenario:
            path, data_source = FIXTURE, 'fixture'
            print('시나리오: 직원 권한 확인 · 합성 로그', flush=True)
        elif args.log:
            path, data_source = args.log.resolve(), 'file'
        else:
            path, data_source = export_audit(compose), 'docker'

        command = [sys.executable, str(BLUE / 'run_blue.py'), '--log', str(path),
                   '--source', data_source, '--html', '--report-dir', str(LOGS), '--limit', str(args.limit),
                   '--batch-size', str(args.batch_size)]
        if args.baseline_only:
            command.append('--baseline-only')
        return subprocess.run(command, cwd=BANKING).returncode
    except subprocess.CalledProcessError:
        print('실행 실패: Docker 상태와 은행 감사 로그를 확인하세요.', file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f'실행 실패: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
