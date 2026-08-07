import datetime
import logging
from PyQt5 import QtWidgets

class MenuBuilder:
    """Pure UI builder for creating application menus and action hierarchies."""

    @staticmethod
    def build_menu_bar(window: QtWidgets.QMainWindow, logger: logging.Logger):
        """Constructs menu bar structure and returns created actions/menus dictionary for window to wire."""
        actions = {}
        menus = {}
        
        try:
            menubar = window.menubar if hasattr(window, 'menubar') else window.menuBar()
            menus['menubar'] = menubar

            # 1. Existing UI File Menu Bindings
            if hasattr(window, 'menu_data'):
                menus['data_menu'] = window.menu_data
            
            # 2. Student Profile Action
            if hasattr(window, 'action_student_profile'):
                actions['student_profile'] = window.action_student_profile
            else:
                act_profile = QtWidgets.QAction('پروفایل دانشجو', window)
                menubar.addAction(act_profile)
                actions['student_profile'] = act_profile

            # 3. Backup History Menu
            history_menu = menubar.addMenu('نسخه‌های پشتیبان')
            current_date = datetime.datetime.now().strftime('%Y/%m/%d')
            history_menu.setTitle(f'نسخه‌های پشتیبان ({current_date})')
            menus['history_menu'] = history_menu

            # 4. Online Services Menu
            cloud_menu = menubar.addMenu("🌐 خدمات آنلاین")
            menus['cloud_menu'] = cloud_menu

            act_cloud_auth = QtWidgets.QAction("🔑 ورود / ایجاد حساب کاربری...", window)
            cloud_menu.addAction(act_cloud_auth)
            actions['cloud_auth'] = act_cloud_auth

            act_cloud_sync = QtWidgets.QAction("☁️ پشتیبان‌گیری و بازیابی آنلاین...", window)
            cloud_menu.addAction(act_cloud_sync)
            actions['cloud_sync'] = act_cloud_sync

            act_prof_review = QtWidgets.QAction("👨‍🏫 نظرسنجی و مقایسه اساتید...", window)
            cloud_menu.addAction(act_prof_review)
            actions['prof_review'] = act_prof_review

            # 5. Academic Services Menu
            acad_menu = menubar.addMenu("🎓 خدمات تحصیلی")
            menus['acad_menu'] = acad_menu

            act_academic = QtWidgets.QAction("🎓 شناسنامه، کارنامه و پیشرفت تحصیلی (گزارش ۲۷۲)...", window)
            acad_menu.addAction(act_academic)
            actions['academic'] = act_academic

            # 6. Settings Menu
            sett_menu = menubar.addMenu("⚙️ تنظیمات")
            menus['sett_menu'] = sett_menu

            act_settings = QtWidgets.QAction("⚙️ تنظیمات برنامه...", window)
            sett_menu.addAction(act_settings)
            actions['settings'] = act_settings

        except Exception as e:
            logger.error(f"Error in MenuBuilder: {e}")

        return menus, actions
