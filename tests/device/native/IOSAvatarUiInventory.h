// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalAvatarControls.h"
#include <QJsonArray>
namespace overte::e2e {
// Passive roots and actual child visibility, before hit-testing. The caller
// retains weak root pointers across visual detachment until real destruction.
class IOSAvatarUiInventory {
public:
    void visit(QQuickItem* item) {
        if (!_complete || !item || !QCoreApplication::arguments().contains("--testScript")) { return; }
        const auto source=avatarComponentSource(item);if (source.isEmpty()) { return; }
        if (_roots.size()>=16) { _complete=false;return; }
        const auto id=avatarRootId(item);if (id.isEmpty()) { _complete=false;return; }
        const bool people=source.endsWith("/Pal.qml");QJsonObject panels;
        const QList<QPair<QString,QString>> fields=people
            ? QList<QPair<QString,QString>>{{"connectionPrompt","connection"}}
            : QList<QPair<QString,QString>>{{"popup","popup"},{"createFavorite","favorite"},
                {"settings","settings"},{"adjustWearables","wearables"}};
        for (const auto& entry:fields) {
            const auto object=avatarNamed(item,entry.first);
            if (!object || object->property("visible").userType()!=QMetaType::Bool) { _complete=false;return; }
            panels[entry.second]=object->property("visible").toBool();
        }
        _roots.append(QJsonObject{{"rootId",id},{"qmlSource",source},{"role",people ? "people" : "avatar"},
            {"visible",item->isVisible()},{"enabled",item->isEnabled()},
            {"attached",item->parentItem()!=nullptr},{"windowPresent",item->window()!=nullptr},{"panels",panels}});
    }
    QJsonObject observation(bool treeComplete) const {
        const bool complete=treeComplete && _complete && QCoreApplication::arguments().contains("--testScript");
        return {{"iosAvatarUiInventoryVersion",1},{"complete",complete},{"roots",complete ? _roots : QJsonArray()}};
    }
private:
    bool _complete {true};QJsonArray _roots;
};
} // namespace overte::e2e
#endif
