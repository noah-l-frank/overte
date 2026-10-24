"""Freeze rooted role ownership without declaring native holder drainage.

The existing host-copy transaction retains exact metadata and fully qualifies
its original graph. This distinct schema cannot retire metadata until separate
typed process/SDK end integration supplies authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_observer import EmoteObservationPending


class IOSEmoteRootedFinalArchive(IOSEmoteFinalArchive):
    VERSION=1
    READS=(1,)
    COPY_VERSION=1
    ARCHIVE_KEY='iosEmoteRootedFinalArchiveVersion'
    COPY_KEY='iosEmoteRootedFinalCopyVersion'
    COPY_PREFIX='emote-rooted-final-'
    PHASES=('freezing','validated')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        need(self.store.path not in {store.path for store in self.paths})
        need(all(store.path!=self.record_store(index).path
            for store in self.paths for index in range(1,len(self.paths)+1)))

    def retire(self):
        raise EmoteObservationPending('Rooted metadata retains responsibility until typed process and SDK end')
