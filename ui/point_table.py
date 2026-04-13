"""Point pair table with inline label and lock editing."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.project import ControlPoint
from ui.theme import color_for_residual


class PointTable(QTableWidget):
    """Tabular editing surface for control point pairs."""

    point_selected = Signal(object)
    label_changed = Signal(int, str)
    lock_changed = Signal(int, bool)
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 8, parent)
        self._updating = False
        self.setHorizontalHeaderLabels(
            ["ID", "Label", "Image X", "Image Y", "Ref X", "Ref Y", "Residual", "Lock"]
        )
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
        self.setAlternatingRowColors(True)
        self.setMouseTracking(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemChanged.connect(self._handle_item_changed)

    def set_points(
        self,
        points: Iterable[ControlPoint],
        selected_point_id: int | None = None,
    ) -> None:
        self._updating = True
        self.blockSignals(True)
        self.setRowCount(0)

        for row, point in enumerate(points):
            self.insertRow(row)
            id_item = QTableWidgetItem(str(point.id))
            id_item.setData(Qt.UserRole, point.id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 0, id_item)

            label_item = QTableWidgetItem(point.label)
            self.setItem(row, 1, label_item)

            self.setItem(
                row, 2, _readonly_number_item(point.image_xy[0] if point.image_xy else None)
            )
            self.setItem(
                row, 3, _readonly_number_item(point.image_xy[1] if point.image_xy else None)
            )
            self.setItem(
                row,
                4,
                _readonly_number_item(point.reference_xy[0] if point.reference_xy else None),
            )
            self.setItem(
                row,
                5,
                _readonly_number_item(point.reference_xy[1] if point.reference_xy else None),
            )
            residual_item = _readonly_number_item(point.residual)
            residual_item.setForeground(QBrush(QColor(color_for_residual(point.residual))))
            self.setItem(row, 6, residual_item)

            lock_item = QTableWidgetItem("")
            lock_item.setData(Qt.UserRole, point.id)
            lock_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            lock_item.setCheckState(Qt.Checked if point.locked else Qt.Unchecked)
            lock_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 7, lock_item)

            if point.id == selected_point_id:
                self.selectRow(row)
                self.setCurrentCell(row, 0)

        self.blockSignals(False)
        self._updating = False

    def current_point_id(self) -> int | None:
        current = self.currentRow()
        if current < 0:
            return None
        item = self.item(current, 0)
        return int(item.data(Qt.UserRole)) if item is not None else None

    def select_point(self, point_id: int | None) -> None:
        if point_id is None:
            self.clearSelection()
            return
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None and int(item.data(Qt.UserRole)) == point_id:
                self.selectRow(row)
                self.setCurrentCell(row, 0)
                return

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace}:
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _emit_selection(self) -> None:
        self.point_selected.emit(self.current_point_id())

    def _handle_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        id_item = self.item(item.row(), 0)
        if id_item is None:
            return
        point_id = id_item.data(Qt.UserRole)
        if item.column() == 1:
            self.label_changed.emit(int(point_id), item.text().strip())
        elif item.column() == 7:
            self.lock_changed.emit(int(point_id), item.checkState() == Qt.Checked)


def _readonly_number_item(value: float | None) -> QTableWidgetItem:
    text = "" if value is None else f"{value:.3f}"
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item
