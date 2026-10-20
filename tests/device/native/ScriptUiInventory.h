// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalScriptFileControls.h"
#include <QSet>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
// Collected during the original bounded whole-tree UI walk, including hidden
// items. Input eligibility and modal suppression never determine this inventory.
class ScriptUiInventory {
public:
    void visit(QQuickItem* item) {
        if (!_complete) { return; }
        if (_seen.contains(item)) { _complete=false;return; }
        _seen.insert(item);
        if (item->objectName()=="RunningScripts") {
            const auto manager=scriptManagerRootStatus(item);
            if (!manager.value("available").toBool() || _managers.size()>=16) { _complete=false;return; }
            _managers.append(manager);
        } else if (item->objectName()=="nativeFileBrowser") {
            // Other original file browsers are not Script pickers. Matching
            // captions without the exact original component are unknown.
            if (item->property("caption").toString()!="Open Script and Companion Files") { return; }
            if (!scriptFileBrowser(item) || _pickers.size()>=16) { _complete=false;return; }
            QQmlContext* original {nullptr};int contexts {0};
            for (auto context=qmlContext(item);context && ++contexts<=128;context=context->parentContext()) {
                if (context->thread()==item->thread() && context->nameForObject(item)=="root"
                        && context->baseUrl()==PathUtils::qmlUrl(QStringLiteral("dialogs/NativeFileBrowser.qml"))) {
                    original=context;break;
                }
            }
            const auto closing=item->property("closing"),request=item->property("requestId"),error=item->property("error");
            if (!original || closing.userType()!=QMetaType::Bool || request.userType()!=QMetaType::QString
                    || error.userType()!=QMetaType::QString || request.toString().size()>4096
                    || error.toString().size()>8192) { _complete=false;return; }
            _pickers.append(QJsonObject{{"componentSource",original->baseUrl().toString(QUrl::FullyEncoded)},
                {"visible",scriptManagerVisible(item)},{"closing",closing.toBool()},
                {"requestId",request.toString()},{"errorText",error.toString()}});
        }
    }

    QJsonObject observation(bool wholeTreeReady) const {
        const bool complete=wholeTreeReady && _complete;
        // Partial arrays cannot be mistaken for a complete empty inventory.
        return {{"inventoryVersion",1},{"complete",complete},
            {"managers",complete ? _managers : QJsonArray()},
            {"pickers",complete ? _pickers : QJsonArray()}};
    }

private:
    bool _complete {true};
    QSet<QQuickItem*> _seen;
    QJsonArray _managers,_pickers;
};
#endif
} // namespace overte::e2e
