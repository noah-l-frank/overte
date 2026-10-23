// Controlled native-account boundary for the existing offscreen QML contracts.
// This fixture never supplies a product or device authentication result.
pragma Singleton
import QtQuick 2.12

QtObject {
    property string username: "Unknown user"
    property bool loggedIn: false
}
