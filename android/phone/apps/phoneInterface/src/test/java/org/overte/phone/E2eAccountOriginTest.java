// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.phone;

import org.junit.Test;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/** Parser checks only; no Activity, environment mutation, credentials or network. */
public class E2eAccountOriginTest {
    @Test public void acceptsOnlyClosedCanonicalHttpsOrigins() {
        for (String value : new String[] {"https://owned.invalid", "https://127.0.0.1:10443", "https://[::1]:10443"}) {
            assertTrue(E2eLauncherActivity.validAccountOrigin(value));
        }
    }

    @Test public void rejectsCredentialsAlternateSpellingsAndAdditionalComponents() {
        for (String value : new String[] {"", "http://owned.invalid", "https://u:p@owned.invalid",
                "https://owned.invalid/", "https://owned.invalid?x", "https://owned.invalid#x",
                "https://owned.invalid:0", "https://owned.invalid:65536", "https://owned.invalid:",
                "https://OWNED.invalid", "https://%65vil.invalid", "https://$(echo-x)",
                "https://owned.invalid\n", "https://owned.invalid/path", "https://-bad.invalid"}) {
            assertFalse(E2eLauncherActivity.validAccountOrigin(value));
        }
        assertFalse(E2eLauncherActivity.validAccountOrigin(null));
    }
}
