#!/usr/bin/env python3
"""Run one clean GitHub runner; systemd supplies restart/backoff semantics."""
import json
import pathlib
import re
import signal
import subprocess
import sys
import uuid

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: run-ephemeral.py REPOSITORY [review|ci]")
repo = sys.argv[1]
if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo) or repo in {".", ".."}:
    raise SystemExit("Invalid repository name")
kind = sys.argv[2] if len(sys.argv) > 2 else 'review'
if kind not in ['review', 'ci']:
    raise SystemExit('Invalid runner kind')
label = f'5900xt-{repo}-agy-review' if kind == 'review' else (f'5900xt-{repo}-ci' if repo != 'clipsync' else '5900xt-clipsync-publish')
name = f'{label}-{uuid.uuid4().hex[:12]}'
container = label
image = 'local/agy-review-runner:ephemeral-2026-09-13' if kind == 'review' else 'local/light-ci-runner:ephemeral-2026-09-13'

def stop(signum, _frame):
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, stop)
network = json.loads(subprocess.check_output(['docker', 'network', 'inspect', 'ci-containers'], text=True, timeout=30))[0]
if (network['Driver'] != 'bridge' or network['EnableIPv6'] or
        [entry.get('Subnet') for entry in network['IPAM']['Config']] != ['10.90.0.0/24']):
    raise SystemExit('Dedicated CI network configuration does not match firewall policy')
subprocess.run(['docker', 'run', '--pull=never', '--rm', '--network', 'host', '--cap-drop', 'ALL',
                '--cap-add', 'NET_ADMIN', '--security-opt', 'no-new-privileges',
                'local/ci-runner-firewall:2026-09-13'], check=True, timeout=60)
subprocess.run(['docker', 'create', '--pull=never', '-i', '--name', container, '--hostname', name,
                '--network', 'ci-containers', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=1', '--init', '--user', '1001:1001', '--cpus', '2', '--memory', '2g' if kind == 'review' else '3g',
                '--memory-swap', '2g' if kind == 'review' else '3g',
                '--pids-limit', '256' if kind == 'review' else '512', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                image, 'bash', '-ec',
                'IFS= read -r registration_token; ./config.sh --unattended --ephemeral --disableupdate '
                f'--url https://github.com/jeffbking/{repo} --token "$registration_token" '
                f'--name {name} --labels {label} --work _work; '
                'unset registration_token; exec ./run.sh'], check=True, stdout=subprocess.DEVNULL, timeout=60)
try:
    pages = json.loads(subprocess.check_output(['gh', 'api', '--paginate', '--slurp',
                       f'repos/jeffbking/{repo}/actions/runners'], text=True, timeout=60))
    for page in pages:
        for old in page['runners']:
            if old['name'].startswith(label + '-') and old['status'] == 'offline' and not old['busy']:
                subprocess.run(['gh', 'api', '-X', 'DELETE',
                                f'repos/jeffbking/{repo}/actions/runners/{old["id"]}'], check=True, timeout=60)
    token = json.loads(subprocess.check_output(['gh', 'api', '-X', 'POST',
                       f'repos/jeffbking/{repo}/actions/runners/registration-token'], text=True, timeout=60))['token']
    result = subprocess.run(['docker', 'start', '-ai', container], input=token+'\n', text=True)
    result.check_returncode()
finally:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        subprocess.run(['docker', 'stop', '--timeout', '30', container], stdout=subprocess.DEVNULL, timeout=40)
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Container cleanup failed: {error}', file=sys.stderr)
    logs = pathlib.Path.home() / 'actions-runners/agy-review/logs' / name
    try:
        logs.mkdir(parents=True, exist_ok=True)
        subprocess.run(['docker', 'cp', f'{container}:/home/runner/_diag/.', str(logs)],
                       stdout=subprocess.DEVNULL, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Diagnostic archive failed: {error}', file=sys.stderr)
    try:
        subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, timeout=40)
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Container cleanup failed: {error}', file=sys.stderr)
    # Completed ephemeral runners deregister themselves. Remove an abandoned
    # registration only after its container has stopped, using its unique name.
    try:
        runners = json.loads(subprocess.check_output(['gh', 'api', '--paginate', '--slurp',
                             f'repos/jeffbking/{repo}/actions/runners'], text=True, timeout=60))
        for page in runners:
            for runner in page['runners']:
                if runner['name'] == name:
                    subprocess.run(['gh', 'api', '-X', 'DELETE',
                                    f'repos/jeffbking/{repo}/actions/runners/{runner["id"]}'], check=True, timeout=60)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f'Registration cleanup failed: {error}', file=sys.stderr)
