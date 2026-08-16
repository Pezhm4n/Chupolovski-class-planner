import logging
from typing import Callable, Optional, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets
from app.core.config import COURSES, COLOR_MAP

class CourseSearchController:
    """Decoupled Controller handling course search, filtering, Persian text normalization and major dropdown."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.search_box: Optional[QtWidgets.QLineEdit] = None
        self.search_clear_button: Optional[QtWidgets.QToolButton] = None
        self.major_combo: Optional[QtWidgets.QComboBox] = None
        self.course_list_widget: Optional[QtWidgets.QListWidget] = None
        self.get_current_major_filter: Optional[Callable[[], str]] = None
        self.on_refresh_course_list: Optional[Callable[[str], None]] = None
        self.db_instance = None
        self.parent_window: Optional[QtWidgets.QWidget] = None

    def attach(self,
               search_box: Optional[QtWidgets.QLineEdit] = None,
               search_clear_button: Optional[QtWidgets.QToolButton] = None,
               major_combo: Optional[QtWidgets.QComboBox] = None,
               course_list_widget: Optional[QtWidgets.QListWidget] = None,
               db_instance=None,
               get_current_major_filter: Optional[Callable[[], str]] = None,
               on_refresh_course_list: Optional[Callable[[str], None]] = None,
               parent_window: Optional[QtWidgets.QWidget] = None,
               wire_signals: bool = True):
        """Attaches specific UI widgets and callbacks without storing MainWindow instance.

        Args:
            wire_signals: When False, signal wiring is skipped — use this when the
                host window already connects the widget signals to the delegation
                methods (avoids double-firing handlers).
        """
        self.search_box = search_box
        self.search_clear_button = search_clear_button
        self.major_combo = major_combo
        self.course_list_widget = course_list_widget
        self.db_instance = db_instance
        self.get_current_major_filter = get_current_major_filter
        self.on_refresh_course_list = on_refresh_course_list
        self.parent_window = parent_window
        if wire_signals:
            self.connect_signals()

    def connect_signals(self):
        """Connects signals for search and major widgets."""
        if self.search_box:
            try:
                self.search_box.textChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.search_box.textChanged.connect(self.on_search_text_changed)

        if self.search_clear_button:
            try:
                self.search_clear_button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.search_clear_button.clicked.connect(self.clear_search)

        if self.major_combo:
            try:
                self.major_combo.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.major_combo.currentIndexChanged.connect(self.on_major_selection_changed)

    def normalize_persian_text(self, text: str) -> str:
        """Normalizes Persian characters for search operations."""
        if not text:
            return ""
        replacements = {
            'ي': 'ی', 'ك': 'ک', 'ة': 'ه', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا',
            '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5',
            '۶': '6', '۷': '7', '۸': '8', '۹': '9', '۰': '0'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text.strip().lower()

    def on_search_text_changed(self, text: str):
        """Handles user typing in search input."""
        try:
            self.toggle_search_clear_button(text)
            self.populate_course_list(text)
        except Exception as e:
            self.logger.error(f"Error in on_search_text_changed: {e}")

    def toggle_search_clear_button(self, text: str):
        """Shows or hides clear button based on search length."""
        if self.search_clear_button:
            if text:
                self.search_clear_button.show()
            else:
                self.search_clear_button.hide()

    def clear_search(self):
        """Clears search box and resets course list."""
        if self.search_box:
            self.search_box.clear()
        if self.search_clear_button:
            self.search_clear_button.hide()
        self.populate_course_list(None)

    def populate_major_dropdown(self):
        """Populates major dropdown widget."""
        if not self.major_combo:
            return
        try:
            from app.core.translator import translator
            self.major_combo.blockSignals(True)
            self.major_combo.clear()
            self.major_combo.addItem(translator.t("ui.settings.all_majors"), "ALL")

            majors = set()
            for course in COURSES.values():
                major = course.get('major')
                if major:
                    majors.add(major)

            for major in sorted(majors):
                self.major_combo.addItem(major, major)

            self.major_combo.blockSignals(False)
        except Exception as e:
            self.logger.error(f"Error populating major dropdown: {e}")
            if self.major_combo:
                self.major_combo.blockSignals(False)

    def on_major_selection_changed(self, index: int):
        """Handles selection of a major from the dropdown."""
        try:
            if not self.major_combo:
                return
            selected_major = self.major_combo.itemData(index)
            if selected_major == "ALL":
                self.populate_course_list(None)
            elif self.on_refresh_course_list:
                self.on_refresh_course_list(selected_major)
        except Exception as e:
            self.logger.error(f"Error in on_major_selection_changed: {e}")

    def populate_course_list(self, filter_items=None):
        """Populate list widget based on search text or pre-filtered dict."""
        try:
            from app.ui.widgets import CourseListWidget

            # NOTE: compare against None explicitly — an EMPTY QListWidget is
            # falsy (it implements __len__), which used to abort population
            # right after startup and leave the list permanently blank.
            if self.course_list_widget is None:
                self.logger.warning("populate_course_list skipped: no course list widget attached")
                return

            self.course_list_widget.clear()

            if isinstance(filter_items, dict):
                courses_to_show = filter_items
                filter_text = ""
            else:
                courses_to_show = COURSES
                cur_filter = self.get_current_major_filter() if self.get_current_major_filter else None
                if cur_filter and cur_filter != "دروس اضافه‌شده توسط کاربر":
                    courses_to_show = {
                        key: course for key, course in COURSES.items()
                        if course.get('major') == cur_filter
                    }
                elif cur_filter == "دروس اضافه‌شده توسط کاربر":
                    courses_to_show = {
                        key: course for key, course in COURSES.items()
                        if course.get('major') == "دروس اضافه‌شده توسط کاربر"
                    }
                filter_text = str(filter_items).strip().lower() if isinstance(filter_items, str) else ""

            if filter_text:
                courses_to_show = {
                    key: course for key, course in courses_to_show.items()
                    if (
                        filter_text in (course.get('name') or course.get('course_name') or '').lower() or
                        filter_text in str(course.get('code') or course.get('course_code') or '').lower() or
                        filter_text in (course.get('instructor') or '').lower() or
                        filter_text in (course.get('department') or '').lower() or
                        filter_text in (course.get('faculty') or '').lower()
                    )
                }

            used = 0
            sorted_courses = sorted(courses_to_show.items(), key=lambda x: x[1].get('name', ''))
            total_matching = len(sorted_courses)

            # Virtualization cap: rendering ~2000 heavyweight item widgets
            # freezes (and can natively crash) the GUI. Show the first page
            # and guide the user to search/filter for the rest (web parity —
            # the web list is virtualized too).
            MAX_VISIBLE = 400
            visible_courses = sorted_courses[:MAX_VISIBLE]

            for key, course in visible_courses:
                try:
                    if not isinstance(course, dict):
                        continue

                    required_fields = ['code', 'name', 'credits', 'instructor', 'schedule']
                    if any(field not in course for field in required_fields):
                        continue

                    item = QtWidgets.QListWidgetItem()
                    item.setData(QtCore.Qt.UserRole, key)

                    color = COLOR_MAP[used % len(COLOR_MAP)]
                    item.setBackground(QtGui.QBrush(color))

                    # NOTE: no item.setToolTip here — the custom floating info
                    # panel (CourseListWidget hover) already shows full course
                    # details; a native tooltip would duplicate it.

                    self.course_list_widget.addItem(item)
                    course_widget = CourseListWidget(key, course, self.course_list_widget, self.parent_window)
                    course_widget.setProperty('colorIndex', used % len(COLOR_MAP))
                    item.setSizeHint(course_widget.sizeHint())
                    self.course_list_widget.setItemWidget(item, course_widget)
                    used += 1

                except Exception as e:
                    self.logger.error(f"Error creating course item for {key}: {e}")
                    continue

            # Footer hint when the list was capped
            hidden = total_matching - len(visible_courses)
            if hidden > 0:
                footer = QtWidgets.QListWidgetItem(
                    f"🔎 … {hidden} درس دیگر یافت شد — برای یافتن سریع‌تر، جستجو کنید یا رشته را انتخاب کنید"
                )
                footer.setFlags(QtCore.Qt.NoItemFlags)  # not clickable
                self.course_list_widget.addItem(footer)

            self.logger.info(
                f"Populated course list with {used} courses "
                f"(matched {total_matching}, capped at {MAX_VISIBLE})"
            )
        except Exception as e:
            self.logger.error(f"Error in populate_course_list: {e}")
