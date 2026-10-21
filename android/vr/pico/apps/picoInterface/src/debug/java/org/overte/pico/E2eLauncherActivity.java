// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0

package org.overte.pico;

import android.app.Activity;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import android.system.Os;
import android.system.ErrnoException;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import org.overte.e2e.E2eLauncherActivityBase;

/** Shell-only entry point; this class does not exist in release APKs. */
public final class E2eLauncherActivity extends E2eLauncherActivityBase {
    @Override
    protected void prepareAdditionalAssets(File directory) throws IOException {
        copyAsset("scripted_interactable.js", directory);
        copyAsset("ControlledTextInput.qml", directory);
        // This APK-owned fixture script uses the existing immutable-resource
        // trust path. File/world scripts retain their normal consent checks.
        File scene = new File(directory, "scene.json");
        try {
            JSONObject contents = new JSONObject(new String(
                    Files.readAllBytes(scene.toPath()), StandardCharsets.UTF_8));
            JSONArray entities = contents.getJSONArray("Entities");
            int matches = 0;
            for (int index = 0; index < entities.length(); ++index) {
                JSONObject entity = entities.getJSONObject(index);
                if ("OVERTE_E2E_INTERACTABLE".equals(entity.optString("name"))) {
                    if (!"scripted_interactable.js".equals(entity.getString("script"))
                            || entity.getBoolean("locked")) {
                        throw new IOException("unexpected scripted fixture contract");
                    }
                    entity.put("script", "qrc:///overte-e2e/scripted_interactable.js");
                    ++matches;
                }
            }
            if (matches != 1) {
                throw new IOException("scripted fixture target must be unique");
            }
            File temporary = new File(directory, "scene.json.tmp");
            try (FileOutputStream output = new FileOutputStream(temporary, false)) {
                output.write(contents.toString().getBytes(StandardCharsets.UTF_8));
                output.getFD().sync();
            }
            if (!scene.delete() || !temporary.renameTo(scene)) {
                throw new IOException("could not commit scripted fixture URL");
            }
        } catch (JSONException exception) {
            throw new IOException("invalid scripted fixture scene", exception);
        }
    }

    @Override
    protected Class<? extends Activity> interfaceActivity() {
        // Debug/shell-only process setup before Qt/AccountManager construction.
        // Uses ordinary HTTPS trust and does not change saved account settings.
        String origin = getIntent().getStringExtra("org.overte.e2e.ACCOUNT_ORIGIN");
        if (origin != null) {
            if (!validAccountOrigin(origin)) {
                throw new IllegalArgumentException("Invalid owned account fixture origin");
            }
            try {
                Os.setenv("HIFI_METAVERSE_URL", origin, true);
            } catch (ErrnoException exception) {
                throw new IllegalStateException("Owned account fixture environment is unavailable");
            }
        }
        return PicoInterfaceActivity.class;
    }

    static boolean validAccountOrigin(String value) {
        if (value == null || value.isEmpty() || value.length() > 1024) { return false; }
        for (int index = 0; index < value.length(); ++index) {
            char character = value.charAt(index);
            if (character < 0x21 || character > 0x7e || character == '%') { return false; }
        }
        try {
            URI uri = new URI(value);
            String authority = uri.getRawAuthority();
            String path = uri.getRawPath();
            return "https".equals(uri.getScheme()) && uri.getHost() != null && !uri.getHost().isEmpty()
                    && uri.getRawUserInfo() == null && authority != null && !authority.contains("@")
                    && authority.equals(authority.toLowerCase(Locale.ROOT)) && !authority.endsWith(":")
                    && (uri.getPort() == -1 || uri.getPort() > 0 && uri.getPort() <= 65535)
                    && (path == null || path.isEmpty()) && uri.getRawQuery() == null
                    && uri.getRawFragment() == null && value.equals(uri.toASCIIString());
        } catch (URISyntaxException exception) {
            return false;
        }
    }
}
