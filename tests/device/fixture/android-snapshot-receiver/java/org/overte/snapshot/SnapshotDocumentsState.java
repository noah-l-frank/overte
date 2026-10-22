// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.os.Handler;
import android.os.HandlerThread;
import java.io.IOException;

/** Independent Documents lifetime: never obtains/arms the share Consumer. */
final class SnapshotDocumentsState {
    private static SnapshotDocumentsState state;
    final SnapshotDocumentsEvidence source;
    private final HandlerThread callbacks=new HandlerThread("OverteSnapshotDocumentsClose");
    final Handler handler;
    private SnapshotDocumentsState(Context context) throws IOException {
        source=new SnapshotDocumentsEvidence(context.getFilesDir().toPath());callbacks.start();handler=new Handler(callbacks.getLooper());
    }
    static synchronized SnapshotDocumentsState get(Context context,boolean create) throws IOException {
        if(!SnapshotReceiverState.PACKAGE.equals(context.getPackageName()) || (context.getApplicationInfo().flags&ApplicationInfo.FLAG_DEBUGGABLE)==0)throw new IOException("Standalone debug fixture required");
        if(state==null && create)state=new SnapshotDocumentsState(context);return state;
    }
    void retire(String run) throws IOException {
        source.retire(run);callbacks.quitSafely();
        try { callbacks.join(5000);if(callbacks.isAlive())throw new IOException("Document callback thread remains alive"); }
        catch(InterruptedException failure) { Thread.currentThread().interrupt();throw new IOException("Document callback retirement interrupted"); }
    }
    boolean callbacksTerminated() { return !callbacks.isAlive(); }
}
