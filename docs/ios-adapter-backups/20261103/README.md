# Paused iOS adapter source backup, 2026-11-03

This recovery commit preserves unfinished work and private source proposals.
Five of fourteen feature adapters are complete at source level. Native compilation
and device qualification have not been performed. Development remains paused.

Normal repository paths preserve all public working-code changes. The incremental
`private-source-drafts.tar.gz` contains private sources and selected source metadata
that are new or changed since `../20261029/manifest.json`. Keep both backups:
unchanged private sources remain in the 2026-10-29 archive. The manifest records
SHA-256 and size for every incremental entry and every public working-code path.
Every archive entry is read back and compared with the unchanged local original.

Raw test originals, runtime source copies, large census/source-map/result logs,
credentials, account/device configuration, SDKs and binary build artifacts remain
local. Historical frozen launchers may depend on these excluded local originals;
this source backup does not make those launchers independently runnable.

Read `.ios-host-tmp/remote-backup-preparation-20261103/RESTART.txt` and
`checkpoint.json` inside the incremental archive before resuming. Restore only
into a separate reviewed checkout. Never extract over existing work or blindly
execute old launchers. The latest Emote current-state five countermodels passed;
Assets historical snapshot cases02..07 passed and case01 failed. Its frozen
test-only measurement correction is unpublished and unexecuted. The Source4
Avatar readonly profile map exists, but that target has not started. New Audio,
Assets generation and Lifecycle proposals remain unintegrated and unqualified.

This commit is a source backup, not feature completion or integration acceptance.
No PR, protected integration, build, device test or laboratory run is included.
