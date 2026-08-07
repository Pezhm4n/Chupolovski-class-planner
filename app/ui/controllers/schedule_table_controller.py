import logging
from typing import Optional, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets

class ScheduleTableController:
    """Decoupled Controller managing schedule table animations and silent clearing."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.schedule_table: Optional[QtWidgets.QTableWidget] = None
        self.parent_window: Optional[QtWidgets.QWidget] = None
        self._pulse_timers: Dict[str, QtCore.QTimer] = {}

    def attach(self, schedule_table: Optional[QtWidgets.QTableWidget] = None, parent_window: Optional[QtWidgets.QWidget] = None):
        """Attaches schedule table widget without holding MainWindow reference."""
        self.schedule_table = schedule_table
        self.parent_window = parent_window

    def start_pulse_animation(self, row: int, col: int):
        """Start pulse animation for a cell."""
        try:
            if not self.schedule_table:
                return
            item = self.schedule_table.item(row, col)
            if item:
                course_key = item.data(QtCore.Qt.UserRole)
                if course_key in self._pulse_timers:
                    return

                pulse_timer = QtCore.QTimer(self.parent_window or self.schedule_table)
                pulse_timer.setInterval(100)
                pulse_timer.timeout.connect(lambda: self.pulse_cell(item))
                self._pulse_timers[course_key] = pulse_timer
                pulse_timer.start()
        except Exception as e:
            self.logger.error(f"Failed to start pulse animation: {e}")

    def stop_pulse_animation(self, row: int, col: int):
        """Stop pulse animation for a cell."""
        try:
            if not self.schedule_table:
                return
            item = self.schedule_table.item(row, col)
            if item:
                course_key = item.data(QtCore.Qt.UserRole)
                if course_key in self._pulse_timers:
                    pulse_timer = self._pulse_timers[course_key]
                    pulse_timer.stop()
                    del self._pulse_timers[course_key]
        except Exception as e:
            self.logger.error(f"Failed to stop pulse animation: {e}")

    def pulse_cell(self, item: QtWidgets.QTableWidgetItem):
        """Pulsing animation step for a table item."""
        try:
            current_color = item.background().color()
            r, g, b, a = current_color.getRgb()
            if a < 255:
                a += 10
            else:
                a -= 10
            item.setBackground(QtGui.QColor(r, g, b, a))
        except Exception as e:
            self.logger.error(f"Error in pulse_cell: {e}")

    def clear_table_silent(self, placed_dict: Optional[dict] = None):
        """Clears all cells in schedule table silently."""
        try:
            if not self.schedule_table:
                return
            for row in range(self.schedule_table.rowCount()):
                for col in range(self.schedule_table.columnCount()):
                    self.schedule_table.setCellWidget(row, col, None)
            if placed_dict is not None:
                placed_dict.clear()
        except Exception as e:
            self.logger.error(f"Error clearing table silently: {e}")
