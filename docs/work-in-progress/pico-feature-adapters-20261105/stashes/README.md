# Paused Pico stash snapshots

These source patches preserve three older local Pico stashes before local cleanup. They are archival data and are not applied to the live adapter implementation. The manifest records the original stash, base, index, and untracked commits. Apply staged and unstaged patches in that order against the recorded base; the untracked patch adds the original untracked source files. Patch applicability was checked using temporary Git indexes without builds or device tests.
