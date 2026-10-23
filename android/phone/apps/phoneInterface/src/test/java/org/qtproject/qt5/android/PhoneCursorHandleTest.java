// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.qtproject.qt5.android;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import android.app.Activity;
import android.graphics.drawable.ColorDrawable;
import android.view.MotionEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputConnectionWrapper;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.Implementation;
import org.robolectric.annotation.Implements;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 35, manifest = Config.NONE,
        instrumentedPackages = {"org.qtproject.qt5.android"},
        shadows = {PhoneCursorHandleTest.QtNativeShadow.class})
public final class PhoneCursorHandleTest {
    @Test public void widthBeforeOverlayCreationIsZero() {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 0, 0, false);
        assertEquals(0, handle.width());
    }

    @Test public void widthWithoutDrawableIsZero() throws Exception {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 0, 0, false);
        setCursor(handle, new CursorView(activity, handle));
        assertEquals(0, handle.width());
    }

    @Test public void widthUsesInitializedDrawable() throws Exception {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 0, 0, false);
        CursorView cursor = new CursorView(activity, handle);
        cursor.setImageDrawable(new ColorDrawable() {
            @Override public int getIntrinsicWidth() { return 24; }
        });
        setCursor(handle, cursor);
        assertEquals(24, handle.width());
    }

    @Test public void releasePublishesFinalFingerPositionAfterLastMove() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_MOVE, 150, 300);
        touch(cursor, MotionEvent.ACTION_UP, 100, 300);
        assertEquals(2, handle.positions.size());
        assertEquals("-100,0", handle.positions.get(1));
    }

    @Test public void releaseWithoutMoveStillPublishesChangedFingerPosition() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_UP, 100, 320);
        assertEquals(1, handle.positions.size());
        assertEquals("-100,20", handle.positions.get(0));
    }

    @Test public void horizontalFingerMoveDoesNotJumpVertically() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_MOVE, 150, 300);
        assertEquals("-50,0", handle.positions.get(0));
    }

    @Test public void nativeCursorPointPreservesOriginalCaretAndFingerDelta() throws Exception {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 1, 0, false);
        for (String name : new String[] {"m_posX", "m_posY"}) {
            Field field = CursorHandle.class.getDeclaredField(name);
            field.setAccessible(true);
            field.setInt(handle, name.equals("m_posX") ? 100 : 200);
        }
        QtNativeShadow.calls = 0;
        handle.updatePosition(8, 6);
        assertEquals(1, QtNativeShadow.calls);
        assertEquals(108, QtNativeShadow.x);
        assertEquals(206, QtNativeShadow.y);
    }

    @Implements(value = QtNative.class, isInAndroidSdk = false)
    public static final class QtNativeShadow {
        static int calls, x, y, seenContext;
        static boolean throwOnCall;
        @Implementation protected static void handleLocationChanged(int id, int pointX, int pointY) {
            ++calls; x = pointX; y = pointY;
            seenContext = HandleActivity.context;
            if (throwOnCall) throw new IllegalStateException("Expected native boundary failure");
        }
    }

    public static final class HandleActivity extends Activity {
        static int context;
        final List<Integer> notifications = new ArrayList<>();
        public void onNativeCursorHandle(int id) { context = id; notifications.add(id); }
    }

    @Test public void cursorHandleIdentitySurroundsTheOriginalQtCallback() {
        HandleActivity activity = Robolectric.buildActivity(HandleActivity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 3, 0, false);
        handle.updatePosition(8, 6);
        assertEquals(3, QtNativeShadow.seenContext);
        assertEquals(java.util.Arrays.asList(3, 0), activity.notifications);
        assertEquals(0, HandleActivity.context);
    }

    @Test public void nativeCallbackFailureStillClearsHandleIdentity() {
        HandleActivity activity = Robolectric.buildActivity(HandleActivity.class).setup().get();
        CursorHandle handle = new CursorHandle(activity, new View(activity), 2, 0, false);
        QtNativeShadow.throwOnCall = true;
        try {
            assertThrows(IllegalStateException.class, () -> handle.updatePosition(8, 6));
            assertEquals(2, QtNativeShadow.seenContext);
            assertEquals(java.util.Arrays.asList(2, 0), activity.notifications);
            assertEquals(0, HandleActivity.context);
        } finally {
            QtNativeShadow.throwOnCall = false;
        }
    }

    @Test public void stationaryTapDoesNotMoveCursor() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_UP, 200, 300);
        assertEquals(0, handle.positions.size());
    }

    @Test public void unchangedReleaseDoesNotRepeatLastMove() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_MOVE, 150, 300);
        touch(cursor, MotionEvent.ACTION_UP, 150, 300);
        assertEquals(1, handle.positions.size());
    }

    @Test public void cancelAndOrphanEventsDoNotMoveCursor() {
        RecordingCursorHandle handle = recordingHandle();
        CursorView cursor = cursorView(handle);
        touch(cursor, MotionEvent.ACTION_DOWN, 200, 300);
        touch(cursor, MotionEvent.ACTION_MOVE, 150, 300);
        touch(cursor, MotionEvent.ACTION_CANCEL, 100, 300);
        touch(cursor, MotionEvent.ACTION_MOVE, 90, 300);
        touch(cursor, MotionEvent.ACTION_UP, 80, 300);
        assertEquals(1, handle.positions.size());
    }

    @Test public void modernEmptyReplacementReachesTheNativeEditor() throws Exception {
        RecordingInputConnection editor = recordingInputConnection();
        InputConnection connection = productionConnectionType(editor);
        assertEquals(true, connection.replaceText(4, 1429, "", 1, null));
        assertEquals(java.util.Arrays.asList(
                "begin", "finish", "select:4:1429", "commit::1", "end"), editor.calls);
    }

    @Test public void modernReplacementPreservesReverseRangeAndCursorArgument() throws Exception {
        RecordingInputConnection editor = recordingInputConnection();
        InputConnection connection = productionConnectionType(editor);
        assertEquals(true, connection.replaceText(8, 4, "replacement", -1, null));
        assertEquals(java.util.Arrays.asList(
                "begin", "finish", "select:8:4", "commit:replacement:-1", "end"), editor.calls);
    }

    @Test public void modernReplacementBalancesTheBatchWhenNativeEditorRejectsIt() throws Exception {
        RecordingInputConnection editor = recordingInputConnection();
        editor.finishAccepted = false;
        assertEquals(false, productionConnectionType(editor).replaceText(0, 4, "", 1, null));
        assertEquals(java.util.Arrays.asList("begin", "finish", "end"), editor.calls);
    }

    @Test @Config(sdk = 26) public void olderAndroidRetainsTheLegacyQtConnection() {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        QtEditText view = new QtEditText(activity, null);
        EditorInfo attributes = new EditorInfo();
        assertEquals(QtInputConnection.class, view.onCreateInputConnection(attributes).getClass());
        assertEquals(EditorInfo.IME_FLAG_NO_FULLSCREEN | EditorInfo.IME_FLAG_NO_EXTRACT_UI,
                attributes.imeOptions & (EditorInfo.IME_FLAG_NO_FULLSCREEN | EditorInfo.IME_FLAG_NO_EXTRACT_UI));
    }

    private static RecordingInputConnection recordingInputConnection() {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        return new RecordingInputConnection(new QtEditText(activity, null));
    }

    // Instantiate the connection type selected by the real product with a spy
    // at its existing native editor boundary. No Android/JNI implementation is copied.
    private static InputConnection productionConnectionType(RecordingInputConnection editor) throws Exception {
        InputConnection selected = editor.view.onCreateInputConnection(new EditorInfo());
        if (selected instanceof InputConnectionWrapper) {
            java.lang.reflect.Constructor<?> constructor =
                    selected.getClass().getDeclaredConstructor(InputConnection.class);
            constructor.setAccessible(true);
            return (InputConnection) constructor.newInstance(editor);
        }
        assertEquals(QtInputConnection.class, selected.getClass());
        return editor;
    }

    private static final class RecordingInputConnection extends QtInputConnection {
        final QtEditText view;
        final List<String> calls = new ArrayList<>();
        boolean finishAccepted = true;
        RecordingInputConnection(QtEditText view) { super(view); this.view = view; }
        @Override public boolean beginBatchEdit() { calls.add("begin"); return true; }
        @Override public boolean endBatchEdit() { calls.add("end"); return true; }
        @Override public boolean finishComposingText() { calls.add("finish"); return finishAccepted; }
        @Override public boolean setSelection(int start, int end) {
            calls.add("select:" + start + ":" + end); return true;
        }
        @Override public boolean commitText(CharSequence text, int cursor) {
            calls.add("commit:" + text + ":" + cursor); return true;
        }
    }

    private static RecordingCursorHandle recordingHandle() {
        return new RecordingCursorHandle(
                Robolectric.buildActivity(Activity.class).setup().get());
    }

    private static CursorView cursorView(RecordingCursorHandle handle) {
        CursorView cursor = new CursorView(handle.activity, handle);
        cursor.layout(0, 0, 50, 60);
        return cursor;
    }

    private static void touch(CursorView cursor, int action, float x, float y) {
        MotionEvent event = MotionEvent.obtain(1, 2, action, x, y, 0);
        try {
            cursor.onTouchEvent(event);
        } finally {
            event.recycle();
        }
    }

    private static final class RecordingCursorHandle extends CursorHandle {
        final Activity activity;
        final List<String> positions = new ArrayList<>();

        RecordingCursorHandle(Activity activity) {
            super(activity, new View(activity), 0, 0, false);
            this.activity = activity;
        }

        @Override public void updatePosition(int x, int y) {
            positions.add(x + "," + y);
        }
    }

    private static void setCursor(CursorHandle handle, CursorView cursor) throws Exception {
        Field field = CursorHandle.class.getDeclaredField("m_cursorView");
        field.setAccessible(true);
        field.set(handle, cursor);
    }
}
