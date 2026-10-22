# Linux CI build containers

The current server packaging matrix is in
[`linux_server_build.yml`](../../.github/workflows/linux_server_build.yml).
It selects dated Debian/Fedora images for amd64 and aarch64 and pins each image
by digest. The old `0.1.7-$OS-$ARCH` example does not describe this matrix.

For an interactive reproduction, choose the matching `image` value from that
workflow. For example, the reviewed Debian 12 amd64 entry is:

```bash
build_image='docker.io/overte/overte-server-build:2026-02-09-debian-12-amd64@sha256:deb5e9eeef5ad5df3b44c7bfd456fe73aa5c513aa16456c3983966578d8b0531'
docker run --rm -v "$PWD:/overte" -w /overte -it "$build_image" bash
```

Run this from the repository root on a matching architecture. Follow the
workflow's environment, Conan, CMake, and packaging steps to reproduce its
server artifacts. Use [BUILD_LINUX.md](../../BUILD_LINUX.md) for a general local
build; the [selective native PR lane](../native-tests/README.md) uses a separate
prepared dependency image and is not this server packaging matrix.

The Dockerfiles under `deb_package`, `rpm_package`, and `linux-ci` describe
different build-image recipes. The [docker_package directory](docker_package/README.md)
retains inherited runtime-image recipes. The `overte` image namespace is an
upstream dependency source; a fork's own image publication would use its own
registry and a separate release procedure.

This is a hobby fork. Container reproduction and local host checks do not need
access to the maintainer's private Proxmox laboratory or self-hosted runners.
