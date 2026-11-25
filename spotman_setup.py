"""Post-create setup steps for SpotMan profiles, run over SSH from the local machine.

A profile may carry a `setup_steps` list. `spotman create` runs it once the instance has SSH
(skip with --no-setup), and `spotman setup INSTANCE` runs it again on an existing instance.
Steps run in order; the first failure stops the sequence. Every step may have:

    name:    label printed before the step
    skip_if: remote shell command; when it exits 0 the step is skipped (makes reruns idempotent)

Step kinds (exactly one per step):

    wait_for: remote shell command, retried until it exits 0
              (timeout: seconds, default 900; interval: seconds, default 10)
    copy:     {src: local file or directory, dest: remote directory}
              src may use ~ and is otherwise relative to the profiles directory.
              A directory's contents land in dest (dest/<files>); __pycache__ and .git are left out.
    run:      remote bash script (fed on stdin, runs under `set -e`; timeout default 1800)
    reboot:   true; reboots, waits until SSH answers again (timeout default 900)

Example:

    setup_steps:
      - name: first boot finished
        wait_for: test -e /var/lib/cloud/instance/boot-finished
      - name: isolate cores
        skip_if: grep -q isolcpus= /proc/cmdline
        run: |
          sudo sed -i 's/^GRUB_CMDLINE_LINUX="/&isolcpus=8-95 /' /etc/default/grub
          sudo update-grub
      - name: reboot into the new kernel command line
        skip_if: grep -q isolcpus= /proc/cmdline
        reboot: true
"""
import os
import subprocess
import time
from typing import Dict, List

SSH_OPTS = ['-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=30']


def _ssh(host: str, command: str, timeout: int = 60, input_text: str = None, capture: bool = True):
    return subprocess.run(['ssh', *SSH_OPTS, host, command], input=input_text, text=True,
                          capture_output=capture, timeout=timeout)


def _ssh_ok(host: str, command: str = 'true', timeout: int = 30) -> bool:
    try:
        return _ssh(host, command, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def wait_for_ssh(host: str, timeout: int = 900, interval: int = 10) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ssh_ok(host):
            return True
        time.sleep(interval)
    return False


def _step_wait_for(host: str, step: Dict) -> bool:
    cmd = step['wait_for']
    timeout, interval = int(step.get('timeout', 900)), int(step.get('interval', 10))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ssh_ok(host, cmd):
            return True
        time.sleep(interval)
    print(f"  timed out after {timeout}s waiting for: {cmd}")
    return False


def _step_copy(host: str, step: Dict, base_dir: str) -> bool:
    spec = step['copy']
    src = os.path.expanduser(spec['src'])
    if not os.path.isabs(src):
        src = os.path.normpath(os.path.join(base_dir, src))
    dest = spec['dest']
    if not os.path.exists(src):
        print(f"  local source not found: {src}")
        return False
    if os.path.isdir(src):
        tar = ['tar', 'czf', '-', '--exclude=__pycache__', '--exclude=.git', '-C', src, '.']
    else:
        tar = ['tar', 'czf', '-', '-C', os.path.dirname(src), os.path.basename(src)]
    remote = f'mkdir -p {dest} && tar xzf - -C {dest}'
    p1 = subprocess.Popen(tar, stdout=subprocess.PIPE)
    p2 = subprocess.run(['ssh', *SSH_OPTS, host, remote], stdin=p1.stdout, timeout=int(step.get('timeout', 600)))
    p1.stdout.close()
    p1.wait()
    if p1.returncode != 0 or p2.returncode != 0:
        print(f"  copy failed (tar {p1.returncode}, ssh {p2.returncode})")
        return False
    print(f"  copied {src} -> {host}:{dest}")
    return True


def _step_run(host: str, step: Dict) -> bool:
    script = 'set -e\n' + step['run']
    try:
        r = _ssh(host, 'bash -s', timeout=int(step.get('timeout', 1800)), input_text=script, capture=False)
    except subprocess.TimeoutExpired:
        print("  script timed out")
        return False
    if r.returncode != 0:
        print(f"  script exited {r.returncode}")
        return False
    return True


def _step_reboot(host: str, step: Dict) -> bool:
    try:
        _ssh(host, 'sudo systemctl reboot', timeout=30)
    except subprocess.TimeoutExpired:
        pass  # the connection often drops before ssh returns
    # Wait until the old session is gone, then until SSH answers again.
    gone_deadline = time.time() + 180
    while time.time() < gone_deadline and _ssh_ok(host, timeout=10):
        time.sleep(5)
    t0 = time.time()
    if not wait_for_ssh(host, timeout=int(step.get('timeout', 900))):
        print("  instance did not come back after reboot")
        return False
    print(f"  back after {time.time() - t0:.0f}s")
    return True


KINDS = ('wait_for', 'copy', 'run', 'reboot')


def run_setup_steps(host: str, steps: List[Dict], base_dir: str) -> bool:
    """Run setup steps against an SSH host alias. Returns True when every step passed or was skipped."""
    if not steps:
        return True
    print(f"Running {len(steps)} setup step(s) on {host}")
    if not wait_for_ssh(host, timeout=900):
        print("SSH never became available; setup not run")
        return False
    for i, step in enumerate(steps, 1):
        kinds = [k for k in KINDS if k in step]
        if len(kinds) != 1:
            print(f"[{i}/{len(steps)}] invalid step (needs exactly one of {', '.join(KINDS)}): {step}")
            return False
        kind = kinds[0]
        label = step.get('name', kind)
        if step.get('skip_if') and _ssh_ok(host, step['skip_if'], timeout=60):
            print(f"[{i}/{len(steps)}] {label}: skipped")
            continue
        print(f"[{i}/{len(steps)}] {label}")
        if kind == 'wait_for':
            ok = _step_wait_for(host, step)
        elif kind == 'copy':
            ok = _step_copy(host, step, base_dir)
        elif kind == 'run':
            ok = _step_run(host, step)
        else:
            ok = _step_reboot(host, step)
        if not ok:
            print(f"Setup stopped at step {i} ({label}). Fix it and rerun: ./spotman setup <instance>")
            return False
    print("Setup complete.")
    return True
