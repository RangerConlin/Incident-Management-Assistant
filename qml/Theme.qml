// qml/Theme.qml
pragma Singleton
import QtQuick 2.15

QtObject {
    // This singleton simply proxies the map from themeBridge for ergonomic access
    // Usage: Theme.tokens.bg_window, Theme.tokens.accent, etc.
    property var tokens: ({})
}

