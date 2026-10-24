#!/usr/bin/env bash
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

(( $# > 0 )) || exit 64

# The central candidate boundary removes hosted-runner metadata and already
# permits unprivileged namespaces. Probe that capability before selecting the
# test boundary; a failed test is never retried through a different launcher.
if unshare --user --map-root-user --net /usr/bin/true 2>/dev/null; then
    exec unshare --user --map-root-user --net -- "$@"
fi

# Legacy hosted jobs may restrict unprivileged user namespaces. Create only a
# network namespace with their passwordless sudo, then drop to the runner UID
# and GID. Never request authentication or use sudo on an unrecognized host.
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted && "$(uname -s)" == Linux ]] || {
    echo "This network test launcher requires a GitHub-hosted Linux runner" >&2
    exit 64
}
exec sudo -n unshare --net --setgid "$(id -g)" --setuid "$(id -u)" -- "$@"
