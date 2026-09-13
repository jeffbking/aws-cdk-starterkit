# 5900xt runner

The migrated jobs select `5900xt-aws-cdk-starterkit-ci`. This repository-scoped container is
separate from production and all other repositories. It uses GitHub's pinned
Ubuntu 24.04 runner image, with git, gh, jq, ACL utilities, and native build tools.
Workflows install their required Node versions with setup-node.

From this directory on 5900xt:

```bash
docker compose up -d --build
gh api -X POST repos/jeffbking/aws-cdk-starterkit/actions/runners/registration-token --jq .token |
  docker exec -i 5900xt-aws-cdk-starterkit-ci bash -ec '
    IFS= read -r registration_token
    ./config.sh --unattended --url https://github.com/jeffbking/aws-cdk-starterkit \
      --token "$registration_token" --name 5900xt-aws-cdk-starterkit-ci \
      --labels 5900xt-aws-cdk-starterkit-ci --work _work
    touch /home/runner/.runner-ready
  '
```

Compose enforces resource limits and drops capabilities; the image runs as a
non-root user. No host directories or Docker socket are mounted. Do not add
production credentials or host networking. Registration survives restarts;
recreation requires removing the old offline registration and registering again.
Never replace an active registration. Automatic runner updates remain enabled;
refresh the image digest and rebuild periodically for OS security updates.

This is a persistent container, not a disposable VM. Jobs share writable tool
cache and home directories within this repository. Recreate after suspected
compromise. Release/deploy triggers and credentials remain in their existing
workflows; migrating the runner does not require manually publishing a release.
