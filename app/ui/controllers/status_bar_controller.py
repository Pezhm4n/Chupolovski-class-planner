import logging
from typing import Optional, Callable, Dict, Any
from PyQt5 import QtWidgets
from app.core.config import COURSES

class StatusBarController:
    """Decoupled Controller managing status bar updates and stats panel labels."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.status_bar: Optional[QtWidgets.QStatusBar] = None
        self.stats_widget: Optional[QtWidgets.QLabel] = None
        self.get_placed_dict: Optional[Callable[[], dict]] = None
        self.get_user_data_dict: Optional[Callable[[], dict]] = None

    def attach(self, 
               status_bar: Optional[QtWidgets.QStatusBar] = None, 
               stats_widget: Optional[QtWidgets.QLabel] = None,
               get_placed_dict: Optional[Callable[[], dict]] = None,
               get_user_data_dict: Optional[Callable[[], dict]] = None):
        """Attaches status bar and stats label without storing MainWindow instance."""
        self.status_bar = status_bar
        self.stats_widget = stats_widget
        self.get_placed_dict = get_placed_dict
        self.get_user_data_dict = get_user_data_dict

    def update_status(self):
        """Update status bar label text."""
        try:
            placed = self.get_placed_dict() if self.get_placed_dict else {}
            if placed:
                count = len(placed)
                total_units = 0
                for info in placed.values():
                    ckey = info.get('course')
                    if ckey and ckey in COURSES:
                        total_units += COURSES[ckey].get('units', 3)
                status_text = f"تعداد دروس: {count} | مجموع واحدها: {total_units}"
            else:
                status_text = "آماده برای برنامه‌ریزی"

            if self.status_bar:
                self.status_bar.showMessage(status_text)
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")

    def update_stats_panel(self):
        """Update the statistics panel label."""
        try:
            if not self.stats_widget:
                return

            placed = self.get_placed_dict() if self.get_placed_dict else {}
            user_data = self.get_user_data_dict() if self.get_user_data_dict else None

            if placed:
                keys = []
                for info in placed.values():
                    if info.get('type') == 'dual':
                        keys.extend(info.get('courses', []))
                    else:
                        keys.append(info.get('course'))

                seen = set()
                unique_keys = [k for k in keys if not (k in seen or seen.add(k))]

                if user_data is not None:
                    user_data['current_schedule'] = unique_keys

                total_units = 0
                for k in unique_keys:
                    if k in COURSES:
                        total_units += COURSES[k].get('units', 3)

                days_count = len(set(info.get('day') for info in placed.values() if 'day' in info))
                text = f"📊 تعداد دروس: {len(unique_keys)} | 🎓 واحدها: {total_units} | 📅 روزهای حضور: {days_count}"
                self.stats_widget.setText(text)
            else:
                self.stats_widget.setText("📊 برنامه‌ای ثبت نشده است")

        except Exception as e:
            self.logger.error(f"Error updating stats panel: {e}")
