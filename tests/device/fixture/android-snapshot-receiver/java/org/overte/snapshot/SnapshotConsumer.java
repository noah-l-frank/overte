// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;
import android.app.Activity;
import android.os.Bundle;
import java.io.IOException;

/** Ordinary separately installed ACTION_SEND consumer, not a chooser callback. */
public final class SnapshotConsumer extends Activity {
    private SnapshotConsumerEvidence owner;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try { owner=SnapshotReceiverState.get(this);owner.activity(true);owner.receive(SnapshotReceiverState.original(this,getIntent())); }
        catch(IOException | RuntimeException failure) { if(owner!=null)owner.rejected();finish(); }
    }
    @Override public void onDestroy() { if(owner!=null)owner.activity(false);super.onDestroy(); }
}
