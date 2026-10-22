<!--
Copyright 2021 Vircadia contributors.
Copyright 2022-2026 Overte e.V.
SPDX-License-Identifier: Apache-2.0
-->

# Overte Server Packaging Scripts

These scripts create Linux server packages from an existing native build.
Run them from the repository's `pkg-scripts` directory: the default `OVERTE`
root is `realpath ..`, or an explicit `OVERTE` override. It is not `../..`.

The scripts expect the flat Release binary layout used by
[the current server workflow](../.github/workflows/linux_server_build.yml),
including `build/domain-server/domain-server` and
`build/assignment-client/assignment-client`. That layout is different from the
Ninja Multi-Config paths in the manual Linux build guide. Use the workflow's
matching Conan/CMake configuration before packaging. The
[container guide](../tools/ci-scripts/README.md) records its image selection.

Version/environment values below are examples, not the current release identity.
Packaging can install build prerequisites and write staging trees; building a
package does not publish a release or require the private device laboratory.

## Debian/Ubuntu packages
```
DEBVERSION="0.0.0-local" DEBEMAIL="your-email@somewhere.com" DEBFULLNAME="Your Full Name" ./make-deb-server
```

This script will retrieve the current git commit date and hash and append it to your specified version.
It will attempt construct a .deb file in the pkg-scripts folder

## RPM packages

Use the RPM build toolchain for the selected distribution; the current CI matrix
uses Fedora rather than the historical Amazon Linux 2 example. Then run the script.
```
RPMVERSION="0.0.0-local" ./make-rpm-server
```

This script will retrieve the current git commit date and hash and append it to your specified version.
It will attempt construct an .rpm file in the pkg-scripts folder

## Docker
```
./make-docker-server
```

This script will attempt to create a docker container.

## Results

### Binaries

The following directory structure is created for binaries:
```
/opt/overte - executables
/opt/overte/lib - private shared libraries required for executables
/opt/overte/resources - files required by domain-server administrative website
/opt/overte/plugins - files required by assignment-client, mainly for audio codecs
```

### Services

The following systemd services are installed in `/usr/lib/systemd/system`:
```
overte-agents@.service
overte-asset-server@.service
overte-audio-mixer@.service
overte-avatar-mixer@.service
overte-domain-server@.service
overte-entity-script-server@.service
overte-entity-server@.service
overte-message-mixer@.service
overte-server@.target - used to launch/shutdown the prior services
```
The services are "template" services designed
to permit multiple services to be installed and running on a single machine.

The script `/opt/overte/new-server serverName basePort` will do the necessary
setup for a new domain with the specified server name and port. Upon installation
the package will create and launch a domain named "default" at base port 40100.
The domain name here has nothing to do with the name people will use to find your
domain and has nothing to do with "place names", it is only used to locate the files
used to configure and run the domain on your server.

### Stored Files

The server stores its files in the following locations:
```
/var/lib/overte/serverName - "named" (template) domains
/etc/opt/overte - environment variables when launching named domains
```
