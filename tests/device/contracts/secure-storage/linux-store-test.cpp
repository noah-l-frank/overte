// SPDX-License-Identifier: Apache-2.0
// Host-only native adapter contract. The child is a private D-Bus test double;
// real keyring persistence and normal client login require separate lab evidence.
#include <QString>
#include <QCoreApplication>
#include <QProcess>
#include <QVariant>
#include <QtDBus/QDBusArgument>
#include <QtDBus/QDBusConnection>
#include <QtDBus/QDBusMessage>
#include <QtDBus/QDBusMetaType>
#include <QtDBus/QDBusObjectPath>
#include <QtDBus/QDBusVariant>
#include <QtDBus/QDBusVirtualObject>
#include <cassert>
#include <cstdio>
#include <sys/resource.h>
#include "../../../../security/storage/LinuxProtectedAccountStore.h"

using namespace overte::security;
using Paths = QList<QDBusObjectPath>;
using Attributes = QMap<QString, QString>;
struct WireSecret { QDBusObjectPath session; QByteArray parameters, value; QString contentType; };
Q_DECLARE_METATYPE(WireSecret)
QDBusArgument& operator<<(QDBusArgument& wire, const WireSecret& value) {
    wire.beginStructure(); wire << value.session << value.parameters << value.value << value.contentType; wire.endStructure(); return wire;
}
const QDBusArgument& operator>>(const QDBusArgument& wire, WireSecret& value) {
    wire.beginStructure(); wire >> value.session >> value.parameters >> value.value >> value.contentType; wire.endStructure(); return wire;
}
const QString ROOT = QStringLiteral("/org/freedesktop/secrets");
const QString COLLECTION = ROOT + QStringLiteral("/collection/login");
const QString SESSION = ROOT + QStringLiteral("/session/one");
class Service final : public QDBusVirtualObject {
public:
    QString introspect(const QString&) const override { return {}; }
    bool handleMessage(const QDBusMessage& message, const QDBusConnection& bus) override {
        const auto args = message.arguments(); const auto method = message.member();
        auto reply = [&](const QVariantList& values = {}) { return bus.send(message.createReply(values)); };
        auto fail = [&](const QString& name) { return bus.send(message.createErrorReply(name, QStringLiteral("synthetic fault"))); };
        if (message.interface() == QStringLiteral("org.overte.SecretStoreTest")) {
            const auto action = args.at(0).toString();
            if (action == QStringLiteral("locked")) { locked = args.at(1).toBool(); }
            else if (action == QStringLiteral("itemLocked")) { itemLocked = args.at(1).toBool(); }
            else if (action == QStringLiteral("aliasAbsent")) { aliasAbsent = args.at(1).toBool(); }
            else if (action == QStringLiteral("duplicates")) { count = 2; }
            else if (action == QStringLiteral("mime")) { contentType = args.at(1).toString(); }
            else if (action == QStringLiteral("parameters")) { parameters = args.at(1).toByteArray(); }
            else if (action == QStringLiteral("badSession")) { badSession = args.at(1).toBool(); }
            else if (action == QStringLiteral("prompt")) { prompt = args.at(1).toBool(); }
            else if (action == QStringLiteral("error")) { nextError = args.at(1).toString(); }
            else if (action == QStringLiteral("oversize")) { data.fill('x', int(MAX_ACCOUNT_BYTES + 1)); }
            else if (action == QStringLiteral("empty")) { data.clear(); }
            else { return false; }
            return reply();
        }
        if (!nextError.isEmpty()) { auto error = nextError; nextError.clear(); return fail(error); }
        if (method == QStringLiteral("ReadAlias")) {
            assert(args.size() == 1 && args.front().toString() == QStringLiteral("default"));
            return reply({ QVariant::fromValue(QDBusObjectPath(aliasAbsent ? QStringLiteral("/") : COLLECTION)) });
        }
        if (method == QStringLiteral("Get") && message.interface() == QStringLiteral("org.freedesktop.DBus.Properties")) {
            assert(args.at(0).toString() == QStringLiteral("org.freedesktop.Secret.Collection"));
            assert(args.at(1).toString() == QStringLiteral("Locked"));
            return reply({ QVariant::fromValue(QDBusVariant(locked)) });
        }
        if (method == QStringLiteral("SearchItems")) {
            const auto attributes = qdbus_cast<Attributes>(args.front());
            assert(attributes.size() == 2 && attributes.value(QStringLiteral("application")) == QStringLiteral("org.overte.interface"));
            assert(attributes.value(QStringLiteral("record")) == QStringLiteral("account-map-v1"));
            Paths paths; for (int n = 0; n < count; ++n) { paths.append(QDBusObjectPath(COLLECTION + QStringLiteral("/item%1").arg(n))); }
            return reply({ QVariant::fromValue(itemLocked ? Paths() : paths), QVariant::fromValue(itemLocked ? paths : Paths()) });
        }
        if (method == QStringLiteral("OpenSession")) {
            assert(args.front().toString() == QStringLiteral("plain"));
            return reply({ QVariant::fromValue(QDBusVariant(QString())), QVariant::fromValue(QDBusObjectPath(SESSION)) });
        }
        if (method == QStringLiteral("Close")) { return reply(); }
        if (method == QStringLiteral("GetSecret")) {
            assert(qdbus_cast<QDBusObjectPath>(args.front()).path() == SESSION);
            if (locked || itemLocked) { return fail(QStringLiteral("org.freedesktop.Secret.Error.IsLocked")); }
            WireSecret value { QDBusObjectPath(badSession ? ROOT : SESSION), parameters, data, contentType };
            return reply({ QVariant::fromValue(value) });
        }
        if (method == QStringLiteral("CreateItem") || method == QStringLiteral("SetSecret")) {
            if (locked || itemLocked) { return fail(QStringLiteral("org.freedesktop.Secret.Error.IsLocked")); }
            const auto value = qdbus_cast<WireSecret>(args.at(method == QStringLiteral("CreateItem") ? 1 : 0));
            assert(value.session.path() == SESSION && value.parameters.isEmpty());
            assert(value.contentType == QStringLiteral("application/octet-stream"));
            data = value.value; contentType = value.contentType; count = 1;
            if (method == QStringLiteral("SetSecret")) { return reply(); }
            const auto properties = qdbus_cast<QVariantMap>(args.at(0));
            assert(properties.contains(QStringLiteral("org.freedesktop.Secret.Item.Attributes")));
            assert(args.at(2).toBool());
            return reply({ QVariant::fromValue(QDBusObjectPath(COLLECTION + QStringLiteral("/item0"))), QVariant::fromValue(QDBusObjectPath(QStringLiteral("/"))) });
        }
        if (method == QStringLiteral("Delete")) {
            if (locked || itemLocked) { return fail(QStringLiteral("org.freedesktop.Secret.Error.IsLocked")); }
            if (!prompt) { --count; }
            return reply({ QVariant::fromValue(QDBusObjectPath(prompt ? ROOT + QStringLiteral("/prompt/one") : QStringLiteral("/"))) });
        }
        return false;
    }
    bool locked { false }, itemLocked { false }, aliasAbsent { false }, badSession { false }, prompt { false };
    int count { 0 };
    QByteArray data, parameters;
    QString contentType { QStringLiteral("application/octet-stream") }, nextError;
};
static void control(const QString& action, const QVariant& value = {}) {
    auto message = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.secrets"), ROOT,
        QStringLiteral("org.overte.SecretStoreTest"), QStringLiteral("Set"));
    message.setArguments({ action, value.isValid() ? value : QVariant(false) });
    assert(QDBusConnection::sessionBus().call(message).type() == QDBusMessage::ReplyMessage);
}
int main(int argc, char** argv) {
    const rlimit core { 0, 0 }; assert(setrlimit(RLIMIT_CORE, &core) == 0);
    QCoreApplication app(argc, argv);
    qDBusRegisterMetaType<WireSecret>(); qDBusRegisterMetaType<Paths>(); qDBusRegisterMetaType<Attributes>();
    if (app.arguments().contains(QStringLiteral("--service"))) {
        Service service;
        auto bus = QDBusConnection::sessionBus();
        assert(bus.registerService(QStringLiteral("org.freedesktop.secrets")));
        assert(bus.registerVirtualObject(ROOT, &service, QDBusConnection::SubPath));
        std::puts("READY"); std::fflush(stdout); return app.exec();
    }
    // Run only under a new dbus-run-session; never claim an existing user's service.
    auto activatable = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.DBus"),
        QStringLiteral("/org/freedesktop/DBus"), QStringLiteral("org.freedesktop.DBus"), QStringLiteral("ListActivatableNames"));
    const auto services = QDBusConnection::sessionBus().call(activatable);
    assert(services.type() == QDBusMessage::ReplyMessage && services.arguments().size() == 1);
    assert(!qdbus_cast<QStringList>(services.arguments().front()).contains(QStringLiteral("org.freedesktop.secrets")));
    auto store = linuxProtectedAccountStore(); AccountBytes out { 99 };
    assert(store->read(out) == StoreResult::Unavailable && out.empty());
    QProcess child; child.setProgram(QCoreApplication::applicationFilePath()); child.setArguments({ QStringLiteral("--service") });
    child.start(); assert(child.waitForStarted(5000) && child.waitForReadyRead(5000)); assert(child.readLine() == QByteArray("READY\n"));
    const AccountBytes first { 0, 1, 2, 128, 255, 0, 7 }, second { 4, 3, 2, 0 };
    assert(store->read(out) == StoreResult::Absent && out.empty());
    assert(store->write({}) == StoreResult::Corrupt);
    assert(store->write(AccountBytes(MAX_ACCOUNT_BYTES + 1, 1)) == StoreResult::Corrupt);
    assert(store->write(first) == StoreResult::Ok);
    assert(store->read(out) == StoreResult::Ok && out == first);
    assert(store->write(second) == StoreResult::Ok);
    auto restarted = linuxProtectedAccountStore(); assert(restarted->read(out) == StoreResult::Ok && out == second);
    control(QStringLiteral("locked"), true); out = first;
    assert(store->read(out) == StoreResult::Locked && out.empty());
    assert(store->write(first) == StoreResult::Locked && store->erase() == StoreResult::Locked);
    control(QStringLiteral("locked"), false);
    control(QStringLiteral("itemLocked"), true); assert(store->read(out) == StoreResult::Locked && out.empty());
    assert(store->erase() == StoreResult::Locked); control(QStringLiteral("itemLocked"), false);
    // Actual GNOME Keyring normalizes this metadata while retaining binary bytes.
    control(QStringLiteral("mime"), QStringLiteral("text/plain")); assert(store->read(out) == StoreResult::Ok && out == second);
    assert(restarted->read(out) == StoreResult::Ok && out == second);
    control(QStringLiteral("mime"), QStringLiteral("image/png")); assert(store->read(out) == StoreResult::Corrupt && out.empty());
    control(QStringLiteral("mime"), QStringLiteral("application/octet-stream"));
    control(QStringLiteral("parameters"), QByteArray("unexpected")); assert(store->read(out) == StoreResult::Corrupt && out.empty());
    control(QStringLiteral("parameters"), QByteArray());
    control(QStringLiteral("badSession"), true); assert(store->read(out) == StoreResult::Corrupt && out.empty()); control(QStringLiteral("badSession"), false);
    control(QStringLiteral("oversize")); assert(store->read(out) == StoreResult::Corrupt && out.empty());
    control(QStringLiteral("empty")); assert(store->read(out) == StoreResult::Corrupt && out.empty());
    assert(store->write(first) == StoreResult::Ok);
    control(QStringLiteral("duplicates")); assert(store->read(out) == StoreResult::Corrupt && out.empty());
    assert(store->write(second) == StoreResult::Corrupt && store->erase() == StoreResult::Ok);
    assert(store->read(out) == StoreResult::Absent);
    control(QStringLiteral("aliasAbsent"), true); assert(store->read(out) == StoreResult::Unavailable && out.empty()); control(QStringLiteral("aliasAbsent"), false);
    control(QStringLiteral("error"), QStringLiteral("org.freedesktop.DBus.Error.ServiceUnknown")); assert(store->read(out) == StoreResult::Unavailable && out.empty());
    control(QStringLiteral("error"), QStringLiteral("org.freedesktop.DBus.Error.Failed")); assert(store->read(out) == StoreResult::IoError && out.empty());
    assert(store->write(first) == StoreResult::Ok); control(QStringLiteral("prompt"), true);
    assert(store->erase() == StoreResult::Locked); control(QStringLiteral("prompt"), false);
    assert(store->erase() == StoreResult::Ok && store->read(out) == StoreResult::Absent && out.empty());
    child.terminate(); assert(child.waitForFinished(5000));
    clearAccountBytes(out);
    std::puts("PASS: production Linux store binary records, restart, locked/missing services, corruption, duplicate records and erase; no real-keyring or client-login claim");
}
