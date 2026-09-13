# Disposable CI runner on 5900xt

Jobs select `5900xt-aws-cdk-starterkit-ci`. Every job gets a fresh non-root container; GitHub's
`--ephemeral` registration accepts one job and systemd starts the next container.
Home, workspace and writable tool cache are destroyed after each job. The
launcher enforces user 1001, 2 CPUs, 3 GiB RAM, no capabilities and
no-new-privileges, with no host filesystem mounts or Docker socket.

## CI network policy

Before enabling a runner, build and install the shared network policy from this directory:

```bash
docker network inspect ci-containers >/dev/null 2>&1 || docker network create --subnet 10.90.0.0/24 -o com.docker.network.bridge.enable_icc=false ci-containers
docker network inspect ci-vms >/dev/null 2>&1 || docker network create --subnet 10.89.0.0/24 ci-vms
docker build -t local/ci-runner-firewall:2026-09-13 network
install -Dm644 network/ci-runner-firewall.service "$HOME/.config/systemd/user/ci-runner-firewall.service"
systemctl --user daemon-reload
systemctl --user enable --now ci-runner-firewall.service
```

Both networks are IPv4-only. The host-side helper has NET_ADMIN solely to install
idempotent rules in Docker's DOCKER-USER and host INPUT chains. Only traffic from
10.89.0.0/24 and 10.90.0.0/24 enters these rules. New connections to host services,
private/LAN/tailnet/link-local addresses and other CI guests are rejected; replies
to operator-initiated SSH remain allowed. Public internet access is permitted.
The launcher reapplies the rules before each new job environment, including after
Docker restarts. Job containers never get NET_ADMIN or the helper's host network.
Do not attach other workloads to these reserved networks or enable IPv6 without
an equivalent IPv6 policy. Existing host firewall rules are never flushed.

Verified on 5900xt: GitHub HTTPS succeeds; host gateway SSH and LAN HTTP probes
increment the dedicated REJECT counters. This is network isolation, not an
internet destination allowlist. Docker containers still share the host kernel.

## Install

Use the host operator account with Docker access and authenticated `gh`. From
this directory, after installing the network policy:

```bash
docker build -t local/light-ci-runner:ephemeral-2026-09-13 .
install -d -m 700 "$HOME/actions-runners/agy-review"
install -m 700 run-ephemeral.py "$HOME/actions-runners/agy-review/run-ephemeral.py"
install -Dm644 ci-runner.service "$HOME/.config/systemd/user/ci-runner-aws-cdk-starterkit.service"
install -Dm644 logs.conf "$HOME/.config/user-tmpfiles.d/ci-runner-logs.conf"
systemctl --user daemon-reload
systemctl --user enable --now ci-runner-aws-cdk-starterkit.service
systemctl --user enable --now systemd-tmpfiles-clean.timer
```

The shared launcher accepts `REPO review` or `REPO ci`; copies in these operator
bundles are identical. Replace the former persistent container and registration
only while idle. Logs are archived to `~/actions-runners/agy-review/logs/<name>`.
The `gh` binary supports job GitHub lookups; it holds no operator credential.
The image supplies Python venv support for setup-python and a writable tool cache.
ARC was considered; a Kubernetes control plane is unnecessary for one runner per
repository. GitHub, Docker and systemd provide admission, isolation and restart.

## Maintenance and verification

Stop or replace a runner only after its GitHub registration reports `busy: false`.
A fresh unique runner name is expected after each job, with a short offline gap.
The Runner preflight checks tools and identity without checkout or application
secrets. The host `gh` credential is never copied into a job environment. Only a
short-lived registration token crosses stdin; `config.sh` briefly receives that
token in its guest/container argv and writes credentials inside the disposable
environment. Never run `gh auth login` inside a job environment.

`--disableupdate` prevents updates from being discarded and downloaded again on
every job. Refresh the official runner image/archive at least every 30 days, and
sooner for mandatory/security updates, then rebuild before GitHub stops accepting
jobs. OS packages follow Ubuntu security updates at build time; these builds are
not bit-for-bit reproducible. Record `docker image inspect <image> --format
'{{.Id}}'` with maintenance records. Rebuild explicitly rather than reusing an old
image unintentionally. Do not modify a golden image while runners use it.

Ensure `loginctl show-user "$USER" -p Linger` reports yes for reboot startup.
`systemctl --user status <unit>` and `journalctl --user -u <unit> -n 50` expose
registration failures; `gh api repos/jeffbking/aws-cdk-starterkit/actions/runners --paginate`
checks online registrations. Restarts use systemd restart delay, not a marker-file poll.
Archive directories are private to the operator; apply the supplied tmpfiles
policy to retain seven days of diagnostics. This host has finite capacity: watch
available RAM and memory pressure when changing concurrency or per-job limits.

GitHub contract: <https://docs.github.com/en/actions/reference/runners/self-hosted-runners#ephemeral-runners-for-autoscaling>.
