# -*- coding: utf-8 -*-
"""
Golestoon Menu Builder.
Constructs a unified, clean, and modern menu bar aligned with Golestoon Web routes.
All labels are translated via `translator.t("menu.*")` for full fa/en support.
"""

import datetime
import logging
from PyQt5 import QtWidgets, QtCore

from app.core.translator import translator


class MenuBuilder:
    """Pure UI builder for creating application menus and action hierarchies."""

    @staticmethod
    def build_menu_bar(window: QtWidgets.QMainWindow, logger: logging.Logger):
        """Constructs menu bar structure and returns created actions/menus dictionary for window to wire."""
        actions = {}
        menus = {}
        t = translator.t

        try:
            menubar = window.menubar if hasattr(window, 'menubar') else window.menuBar()
            menubar.clear()
            menus['menubar'] = menubar

            # -------------------------------------------------------------
            # 1. 🌐 داده‌ها و همگام‌سازی (Data & Cloud Sync)
            # -------------------------------------------------------------
            data_menu = menubar.addMenu(t("menu.data_menu"))
            menus['data_menu'] = data_menu

            act_cloud_auth = QtWidgets.QAction(t("menu.cloud_auth"), window)
            data_menu.addAction(act_cloud_auth)
            actions['cloud_auth'] = act_cloud_auth

            data_menu.addSeparator()

            act_fetch_golestan = QtWidgets.QAction(t("menu.fetch_golestan"), window)
            data_menu.addAction(act_fetch_golestan)
            actions['fetch_golestan'] = act_fetch_golestan

            act_reset_creds = QtWidgets.QAction(t("menu.reset_creds"), window)
            data_menu.addAction(act_reset_creds)
            actions['reset_creds'] = act_reset_creds

            # -------------------------------------------------------------
            # 2. 📊 کارنامه گلستان (Direct Click Action)
            # -------------------------------------------------------------
            act_student_dashboard = QtWidgets.QAction(t("menu.academic_menu"), window)
            menubar.addAction(act_student_dashboard)
            actions['student_dashboard'] = act_student_dashboard
            actions['student_profile'] = act_student_dashboard
            actions['academic'] = act_student_dashboard

            # -------------------------------------------------------------
            # 3. 👨‍🏫 نظرسنجی اساتید (Direct Click Action)
            # -------------------------------------------------------------
            act_prof_review = QtWidgets.QAction(t("menu.professors_menu"), window)
            menubar.addAction(act_prof_review)
            actions['prof_review'] = act_prof_review

            # -------------------------------------------------------------
            # 4. 📝 امتحانات (Exams)
            # -------------------------------------------------------------
            exam_menu = menubar.addMenu(t("menu.exams_menu"))
            menus['exam_menu'] = exam_menu

            act_show_exams = QtWidgets.QAction(t("menu.show_exams"), window)
            exam_menu.addAction(act_show_exams)
            actions['show_exam_schedule'] = act_show_exams

            act_export_exams = QtWidgets.QAction(t("menu.export_exams"), window)
            exam_menu.addAction(act_export_exams)
            actions['export_exam_schedule'] = act_export_exams

            # -------------------------------------------------------------
            # 5. ⚙️ تنظیمات (Settings, Language & Theme)
            # -------------------------------------------------------------
            settings_menu = menubar.addMenu(t("menu.settings_menu"))
            menus['settings_menu'] = settings_menu

            lang_submenu = settings_menu.addMenu(t("menu.language_menu"))
            menus['lang_menu'] = lang_submenu

            lang_group = QtWidgets.QActionGroup(window)
            lang_group.setExclusive(True)

            act_persian = QtWidgets.QAction(t("menu.persian"), window, checkable=True)
            act_english = QtWidgets.QAction(t("menu.english"), window, checkable=True)

            lang_group.addAction(act_persian)
            lang_group.addAction(act_english)

            lang_submenu.addAction(act_persian)
            lang_submenu.addAction(act_english)

            actions['persian_lang'] = act_persian
            actions['english_lang'] = act_english
            actions['lang_group'] = lang_group

            settings_menu.addSeparator()

            theme_submenu = settings_menu.addMenu(t("menu.theme_menu"))
            menus['theme_menu'] = theme_submenu

            theme_group = QtWidgets.QActionGroup(window)
            theme_group.setExclusive(True)

            act_theme_light = QtWidgets.QAction(t("menu.theme_light"), window, checkable=True)
            act_theme_dark = QtWidgets.QAction(t("menu.theme_dark"), window, checkable=True)
            act_theme_system = QtWidgets.QAction(t("menu.theme_system"), window, checkable=True)

            theme_group.addAction(act_theme_light)
            theme_group.addAction(act_theme_dark)
            theme_group.addAction(act_theme_system)

            theme_submenu.addAction(act_theme_light)
            theme_submenu.addAction(act_theme_dark)
            theme_submenu.addAction(act_theme_system)

            actions['theme_light'] = act_theme_light
            actions['theme_dark'] = act_theme_dark
            actions['theme_system'] = act_theme_system
            actions['theme_group'] = theme_group

            settings_menu.addSeparator()

            act_settings = QtWidgets.QAction(t("menu.open_settings"), window)
            settings_menu.addAction(act_settings)
            actions['settings'] = act_settings

            # -------------------------------------------------------------
            # 6. ❓ راهنما (Help)
            # -------------------------------------------------------------
            help_menu = menubar.addMenu(t("menu.help_menu"))
            menus['help_menu'] = help_menu

            act_tutorial = QtWidgets.QAction(t("menu.tutorial"), window)
            help_menu.addAction(act_tutorial)
            actions['tutorial'] = act_tutorial

            act_about = QtWidgets.QAction(t("menu.about"), window)
            help_menu.addAction(act_about)
            actions['about'] = act_about

        except Exception as e:
            logger.error(f"Error in MenuBuilder: {e}")

        return menus, actions
