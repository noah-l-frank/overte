"""Actual Callback8 inspect/seal factory and original-membership barrier.

The production controller/journal/receipt/role decoders run unchanged except
explicit profile selection. Native/SDK/Qt/GPU are models; Finish is CLOSED.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.adapters.emote_callback_terminal import IOSEmoteCallbackTerminal,IOSEmoteCallbackTerminalJournal
from ios.adapters.emote_observer import EmoteObservationPending
from ios.self_tests.emote_callback_terminal_fixture import paired


class CallbackTerminalTests(unittest.TestCase):
    def counts(self,f):
        return dict(primary=len(f.target.domain.history),actor=len(f.actor.target.domain.history),
            inputs=deepcopy(f.target.domain.io.actions),actorInputs=deepcopy(f.actor.target.domain.io.actions),
            gpu={role:[deepcopy(q) for slot in t.callback_context.worlds.values() for q in slot.commands]
                for role,t in (('primary',f.target),('actor',f.actor.target))})

    def test_normal_feature8_inspect_and_seal_use_actual_roles_receipts_journal_and_refuse_finish(self):
        f=paired(self);p,a=f.flow,f.actor.flow;reader=Client(f.target.client.url,'r'*64)
        call=dict(contractVersion=16,runId=p.run,afterSequence=0)
        p.observe(call);a.observe(call);p.act(f.call('play',name='Crying'));f.target.native.sleep(.25)
        self.assertTrue(a.observe(call)['state']['override']);p.act(f.call('cancel'));self.assertFalse(a.observe(call)['state']['override'])
        f.call('cleanup');cleanup=dict(contractVersion=16,runId=p.run)
        def waiting(seconds):
            if p.lock._owner is None and p.primary_lock._owner is None:
                self.assertIsNone(a.lock._owner);a.cleanup(cleanup)
            f.target.domain.sleep(seconds)
        p.sleep=waiting;self.assertEqual(dict(performed=True),p.cleanup(cleanup))
        samples=[]
        for index in range(3):
            primary=p.observe(call);actor=a.observe(call);witness=reader.request('/runs/'+p.run)
            entries=[row for row in witness['entries'] if row['actorSequence']==actor['sequence']]
            self.assertEqual(1,len(entries));samples.append(dict(primary=primary,actor=entries[0]))
            if index<2:f.target.domain.sleep(1.6)
        # This exact unknown source is not a mutable terminal output, and it
        # has no typed original reader. It must block BEFORE journal birth.
        journal_path=p.store.path.with_name('ios-emote-primary-'+p.run+'-terminal.json')
        orphan=p.root/'emote-foreign-unowned-obligation.json';orphan.write_bytes(b'{}');orphan.chmod(0o600)
        before=self.counts(f)
        with self.assertRaises(NativeUIError):p.terminal(dict(contractVersion=16,runId=p.run,stage='inspect'))
        self.assertIsNone(PrivateFeatureState(journal_path).read());self.assertEqual(before,self.counts(f))
        # The fixture removes only the exact newly introduced counterexample,
        # with byte/inode binding; no product cleanup/adoption is invoked.
        identity=orphan.stat();self.assertEqual(b'{}',orphan.read_bytes())
        self.assertEqual((identity.st_dev,identity.st_ino),(orphan.stat().st_dev,orphan.stat().st_ino));orphan.unlink()
        inspected=p.terminal(dict(contractVersion=16,runId=p.run,stage='inspect'))
        self.assertEqual('inspect',inspected['stage']);value=PrivateFeatureState(journal_path).read()
        self.assertEqual(2,value['iosEmoteTerminalJournalVersion'])
        sealed=p.terminal(dict(contractVersion=16,runId=p.run,stage='seal',description=inspected['description'],samples=samples))
        self.assertEqual('seal',sealed['stage']);self.assertEqual(before,self.counts(f))
        with a.held(30):
            controller=IOSEmoteCallbackTerminal(p,a);window=controller.window();journal=IOSEmoteCallbackTerminalJournal(window,check=controller.guard)
            self.assertEqual('sealed',journal.state['phase']);proof=journal.originals.read(journal.originals.expand(journal.state['record']))
            journal.proof(proof,journal.state);self.assertEqual(2,proof['original']['iosEmoteTerminalWindowVersion'])
            with self.assertRaises(NativeUIError):IOSEmoteTerminalJournal(window)
        with self.assertRaises(NativeUIError):IOSEmoteTerminal(p,a)
        files={str(path):(path.stat().st_ino,path.read_bytes()) for root in (p.root,a.root) for path in root.rglob('*') if path.is_file()}
        with self.assertRaises(EmoteObservationPending):p.terminal(dict(contractVersion=16,runId=p.run,stage='finish',seal=sealed['seal']))
        self.assertEqual(before,self.counts(f));self.assertEqual(files,{str(path):(path.stat().st_ino,path.read_bytes())
            for root in (p.root,a.root) for path in root.rglob('*') if path.is_file()})
        self.assertIsNone(p.lock._owner);self.assertIsNone(a.lock._owner)


if __name__=='__main__':unittest.main()
