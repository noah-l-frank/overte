# Paused iOS adapter source backup, 2026-10-29

This commit preserves unfinished work for recovery. Development and the existing
goal remain paused. Five of fourteen complete feature adapters are finished;
native compilation and device qualification have not been performed.

The normal repository paths contain all 98 public working-code changes as of
the pause. The preceding commits include the verified Audio held-owner entry
and Lifecycle original-child/quiet-collection integrations.

`private-source-drafts.tar.gz` preserves local source candidates, patches,
implementation plans, frozen source manifests and restart notes. `manifest.json`
records every archived path and SHA-256, the public working-code hashes and
the base commit. The archive was read back and each entry was verified against
the unchanged local source. It does not contain the 9.7 GB runtime directory.

Raw test originals, certificates and keys, account/device configuration, binary
artifacts and historical runtime/census logs remain local. Archive manifests
can reference those excluded inputs. Restoring source does not qualify those
inputs or make historical launchers independently runnable.

To resume, first read `.ios-host-tmp/root-pause-handoff-20261029-0831utc/RESTART.txt`
inside the archive. Inspect the recorded base, paths and hashes before restoring
files into a new isolated checkout; do not extract over existing work or execute
old launchers blindly. Paths in historical plans may require explicit rebinding.

The last focused protected-account TLS test passed. The subsequent normal
Avatar test failed at installed-bundle observation and remains unqualified.
Assets source/end proposals and Lifecycle Resource4 drafts remain unpublished
and untested. The source backup does not merge or activate those proposals.

No PR, protected-branch integration, device test or build is part of this backup.
