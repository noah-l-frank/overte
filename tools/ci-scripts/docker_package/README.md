<!--
Copyright 2022 Overte e.V.
SPDX-License-Identifier: MIT
-->

# Inherited server runtime-image recipes

This directory retains upstream Linux server Docker recipes. Its Debian 11 and
`0.1` examples describe that older packaging layout, not the current fork's
server CI matrix. Start with the [current CI container guide](../README.md) and
its linked workflow for the actual distribution, architecture, and immutable
build-image digest.

The retained recipe roles are:

- `Dockerfile_build`: the build environment for the older server-image layout.
- `Dockerfile_runtime_linuxbase`: a runtime dependency base image.
- `Dockerfile_runtime`: installs the built server into a runtime image.

These recipes are separate from the fork's current server CI. Registry names
embedded in inherited examples belong to their respective owners. If adapting
the recipes for your own images, use your own registry and release procedure.
The maintainer's private Proxmox device laboratory is unrelated to these recipes.
