import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons

// The bar panel's content: every trophy style side by side with its four
// metals, preview buttons that fire real toasts through the running
// service, and the position and sound settings. Reads and writes the same
// ~/.config/omatrophy/config.json the service watches, through
// `omatrophy.py set`, so a choice applies to the next toast.
Column {
  id: root
  property color foreground: Commons.Color.popups.text

  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property var styles: [
    { id: "omarchy", name: "Omarchy", about: "Pixel grid, flat metal, inlay in your theme accent" },
    { id: "vector", name: "Faceted", about: "Clean vector metal with soft highlights" },
    { id: "painted", name: "Painted", about: "Rendered metal, closest to a console trophy" }
  ]
  readonly property var metals: ["bronze", "silver", "gold", "platinum"]

  property string iconSet: "omarchy"
  property string position: "top-center"
  property bool sound: true

  function set(key, value) {
    if (key === "icons") iconSet = value
    if (key === "position") position = value
    if (key === "sound") sound = value === "on"
    runner.exec(["python3", helperPath, "set", key, value])
  }

  function preview(kind) {
    runner.exec(["python3", helperPath, "test", kind])
  }

  spacing: Commons.Style.space(10)

  FileView {
    path: Quickshell.env("HOME") + "/.config/omatrophy/config.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (c.icons) root.iconSet = c.icons
      if (c.position) root.position = c.position
      if (typeof c.sound === "boolean") root.sound = c.sound
    }
  }

  Process { id: runner }

  // One trophy, drawn the way the cards draw it (the omarchy set's inlay
  // painted in the theme accent).
  component Thumb: Item {
    id: thumb
    property string style: "omarchy"
    property string metal: "bronze"
    width: 40
    height: 40
    Image {
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/" + thumb.style + "/trophy-" + thumb.metal + (thumb.style === "painted" ? ".png" : ".svg"))
      sourceSize: Qt.size(128, 128)
      smooth: thumb.style !== "omarchy"
      mipmap: thumb.style === "painted"
    }
    Item {
      anchors.fill: parent
      visible: thumb.style === "omarchy"
      Rectangle { id: paint; anchors.fill: parent; color: Commons.Color.accent; visible: false; layer.enabled: true }
      Image {
        id: inlay
        anchors.fill: parent
        source: thumb.style === "omarchy" ? Qt.resolvedUrl("assets/omarchy/trophy-accent.svg") : ""
        sourceSize: Qt.size(128, 128)
        visible: false
      }
      MultiEffect { anchors.fill: parent; source: paint; maskEnabled: true; maskSource: inlay }
    }
  }

  Text {
    text: "OmaTrophy"
    color: root.foreground
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.title
  }
  Text {
    width: parent.width
    wrapMode: Text.Wrap
    text: "Steam achievements as toasts over your games. Pick a trophy style, then preview it."
    color: root.foreground
    opacity: 0.7
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
  }

  PanelSectionHeader { text: "TROPHY STYLE"; foreground: root.foreground }

  Repeater {
    model: root.styles
    // Rows hold thumbnails, so they are plain surfaces styled like the
    // kit's selectable rows (see the HDR panel) rather than Buttons.
    delegate: Rectangle {
      id: styleRow
      required property var modelData
      readonly property bool chosen: root.iconSet === modelData.id
      width: root.width
      height: styleBody.implicitHeight + Commons.Style.space(16)
      radius: Commons.Style.cornerRadius
      color: chosen ? Commons.Style.selectedFill : (pick.containsMouse ? Commons.Style.hoverFill : "transparent")
      border.color: chosen ? Commons.Color.accent : "transparent"
      border.width: 1
      Accessible.role: Accessible.Button
      Accessible.name: modelData.name + " trophies" + (chosen ? ", in use" : "")

      MouseArea {
        id: pick
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.set("icons", styleRow.modelData.id)
      }

      Column {
        id: styleBody
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: Commons.Style.space(10)
        spacing: Commons.Style.space(6)

        Row {
          spacing: Commons.Style.space(8)
          Text {
            text: styleRow.modelData.name
            color: root.foreground
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.subtitle
            font.bold: true
          }
          Text {
            visible: styleRow.chosen
            text: "in use"
            color: Commons.Color.accent
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
          }
        }
        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: styleRow.modelData.about
          color: root.foreground
          opacity: 0.65
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
        Row {
          spacing: Commons.Style.space(10)
          Repeater {
            model: root.metals
            Thumb {
              required property string modelData
              style: styleRow.modelData.id
              metal: modelData
            }
          }
        }
      }
    }
  }

  PanelSectionHeader { text: "PREVIEW"; foreground: root.foreground }
  Row {
    spacing: Commons.Style.space(6)
    Repeater {
      model: root.metals
      Button {
        required property string modelData
        text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
        bordered: true
        foreground: root.foreground
        tooltipText: "Show a " + modelData + " toast now"
        onClicked: root.preview(modelData)
      }
    }
  }

  PanelSectionHeader { text: "POSITION"; foreground: root.foreground }
  ButtonGroup {
    options: [
      { value: "top-left", label: "Top left" },
      { value: "top-center", label: "Top center" },
      { value: "top-right", label: "Top right" }
    ]
    value: root.position
    foreground: root.foreground
    onChanged: value => root.set("position", value)
  }

  PanelSectionHeader { text: "SOUND"; foreground: root.foreground }
  ButtonGroup {
    options: [{ value: "on", label: "Chime" }, { value: "off", label: "Silent" }]
    value: root.sound ? "on" : "off"
    foreground: root.foreground
    onChanged: value => root.set("sound", value)
  }
}
