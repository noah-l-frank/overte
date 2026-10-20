// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0

package org.overte.phone;

import android.app.Activity;
import java.io.File;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import android.system.Os;
import android.system.ErrnoException;

import org.overte.e2e.E2eLauncherActivityBase;

/** Shell-only entry point; this class does not exist in release APKs. */
public final class E2eLauncherActivity extends E2eLauncherActivityBase {
    @Override
    protected String[] additionalAssets() {
        return new String[] { "scripted_interactable.js" };
    }

    @Override
    protected String additionalAssetUrl(String asset, File directory) {
        return "qrc:/overte-e2e/scripted_interactable.js";
    }

    @Override
    protected Class<? extends Activity> interfaceActivity() {
        // This Activity exists only in debug APKs and its manifest requires the
        // shell permission. Configure the existing process environment before
        // Qt/AccountManager initialization. No saved endpoint or TLS trust is
        // modified, and no login/logout/request is performed here.
        String accountOrigin = getIntent().getStringExtra("org.overte.e2e.ACCOUNT_ORIGIN");
        if (accountOrigin != null) {
            if (!validAccountOrigin(accountOrigin)) {
                throw new IllegalArgumentException("Invalid owned account fixture origin");
            }
            try {
                Os.setenv("HIFI_METAVERSE_URL", accountOrigin, true);
            } catch (ErrnoException exception) {
                throw new IllegalStateException("Owned account fixture environment is unavailable");
            }
        }
        PhoneE2eLaunchState.begin();
        return PhoneInterfaceActivity.class;
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
