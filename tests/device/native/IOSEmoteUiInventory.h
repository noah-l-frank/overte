// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalEmoteControls.h"
#include <QPointer>
#include <QVector>
#include <QUuid>
namespace overte::e2e {
// Passive before hit-testing. Hidden/detached live roots stay visible here.
class IOSEmoteUiInventory {
public:
    void visit(QQuickItem* item) {
        if (!_complete || !item || !QCoreApplication::arguments().contains("--testScript")) { return; }
        const auto source=emoteComponentSource(item);if (source.isEmpty()) { return; }
        if (_roots.size()>=16) { _complete=false;return; }
        const auto id=identity(item);if (id.isEmpty()) { _complete=false;return; }
        const auto active=item->property("activeEmote");const auto names=emoteModel(item);
        if (active.userType()!=QMetaType::QString || names.size()!=10) { _complete=false;return; }
        _roots.append(QJsonObject{{"rootId",id},{"qmlSource",source},{"activeName",active.toString()},
            {"visible",item->isVisible()},{"enabled",item->isEnabled()},
            {"attached",item->parentItem()!=nullptr},{"windowPresent",item->window()!=nullptr}});
    }
    QJsonObject observation(bool treeComplete) const {
        const bool complete=treeComplete && _complete && QCoreApplication::arguments().contains("--testScript");
        return {{"iosEmoteUiInventoryVersion",1},{"complete",complete},{"roots",complete ? _roots : QJsonArray()}};
    }
private:
    static QString identity(QQuickItem* item) {
        struct Entry {QPointer<QQuickItem> item;QString id;};static QVector<Entry> entries;
        for (int i=entries.size()-1;i>=0;--i) { if (!entries[i].item) { entries.remove(i); } }
        for (const auto& entry:entries) { if (entry.item==item) { return entry.id; } }
        if (entries.size()>=256) { return {}; }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);entries.append(Entry{item,id});return id;
    }
    bool _complete {true};QJsonArray _roots;
};
} // namespace overte::e2e
#endif
