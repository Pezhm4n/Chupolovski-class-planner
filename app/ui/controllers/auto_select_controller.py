import logging
from typing import Optional, Callable
from PyQt5 import QtCore, QtWidgets
from app.core.config import COURSES

class AutoSelectListController:
    """Decoupled Controller handling auto-select list behavior, drag-and-drop, key events and context menus."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.auto_select_list: Optional[QtWidgets.QListWidget] = None
        self.course_list_widget: Optional[QtWidgets.QListWidget] = None
        self.on_save_auto_select_list: Optional[Callable[[], None]] = None
        self.parent_window: Optional[QtWidgets.QWidget] = None

    def attach(self, 
               auto_select_list: Optional[QtWidgets.QListWidget] = None,
               course_list_widget: Optional[QtWidgets.QListWidget] = None,
               on_save_auto_select_list: Optional[Callable[[], None]] = None,
               parent_window: Optional[QtWidgets.QWidget] = None):
        """Attaches auto-select list widget without storing MainWindow instance."""
        self.auto_select_list = auto_select_list
        self.course_list_widget = course_list_widget
        self.on_save_auto_select_list = on_save_auto_select_list
        self.parent_window = parent_window
        if self.auto_select_list:
            self.setup_auto_select_list()

    def setup_auto_select_list(self):
        """Setup drag and drop and context menu functionality."""
        if not self.auto_select_list:
            return
        self.auto_select_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.auto_select_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.auto_select_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connect_signals()

    def connect_signals(self):
        """Connects signals for auto-select list."""
        if self.auto_select_list:
            try:
                self.auto_select_list.customContextMenuRequested.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.auto_select_list.customContextMenuRequested.connect(self.show_auto_list_context_menu)

            try:
                self.auto_select_list.model().rowsMoved.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.auto_select_list.model().rowsMoved.connect(self.on_auto_list_reordered)

    def on_auto_list_reordered(self, parent, start, end, destination, row):
        """Handle reordering of auto-select list items."""
        try:
            if not self.auto_select_list:
                return
            for i in range(self.auto_select_list.count()):
                item = self.auto_select_list.item(i)
                if item:
                    priority = i + 1
                    item.setData(QtCore.Qt.UserRole + 1, priority)
                    course_key = item.data(QtCore.Qt.UserRole)
                    if course_key in COURSES:
                        course = COURSES[course_key]
                        course_name = course.get('name', course_key)
                        item.setText(f"({priority}) {course_name}")
        except Exception as e:
            self.logger.error(f"Error reordering auto list: {e}")

    def on_add_to_auto(self):
        """Handle add to auto select list button click."""
        try:
            if not self.course_list_widget or not self.auto_select_list:
                return
            selected_items = self.course_list_widget.selectedItems()
            if not selected_items:
                if self.parent_window:
                    QtWidgets.QMessageBox.information(self.parent_window, 'انتخاب درس', 'لطفا ابتدا درسی را از لیست انتخاب کنید.')
                return

            for item in selected_items:
                exists = False
                for i in range(self.auto_select_list.count()):
                    if self.auto_select_list.item(i).data(QtCore.Qt.UserRole) == item.data(QtCore.Qt.UserRole):
                        exists = True
                        break

                if not exists:
                    course_key = item.data(QtCore.Qt.UserRole)
                    course = COURSES.get(course_key)
                    if course:
                        position = self.auto_select_list.count() + 1
                        new_item = QtWidgets.QListWidgetItem(f"({position}) {course['name']} - {course.get('instructor', 'نامشخص')}")
                        new_item.setData(QtCore.Qt.UserRole, course_key)
                        new_item.setData(QtCore.Qt.UserRole + 1, position)
                        self.auto_select_list.addItem(new_item)

            if self.on_save_auto_select_list:
                self.on_save_auto_select_list()
        except Exception as e:
            self.logger.error(f"Error adding to auto list: {e}")

    def on_remove_from_auto(self):
        """Handle remove from auto select list button click."""
        try:
            if not self.auto_select_list:
                return
            selected_items = self.auto_select_list.selectedItems()
            if not selected_items:
                if self.parent_window:
                    QtWidgets.QMessageBox.information(self.parent_window, 'حذف درس', 'لطفا ابتدا درسی را از لیست انتخاب کنید.')
                return

            for item in reversed(selected_items):
                row = self.auto_select_list.row(item)
                self.auto_select_list.takeItem(row)
        except Exception as e:
            self.logger.error(f"Error removing from auto select list: {e}")

    def show_auto_list_context_menu(self, position):
        """Show context menu for auto-select list items."""
        if not self.auto_select_list:
            return
        item = self.auto_select_list.itemAt(position)
        menu = QtWidgets.QMenu()

        delete_action = None
        if item:
            delete_action = menu.addAction("حذف از لیست")

        clear_all_action = None
        if self.auto_select_list.count() > 0:
            clear_all_action = menu.addAction("پاک کردن همه")

        action = menu.exec_(self.auto_select_list.mapToGlobal(position))

        if delete_action and action == delete_action:
            row = self.auto_select_list.row(item)
            self.auto_select_list.takeItem(row)
        elif clear_all_action and action == clear_all_action:
            reply = QtWidgets.QMessageBox.question(
                self.parent_window or self.auto_select_list, 'پاک کردن همه',
                f'آیا مطمئن هستید که می‌خواهید همه {self.auto_select_list.count()} درس را از لیست حذف کنید؟',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.auto_select_list.clear()

    def auto_select_list_key_press_event(self, event):
        """Handle key press events for auto-select list."""
        if not self.auto_select_list:
            return
        if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            selected_items = self.auto_select_list.selectedItems()
            if selected_items:
                for item in reversed(selected_items):
                    row = self.auto_select_list.row(item)
                    self.auto_select_list.takeItem(row)
                return

        if event.key() == QtCore.Qt.Key_A and event.modifiers() == QtCore.Qt.ControlModifier:
            self.auto_select_list.selectAll()
            return

        QtWidgets.QListWidget.keyPressEvent(self.auto_select_list, event)
