// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QInputMethodQueryEvent>
#include <QThread>

// QInputMethod::queryFocusObject can carry a point. QInputMethodQueryEvent
// alone drops that argument when the native widget forwards to offscreen UI.
class InputMethodQueryEventWithArgument : public QInputMethodQueryEvent {
public:
    InputMethodQueryEventWithArgument(Qt::InputMethodQuery query, const QVariant& argument)
        : QInputMethodQueryEvent(query), argument(argument), _query(query) { ignore(); }

    const QVariant argument;

    bool queryOwner(QObject* owner, const QVariant& localArgument) {
        ignore();
        if (!owner || owner->thread() != QThread::currentThread()) { return false; }
        QVariant result;
        const bool queried = QMetaObject::invokeMethod(owner, "inputMethodQuery", Qt::DirectConnection,
            Q_RETURN_ARG(QVariant, result), Q_ARG(Qt::InputMethodQuery, _query), Q_ARG(QVariant, localArgument));
        if (!queried || !result.isValid()) { return false; }
        setValue(_query, result);
        accept();
        return true;
    }

private:
    const Qt::InputMethodQuery _query;
};
