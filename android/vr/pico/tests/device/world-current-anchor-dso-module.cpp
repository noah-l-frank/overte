// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/PicoWorldCurrentDocumentBridge.h"
extern "C" Q_DECL_EXPORT const void* original_anchor(const QVariantMap& command){
    return overte::e2e::picoCurrentAnchor(command).get();
}
