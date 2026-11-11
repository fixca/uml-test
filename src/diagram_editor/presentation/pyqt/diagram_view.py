"""QGraphicsScene adapter: domain IDs map to individual selectable items.

Qt items are projections, never the persisted document itself.
"""
from __future__ import annotations
import math
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPen, QPainterPath, QPolygonF, QFont, QPainter
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsPathItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsPolygonItem,
    QGraphicsItem, QMenu)
from diagram_editor.core.domain.models import DiagramDocument, Node, Edge

INK = QColor("#e4e9f5")
MUTED = QColor("#aab8d0")
STROKE = QColor("#7687a4")
ACCENT = QColor("#7da9ff")
NODE_FILL = QColor("#1e2c46")
CANVAS = QColor("#111a2c")


def rect_point_toward(rect: QRectF, target: QPointF) -> QPointF:
    center = rect.center()
    dx, dy = target.x() - center.x(), target.y() - center.y()
    hw, hh = rect.width()/2, rect.height()/2
    ratio = max(abs(dx)/max(1,hw), abs(dy)/max(1,hh), 0.00001)
    return QPointF(center.x() + dx/ratio, center.y() + dy/ratio)


class DiagramNodeItem(QGraphicsRectItem):
    def __init__(self, node: Node, owner: "DiagramView"):
        super().__init__()
        self.object_id = node.id
        self.owner = owner
        self.node = node
        self._origin = QPointF(node.x, node.y)
        self.title = QGraphicsTextItem(self)
        self.title.setDefaultTextColor(INK)
        self.title.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        self.body = QGraphicsTextItem(self)
        self.body.setDefaultTextColor(MUTED)
        self.body.setFont(QFont("Monospace", 9))
        self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.apply_model(node)

    def apply_model(self, node: Node):
        self.node = node
        self.object_id = node.id
        self.setRect(0, 0, node.width, node.height)
        self.title.setPlainText(node.label)
        self.title.setPos(11, 5)
        self.body.setPlainText("\n".join(node.members))
        self.body.setPos(8, 32)
        self.setPos(node.x, node.y)
        self.setPen(QPen(STROKE, 1.4))
        self.setBrush(QBrush(NODE_FILL))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, self.owner.editable)

    def itemChange(self, change, value):
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
                and self.scene() and not self.owner._updating):
            self.owner.refresh_edges()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._origin = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.owner.editable and self.pos() != self._origin:
            self.owner.commit_visible_moves()


class DiagramEdgeItem(QGraphicsPathItem):
    def __init__(self, edge: Edge):
        super().__init__()
        self.object_id = edge.id
        self.edge = edge
        self.setZValue(2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.label = QGraphicsTextItem(self)
        self.label.setDefaultTextColor(MUTED)
        self.label.setFont(QFont("Sans Serif", 9))
        self.arrow = QGraphicsPolygonItem(self)
        self.arrow.setPen(QPen(STROKE, 1))
        self.arrow.setBrush(QBrush(STROKE))

    def update_geometry(self, edge: Edge, doc: DiagramDocument,
                        nodes: dict[str, DiagramNodeItem]):
        self.edge = edge
        a, b = nodes.get(edge.source), nodes.get(edge.target)
        if not a or not b:
            self.hide()
            return
        self.show()
        style = Qt.PenStyle.DashLine if ".." in edge.relation or "-->>" in edge.relation or edge.relation.startswith("--") and doc.diagram_type == "sequence" else Qt.PenStyle.SolidLine
        self.setPen(QPen(ACCENT if doc.diagram_type == "sequence" else STROKE, 2, style))
        if doc.diagram_type == "sequence":
            y = 142 + edge.order * 66
            start = QPointF(a.pos().x() + a.rect().width()/2, y)
            end = QPointF(b.pos().x() + b.rect().width()/2, y)
            if edge.source == edge.target:
                path = QPainterPath(start)
                path.lineTo(start.x()+65, y)
                path.lineTo(start.x()+65, y+30)
                path.lineTo(start.x(), y+30)
                end = QPointF(start.x(), y+30)
            else:
                path = QPainterPath(start)
                path.lineTo(end)
        else:
            start = rect_point_toward(a.sceneBoundingRect(), b.sceneBoundingRect().center())
            end = rect_point_toward(b.sceneBoundingRect(), a.sceneBoundingRect().center())
            path = QPainterPath(start)
            path.lineTo(end)
        self.setPath(path)
        dx, dy = end.x()-start.x(), end.y()-start.y()
        distance = max(1, math.hypot(dx, dy))
        ux, uy = dx/distance, dy/distance
        size = 11
        self.arrow.setPolygon(QPolygonF([end, QPointF(end.x()-ux*size-uy*6, end.y()-uy*size+ux*6),
                                          QPointF(end.x()-ux*size+uy*6, end.y()-uy*size-ux*6)]))
        self.arrow.setVisible(edge.relation not in ("--", ".."))
        label = edge.label
        self.label.setPlainText(label)
        if edge.source == edge.target and doc.diagram_type == "sequence":
            mid = QPointF(start.x()+37, start.y()-21)
        else:
            mid = QPointF((start.x()+end.x())/2, (start.y()+end.y())/2)
        self.label.setPos(mid.x() - self.label.boundingRect().width()/2,
                          mid.y() - self.label.boundingRect().height() - 4)


class DiagramView(QGraphicsView):
    nodesMoved = pyqtSignal(object)
    selectionUpdated = pyqtSignal()
    requestAdd = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas_scene = QGraphicsScene(self)
        self.canvas_scene.setBackgroundBrush(QBrush(CANVAS))
        self.setScene(self.canvas_scene)
        self.canvas_scene.selectionChanged.connect(self.selectionUpdated)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setBackgroundBrush(QBrush(CANVAS))
        self.editable = True
        self._updating = False
        self._nodes: dict[str, DiagramNodeItem] = {}
        self._edges: dict[str, DiagramEdgeItem] = {}
        self._lifelines: list[QGraphicsLineItem] = []
        self._decorations: list[QGraphicsItem] = []
        self.current_doc = DiagramDocument("class")

    def commit_visible_moves(self):
        if not self.editable or self._updating:
            return
        old = {node.id: node for node in self.current_doc.nodes}
        changes = [(oid, item.pos().x(), item.pos().y())
                   for oid, item in self._nodes.items()
                   if oid in old and (item.pos().x(), item.pos().y()) != (old[oid].x, old[oid].y)]
        if changes:
            self.nodesMoved.emit(changes)

    def selected_ids(self) -> set[str]:
        return {item.object_id for item in self.canvas_scene.selectedItems() if hasattr(item, "object_id")}

    def cancel_drag(self):
        self._updating = True
        try:
            by_id = {n.id: n for n in self.current_doc.nodes}
            for key, item in self._nodes.items():
                if key in by_id:
                    item.setPos(by_id[key].x, by_id[key].y)
        finally:
            self._updating = False
        self.refresh_edges()

    def set_editable(self, enabled: bool):
        if not enabled:
            self.cancel_drag()
        self.editable = enabled
        for item in self._nodes.values():
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled)

    def sync_document(self, doc: DiagramDocument):
        self._updating = True
        try:
            chosen = self.selected_ids()
            self.current_doc = doc
            wanted = {n.id for n in doc.nodes}
            for oid in list(self._nodes):
                if oid not in wanted:
                    self.canvas_scene.removeItem(self._nodes.pop(oid))
            for node in doc.nodes:
                if node.id not in self._nodes:
                    item = DiagramNodeItem(node, self)
                    self.canvas_scene.addItem(item)
                    self._nodes[node.id] = item
                else:
                    self._nodes[node.id].apply_model(node)
                self._nodes[node.id].setSelected(node.id in chosen)
            edge_ids = {e.id for e in doc.edges}
            for oid in list(self._edges):
                if oid not in edge_ids:
                    self.canvas_scene.removeItem(self._edges.pop(oid))
            for edge in doc.edges:
                if edge.id not in self._edges:
                    item = DiagramEdgeItem(edge)
                    self.canvas_scene.addItem(item)
                    self._edges[edge.id] = item
                self._edges[edge.id].setSelected(edge.id in chosen)
            self.refresh_edges()
            self._refresh_lifelines()
            self._refresh_decorations()
            bounds = self.canvas_scene.itemsBoundingRect().adjusted(-55,-55,55,65)
            self.canvas_scene.setSceneRect(bounds if not bounds.isEmpty() else QRectF(0, 0, 800, 600))
        finally:
            self._updating = False

    def refresh_edges(self):
        keys = {item.node.key: item for item in self._nodes.values()}
        for edge in self.current_doc.edges:
            item = self._edges.get(edge.id)
            if item:
                item.update_geometry(edge, self.current_doc, keys)
        if self.current_doc.diagram_type == "sequence":
            self._refresh_lifelines()
            self._refresh_decorations()

    def _refresh_lifelines(self):
        for item in self._lifelines:
            self.canvas_scene.removeItem(item)
        self._lifelines.clear()
        if self.current_doc.diagram_type != "sequence":
            return
        bottom = 175 + max(1,len(self.current_doc.edges))*66
        for node in self.current_doc.nodes:
            it = self._nodes.get(node.id)
            if it is None: continue
            x = it.pos().x() + it.rect().width()/2
            line = QGraphicsLineItem(x, it.pos().y()+it.rect().height(), x, bottom)
            line.setPen(QPen(QColor("#516583"), 1.5, Qt.PenStyle.DashLine))
            line.setZValue(-1)
            self.canvas_scene.addItem(line)
            self._lifelines.append(line)

    def _refresh_decorations(self):
        for item in self._decorations:
            self.canvas_scene.removeItem(item)
        self._decorations.clear()
        doc = self.current_doc
        if doc.diagram_type != "sequence" or not doc.nodes:
            return
        node_pos = {node.key: self._nodes[node.id].pos().x() + node.width / 2
                    for node in doc.nodes if node.id in self._nodes}
        left = min(node_pos.values()) - 105
        right = max(node_pos.values()) + 105
        stack = []
        def add(item):
            self.canvas_scene.addItem(item)
            self._decorations.append(item)
            return item
        def line_y(order):
            return 142 + order * 66
        for record in doc.decorations:
            kind = record.get("kind")
            order = record.get("order", 0)
            if kind == "block_start":
                stack.append(record)
            elif kind == "block_end" and stack:
                start = stack.pop()
                y0 = line_y(start.get("order", 0)) - 40
                y1 = line_y(order) + 43
                frame = add(QGraphicsRectItem(left, y0, right-left, max(65, y1-y0)))
                frame.setZValue(-3)
                frame.setPen(QPen(QColor("#6880a3"), 1, Qt.PenStyle.DashLine))
                frame.setBrush(QBrush(QColor(110, 135, 190, 24)))
                title = add(QGraphicsTextItem(f"{start.get('block','GROUP').upper()}  {start.get('text','')}"))
                title.setDefaultTextColor(QColor("#a5badb"))
                title.setPos(left + 7, y0 + 3)
                title.setZValue(-2)
            elif kind == "block_option":
                label = add(QGraphicsTextItem(record.get("text", "")))
                label.setDefaultTextColor(MUTED)
                label.setPos(left + 10, line_y(order)-31)
                label.setZValue(-1)
            elif kind == "note":
                targets = record.get("targets", [])
                if not targets:
                    continue
                xs = [node_pos[x] for x in targets if x in node_pos]
                if not xs:
                    continue
                x = sum(xs)/len(xs)
                if record.get("position", "").lower() == "right of": x += 38
                if record.get("position", "").lower() == "left of": x -= 185
                y = line_y(order) - 28
                body = record.get("text", "")
                width = max(100, min(240, 14 * len(body)))
                note = add(QGraphicsRectItem(x, y, width, 45))
                note.setZValue(3)
                note.setPen(QPen(QColor("#b7a56a"), 1))
                note.setBrush(QBrush(QColor("#3d3b2b")))
                label = add(QGraphicsTextItem(body))
                label.setTextWidth(width-12)
                label.setDefaultTextColor(QColor("#f2deb1"))
                label.setPos(x+6, y+2)
                label.setZValue(4)

    def zoom_in(self): self.scale(1.2, 1.2)
    def zoom_out(self): self.scale(1/1.2, 1/1.2)

    def fit_all(self):
        rect = self.canvas_scene.itemsBoundingRect().adjusted(-35,-35,35,35)
        if not rect.isEmpty():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            (self.zoom_in if event.angleDelta().y() > 0 else self.zoom_out)()
            event.accept()
        else:
            super().wheelEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        add = menu.addAction("노드/참가자 추가")
        add.setEnabled(self.editable)
        menu.addSeparator()
        fit = menu.addAction("전체 화면 맞춤")
        chosen = menu.exec(event.globalPos())
        if chosen == add: self.requestAdd.emit()
        elif chosen == fit: self.fit_all()
