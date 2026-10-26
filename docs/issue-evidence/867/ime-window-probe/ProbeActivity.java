package org.overte.test.imegeometry;

import android.app.Activity;
import android.graphics.Insets;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsAnimationControlListener;
import android.view.WindowInsetsAnimationController;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Isolated public-API experiment. No settings writes or Overte data access. */
public final class ProbeActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        String mode=getIntent().getStringExtra("mode");
        if (mode==null)mode="edge";
        if (mode.equals("dialog"))setTheme(android.R.style.Theme_Material_Light_Dialog_NoActionBar);
        super.onCreate(state);
        Window window=getWindow();
        WindowManager.LayoutParams attrs=window.getAttributes();
        attrs.layoutInDisplayCutoutMode=mode.equals("never")
            ? WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_NEVER
            : WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        window.setAttributes(attrs);
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        window.setDecorFitsSystemWindows(mode.equals("fit"));
        LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(160,80,160,40);
        TextView title=new TextView(this);title.setText("Issue 867 public IME geometry probe: "+mode);
        content.addView(title);
        EditText editor=new EditText(this);editor.setSingleLine(true);
        editor.setImeOptions(android.view.inputmethod.EditorInfo.IME_FLAG_NO_EXTRACT_UI
            | android.view.inputmethod.EditorInfo.IME_FLAG_NO_FULLSCREEN);
        editor.setHint("Empty geometry probe; no text is entered");
        editor.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        content.addView(editor,new LinearLayout.LayoutParams(-1,120));
        setContentView(content);
        Rect screen=getWindowManager().getMaximumWindowMetrics().getBounds();
        if(mode.equals("center")||mode.equals("dialog")) {
            window.setGravity(Gravity.CENTER);
            window.setLayout(screen.width()-264,mode.equals("dialog")?700:-1);
        } else window.setLayout(-1,-1);
        final String selection=mode;
        window.getDecorView().postDelayed(()->{
            window.getInsetsController().hide(WindowInsets.Type.systemBars());
            editor.requestFocus();
            ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(editor,0);
        },700);
        if(mode.equals("animation"))window.getDecorView().postDelayed(()->{
            window.getInsetsController().controlWindowInsetsAnimation(WindowInsets.Type.ime(),0,null,
                new CancellationSignal(),new WindowInsetsAnimationControlListener(){
                    @Override public void onReady(WindowInsetsAnimationController c,int types){
                        Insets shown=c.getShownStateInsets();
                        c.setInsetsAndAlpha(Insets.of(132,shown.top,132,shown.bottom),1f,1f);
                        android.util.Log.i("OverteImeProbe","requestedSideInsets=132 current="+c.getCurrentInsets()+" shown="+shown);
                        c.finish(true);
                    }
                    @Override public void onFinished(WindowInsetsAnimationController c){}
                    @Override public void onCancelled(WindowInsetsAnimationController c){}
                });
        },1800);
    }
}
