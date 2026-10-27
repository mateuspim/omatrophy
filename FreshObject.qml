import QtQuick
import Quickshell.Io

// Builds a sibling QML file from its current text, so edits to the cards,
// the panel content and the tracker show on the next open without restarting
// the shell (ADR 5, ADR 10).
//
// Omarchy's Quickshell (the OmarchyLoadPatch pragma) serves plugin files as
// qs:// URLs from a cache filled on first load and ignores a ?v= query, so a
// Loader keeps the copy from shell start. A file:// URL does reload, but
// makes Quickshell watch the file and reload the whole shell when it changes,
// which can upset a running game (ADR 8). Compiling the text read fresh does
// neither.
Item {
  id: root

  // The object built by load(); null until then and after clear().
  property var item: null

  FileView {
    id: source
    blockLoading: true
    printErrors: false
  }

  // Builds `name` (a .qml file in this folder) under this item, replacing the
  // previous one. Returns the object, or null when the file doesn't compile.
  function load(name) {
    clear()
    var url = Qt.resolvedUrl(name)
    source.path = decodeURIComponent(String(url).replace(/^(qs|file):\/\//, ""))
    source.reload()
    source.waitForJob()
    // A sibling URL that is never a file, so the engine compiles this text
    // instead of reusing a cached type for the real one. Relative paths in
    // the file resolve as before; errors name it `<name>.live.qml`.
    var live = String(url).replace(/\.qml$/, ".live.qml")
    try {
      root.item = Qt.createQmlObject(source.text(), root, live)
    } catch (e) {
      console.warn("omatrophy: " + name + " failed to build, fix it and reopen:", JSON.stringify(e.qmlErrors || String(e)))
    }
    return root.item
  }

  function clear() {
    if (root.item) root.item.destroy()
    root.item = null
  }
}
