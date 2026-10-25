"""Explicit tail4 preserves actual cached panel operands after normal logout.

All tail1/2/3 sources, fields and strong privacy/keys/UIKit checks remain in the
original reader. This profile changes only the explicitly retained UI lifetime.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_held_ui import disposition


class IOSAvatarHeldTail(IOSAvatarPostLogoutTail):
    VERSION=4
    READS=(4,)

    def panel_quiet(self,widgets):return disposition(widgets,binding=self.binding,run=self.run)

    @staticmethod
    def qualify_proof(proof,panel):
        need(proof['iosAvatarPostLogoutTailProofVersion']==3 and panel is not None)
        proof['iosAvatarPostLogoutTailProofVersion']=4;proof['panelDisposition']=panel;return proof


def tail_type(value):
    need(type(value) is dict and type(value.get('iosAvatarPostLogoutTailVersion')) is int)
    version=value['iosAvatarPostLogoutTailVersion'];need(version in (1,2,3,4))
    return IOSAvatarHeldTail if version==4 else IOSAvatarPostLogoutTail


def archive(value,**kwargs):return tail_type(value).archive(value,**kwargs)
