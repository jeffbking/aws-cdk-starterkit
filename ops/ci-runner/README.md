# Ephemeral CI on 5900xt

Migrated jobs select `5900xt-aws-cdk-starterkit-ci`. Each job runs in a clean non-root container
registered with GitHub's `--ephemeral` option. It is deleted after one job;
workspace, home, tool cache and processes cannot carry over into the next job.
This separates PR-controlled state from subsequent release credentials.

## Install

On 5900xt, from this directory, using the operator account with Docker access
and an authenticated host gh CLI:

```bash
docker build -t local/light-ci-runner:ephemeral-2026-09-13 .
install -d -m 700 "$HOME/actions-runners/agy-review"
install -m 700 run-ephemeral.py "$HOME/actions-runners/agy-review/run-ephemeral.py"
install -Dm644 ci-runner.service "$HOME/.config/systemd/user/ci-runner-aws-cdk-starterkit.service"
systemctl --user daemon-reload
systemctl --user enable --now ci-runner-aws-cdk-starterkit.service
```

The launcher is shared with the fleet's ephemeral review runners; the unit
selects its CI profile. When replacing the old persistent runner, wait until
it is idle, stop/remove its container, and delete its old GitHub registration
before enabling this unit. Ensure the operator's user manager has linger
enabled for reboot startup.

## Implementation and verification

The launcher encodes all isolation flags: user 1001, 2 CPUs / 3 GiB, PID limit,
all capabilities dropped, no-new-privileges, no host mounts or Docker socket.
Only a short-lived registration token enters through stdin. The operator's gh
credential never enters the container. GitHub admits one job; Docker isolates
it; systemd handles restart/backoff. ARC's Kubernetes control plane is not needed
for one runner per repository. The runner name has a unique suffix, while its
scheduling label is stable.

The official runner base image is pinned by digest. Ubuntu packages receive
current updates at image build time, so builds are not bit-for-bit reproducible.
Automatic runner updates stay enabled. Refresh the image digest and rebuild for
OS security maintenance. Containers share the host kernel and outbound network;
they are not VMs or an egress firewall. Do not authenticate gh inside a container.

The Runner preflight workflow checks actual tool installation and runner
identity. Verify successive jobs use different runner names. Inspect
`systemctl --user status ci-runner-aws-cdk-starterkit` and
`journalctl --user -u ci-runner-aws-cdk-starterkit`. The launcher archives diagnostics under
`~/actions-runners/agy-review/logs/<runner-name>`; apply the host's log retention
policy there. Original release/deployment triggers are preserved; do not publish
a release just to test runner placement.

Upstream: <https://docs.github.com/en/actions/reference/runners/self-hosted-runners#ephemeral-runners-for-autoscaling>.
