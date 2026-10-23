"""Original Worlds source-to-live-terminal seals.

Only actual restored source/image/input cuts and actor publication receipts can
qualify this seal. Native process/SDK end is a separate subsequent operation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_restoration import NavigationRestoration
from ios.adapters.navigation_publications import NavigationPublications
from ios.adapters.navigation_terminal_resources import held
from ios.adapters.navigation_cleanup_archive import archive as cleanup_archive

VERSION=1


class NavigationTerminal:
    def __init__(self,flow):
        need(type(flow) is IOSNavigationFeature and flow.role=='primary')
        self.flow,self.lock=flow,flow.lock;self.store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-terminal.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state):
        return dict(iosNavigationTerminalVersion=VERSION,runId=self.flow.run,artifactRoot=str(self.flow.root),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationTerminalVersion','runId','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosNavigationTerminalVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'description','references','seal','samples','live'})
        terminal.description(state['description'],area='world-navigation',run=self.flow.run)
        exact(state['references'],terminal.ROLES)
        if state['seal'] is None:need(state['samples'] is state['live'] is None)
        else:
            terminal.sealed(state['seal'],state['description'],state['samples']);need(type(state['live']) is dict
                and digest(state['live'])==state['seal']['liveOriginalSha256'])
        return deepcopy(state)

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def roles(self):
        result={};f=self.flow
        for role in terminal.ROLES:
            flow=IOSNavigationFeature(f.runtime,f.selector,f.client,f.run,f.root,role=role,epoch_ms=f.epoch_ms,monotonic=f.monotonic,sleep=f.sleep)
            # One actual SDK source lock protects both independent histories.
            flow.lock=f.lock
            result[role]=NavigationRestoration.from_history(flow)
        need(same(result['primary'].binding,result['actor'].binding));return result

    def original(self,owner,reference):
        measured=owner.validate_original(reference);image=owner.image(reference['requestId'],historical=True)
        return measured,held(image)

    def inspect(self):
        f=self.flow
        with f.held():
            f.load();f.current();f.fixture.attach()
            phase=f.fixture.read();need(phase['verb']=='cleanup' and phase['inputs']=={})
            owners=self.roles();references={role:owner.reference() for role,owner in owners.items()}
            actual={role:self.original(owner,references[role])[1] for role,owner in owners.items()}
            for owner in owners.values():owner.quiet();cleanup_archive(owner)
            if self.state is None:
                description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='world-navigation',runId=f.run,ticket=phase['ticket'],roles=actual)
                terminal.description(description);self.state=dict(description=description,references=references,seal=None,samples=None,live=None);self.save()
            else:
                description=self.state['description'];need(description['ticket']==phase['ticket'])
                for role,owner in owners.items():
                    _measured,original=self.original(owner,self.state['references'][role]);need(same(original,description['roles'][role]))
            return deepcopy(self.state['description'])

    def live_original(self,descriptor,samples):
        """Pure historical qualification; never a native/SDK/fixture request."""
        terminal.window(samples,descriptor);owners=self.roles();refs={};actual={};publications=None
        for role,owner in owners.items():
            owner.quiet();_facts,original=self.original(owner,self.state['references'][role])
            need(same(original,descriptor['roles'][role]));refs[role]={};actual[role]={}
            for row in owner.state['rows']:
                ref=dict(iosNavigationRestorationReferenceVersion=1,**row);measured,current=self.original(owner,ref)
                need(same(current['binding'],original['binding'])
                    and [item['resource'] for item in current['heldResources']]==[item['resource'] for item in original['heldResources']])
                refs[role][measured['public']['sequence']]=ref;actual[role][measured['public']['sequence']]=measured
            if role=='actor':
                old=owner.flow.prior_observers()['actor']
                publications=NavigationPublications(owner.admission,{0:old,1:owner.observer},transfer=owner.transfer,restoration=owner)
        journal=publications.state();need(journal is not None and journal['pending'] is None)
        # The unchanged actor publisher decoder already reopens each original
        # receipt and its actual source reference. Match the exact server row.
        from adapters.phase_witness_publisher import PhaseWitnessPublisher
        history=PhaseWitnessPublisher.archive(publications.store.read(),store=publications.store,binding=publications.binding,
            run=self.flow.run,area='world-navigation',fixture_url=self.flow.client.url,phase_instance=publications.phase_instance(),
            validate_original=publications.validate_original)
        archive=object.__new__(PhaseWitnessPublisher);archive.store=publications.store;archive.binding=publications.binding
        archive.run=self.flow.run;archive.area='world-navigation';archive.url=self.flow.client.url
        archive.instance=publications.phase_instance();archive.validate_original=publications.validate_original;archive.live=False
        receipts=[(reference,archive.load(reference)) for reference in history['records']]
        records=[]
        for pair in samples:
            p,a=pair['primary'],pair['actor'];ps,as_=p['sequence'],a['actorSequence']
            need(ps in actual['primary'] and as_ in actual['actor'] and same(p,actual['primary'][ps]['public'])
                and actual['actor'][as_]['ticket']==descriptor['ticket'])
            matches=[reference for reference,row in receipts if row['mode']=='published' and same(row['entry'],a)]
            need(len(matches)==1)
            records.append(dict(primary=deepcopy(refs['primary'][ps]),actor=deepcopy(refs['actor'][as_]),publication=deepcopy(matches[0])))
        return dict(iosNavigationTerminalLiveVersion=1,runId=self.flow.run,descriptionSha256=digest(descriptor),windowSha256=digest(samples),
            roles={role:dict(restorationSha256=digest(owner.previous),quiet=owner.quiet(),cleanup=cleanup_archive(owner))
                for role,owner in owners.items()},samples=records)

    def seal(self,descriptor,samples):
        f=self.flow
        with f.held():
            need(self.state is not None and same(self.store.read(),self.previous) and same(descriptor,self.state['description']))
            f.load();f.current();f.fixture.attach()
            phase=f.fixture.read();need(phase['verb']=='cleanup' and phase['ticket']==descriptor['ticket'] and phase['inputs']=={})
            actual=self.live_original(descriptor,samples)
            value=dict(featureTerminalSealVersion=1,description=deepcopy(descriptor),windowSha256=digest(samples),liveOriginalSha256=digest(actual))
            terminal.sealed(value,descriptor,samples)
            if self.state['seal'] is None:
                self.state.update(seal=value,samples=deepcopy(samples),live=actual);self.save()
            else:need(same(value,self.state['seal']) and same(actual,self.state['live']) and same(samples,self.state['samples']))
            return deepcopy(self.state['seal'])

    def replay(self):
        self.lock.assert_held();need(self.state is not None and self.state['seal'] is not None and same(self.store.read(),self.previous))
        actual=self.live_original(self.state['description'],self.state['samples']);need(same(actual,self.state['live']))
        terminal.sealed(self.state['seal'],self.state['description'],self.state['samples']);return deepcopy(self.state['seal'])

    def finish(self,seal):
        from ios.adapters.navigation_finalization import NavigationFinalization
        return NavigationFinalization(self).finish(seal)
