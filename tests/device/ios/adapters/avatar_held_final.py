"""Final2 joins fresh worldless Web originals and explicitly retained UI.

Final1 remains its strict historical three-component reader. No actual source,
clock, raw artifact, completed proof or public timestamp is relabeled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.avatar_final import IOSAvatarFinal,Frozen,ROLES
from ios.adapters.avatar_held_tail import IOSAvatarHeldTail
from ios.adapters.avatar_marker_web_receipts import IOSAvatarMarkerWebReceipts
from ios.adapters.emote_native_prefix import follow
from ios.adapters import web_closures


class IOSAvatarHeldFinal(IOSAvatarFinal):
    VERSION=2
    COMPONENTS=('post','tail','pointers','web')
    COMPONENT_VERSIONS=dict(IOSAvatarFinal.COMPONENT_VERSIONS,web=None)
    TAIL_READS=(4,)
    Tail=IOSAvatarHeldTail

    def input(self,subject):
        value=self.inputs[subject];exact(value,{'root','paths','childRunId','fixtureUrl','markerFixtureUrl','ticket','baseline','logoutBefore'})
        exact(value['paths'],set(self.COMPONENTS))
        # This is closed private input metadata validation, not a source DTO.
        # The actual original inputs remain intact in every Final2 envelope.
        legacy={key:deepcopy(item) for key,item in value.items() if key!='markerFixtureUrl'}
        legacy['paths']={key:legacy['paths'][key] for key in IOSAvatarFinal.COMPONENTS}
        IOSAvatarFinal.input(SimpleNamespace(inputs={subject:legacy},role=self.role,locks=self.locks),subject)
        need(Path(value['paths']['web'])==self.locks[subject].path.with_name('ios-avatar-'+self.role+'-marker-web.json'))
        web_closures.command(dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-ios-web-closures',runId=self.run,fixtureUrl=value['markerFixtureUrl']))
        return value

    def capture_extra(self,actual):
        owner=actual['web'];need(type(owner) is IOSAvatarMarkerWebReceipts and not owner.historical)
        row=owner.capture();need(row['status']=='observed');return dict(web=row['index'])

    @staticmethod
    def recover_extra(actual):actual['web'].recover()

    def archives(self,subject,parts):
        exact(parts,{'owners','rows'});exact(parts['owners'],set(self.COMPONENTS));exact(parts['rows'],{'post','tail','left','right','web'})
        legacy=dict(owners={key:deepcopy(parts['owners'][key]) for key in IOSAvatarFinal.COMPONENTS},
            rows={key:deepcopy(parts['rows'][key]) for key in ('post','tail','left','right')})
        result=super().archives(subject,legacy);config=self.input(subject);ref=parts['owners']['web'];original=self.component(ref['index'],subject,'web',ref)
        owner=IOSAvatarMarkerWebReceipts.archive(original,store=Frozen(config['paths']['web'],original),root=Path(config['root']),
            binding=self.bindings[subject],run=self.run,role=self.role,lock=self.locks[subject],fixture_url=config['markerFixtureUrl'])
        need(owner.state['pending'] is None and integer(parts['rows']['web'],1,len(owner.state['rows'])))
        row=owner.state['rows'][parts['rows']['web']-1];need(row['status']=='observed');packet=owner.packet(row)
        follow(result['ui']['clockJoin']['nativeAfter'],packet['clockJoin']['nativeBefore'])
        follow(packet['clockJoin']['nativeAfter'],result['right']['clockJoin']['nativeBefore'])
        result.update(web=owner,webReceipt=packet);return result

    def _group(self,value):
        result=super()._group(value);a=value['acquisition']
        for parts in result.values():
            clock=parts['webReceipt']['clockJoin']
            need(a['hostBeforeEpochMs']<=clock['hostBeforeEpochMs']<=clock['hostAfterEpochMs']<=a['hostAfterEpochMs']
                and a['hostBeforeMonotonic']<=clock['hostBeforeMonotonic']<=clock['hostAfterMonotonic']<=a['hostAfterMonotonic'])
        return result

    def subject_quiet(self,samples,binding):
        from ios.adapters.avatar_final_quiet import subject_quiet
        result=subject_quiet(samples,binding,run=self.run,role=self.role,tail_reads=(4,))
        first,last=samples[0]['webReceipt'],samples[-1]['webReceipt'];a,b=first['clockJoin'],last['clockJoin']
        need(3000<=b['hostBeforeEpochMs']-a['hostAfterEpochMs']<60000
            and 3<=b['hostBeforeMonotonic']-a['hostAfterMonotonic']<60
            and 3000<=last['packet']['capturedEpochMs']-first['packet']['capturedEpochMs']<60000)
        for parts in samples:
            packet=parts['webReceipt']['packet'];web_closures.continuity(first['packet'],packet,int(binding['processIdentity'])) if packet is not first['packet'] else None
            need(same(packet['contexts'],first['packet']['contexts']) and packet['complete']
                and all(counter['pending']==0 for context in packet['contexts'] for counter in context['callbacks'].values())
                and all(context['resources']['policy-grant']['pending']==0 for context in packet['contexts']))
        return result


def final_type(value):
    need(type(value) is dict and type(value.get('iosAvatarFinalVersion')) is int)
    version=value['iosAvatarFinalVersion'];need(version in (1,2));return IOSAvatarHeldFinal if version==2 else IOSAvatarFinal
