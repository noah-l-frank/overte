<!--
Copyright 2023 Overte e.V.
SPDX-License-Identifier: Apache-2.0
-->

# Inherited standalone Node build recipes

The root Overte build consumes `libnode` through
[`conanfile.py`](../../conanfile.py) and its reviewed Conan dependency graph.
At the October 20, 2026 source review, that consumer pins `libnode/22.23.2`.
This native library is separate from the Node.js executable used for npm,
JavaScript tests, and API documentation; use [BUILD.md](../../BUILD.md) for
that host-tool baseline.

The Dockerfiles in this directory and the older Node 18.14.2 manual were
inherited from an earlier dependency-production workflow. They are not the
current dependency preparation procedure and must not be substituted for a
locked Conan package. The original build and upload notes remain in the
[historical manual](https://github.com/noah-l-frank/overte/blob/b5f48d2a842a5cc1655ceb2f69a46bf3c4030429/tools/node-builder/README.md).

For current native dependency preparation and its validation/publication
boundary, follow the [native lane guide](../native-tests/README.md) and
[dependency release policy](../../docs/DEPENDENCY_RELEASES.md). A source build
of Node alone does not qualify its ABI, compiler settings, or integration with
Overte. These recipes do not require access to the maintainer's private lab.
