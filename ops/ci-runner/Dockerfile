FROM ghcr.io/actions/actions-runner@sha256:e5496277be5d09bc968b3d64911b74e219ac4a3f2edce956a3ecf9271bea1ef4
USER root
RUN apt-get update && apt-get install -y --no-install-recommends gh jq acl build-essential python3-venv ca-certificates && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/hostedtoolcache && chown runner:runner /opt/hostedtoolcache
ENV AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache
ENV RUNNER_TOOL_CACHE=/opt/hostedtoolcache
USER runner
WORKDIR /home/runner
ENTRYPOINT []
CMD ["./run.sh"]
