# -*- coding: utf-8 -*-
"""
Golestoon Menu Builder.
Constructs a unified, clean, and modern menu bar aligned with Golestoon Web routes.
"""

import datetime
import logging
from PyQt5 import QtWidgets, QtCore

class MenuBuilder:
    """Pure UI builder for creating application menus and action hierarchies."""

    @staticmethod
    def build_menu_bar(window: QtWidgets.QMainWindow, logger: logging.Logger):
        """Constructs menu bar structure and returns created actions/menus dictionary for window to wire."""
        actions = {}
        menus = {}
        
        try:
            menubar = window.menubar if hasattr(window, 'menubar') else window.menuBar()
            menubar.clear()
            menus['menubar'] = menubar

            # -------------------------------------------------------------
            # 1. 🌐 داده‌ها و همگام‌سازی (Data & Cloud Sync)
            # -------------------------------------------------------------
            data_menu = menubar.addMenu("🌐 داده‌ها و همگام‌سازی")
            menus['data_menu'] = data_menu

            act_cloud_auth = QtWidgets.QAction("🔑 ورود / مدیریت حساب کاربری...", window)
            data_menu.addAction(act_cloud_auth)
            actions['cloud_auth'] = act_cloud_auth

            act_cloud_sync = QtWidgets.QAction("☁️ پشتیبان‌گیری و بازیابی ابری...", window)
            data_menu.addAction(act_cloud_sync)
            actions['cloud_sync'] = act_cloud_sync

            data_menu.addSeparator()

            act_fetch_golestan = QtWidgets.QAction("🔄 دریافت آنلاین دروس از گلستان...", window)
            data_menu.addAction(act_fetch_golestan)
            actions['fetch_golestan'] = act_fetch_golestan

            act_reset_creds = QtWidgets.QAction("🔒 پاکسازی اطلاعات ورود به گلستان", window)
            data_menu.addAction(act_reset_creds)
            actions['reset_creds'] = act_reset_creds

            data_menu.addSeparator()

            history_menu = data_menu.addMenu("📂 نسخه‌های پشتیبان محلی")
            menus['history_menu'] = history_menu

            # -------------------------------------------------------------
            # 2. 🎓 داشبورد تحصیلی دانشجو (Student Dashboard)
            # -------------------------------------------------------------
            acad_menu = menubar.addMenu("🎓 خدمات تحصیلی")
            menus['acad_menu'] = acad_menu

            act_student_dashboard = QtWidgets.QAction("📊 داشبورد دانشجو، کارنامه و پیشرفت تحصیلی (گزارش ۲۷۲)...", window)
            acad_menu.addAction(act_student_dashboard)
            actions['student_dashboard'] = act_student_dashboard
            actions['student_profile'] = act_student_dashboard
            actions['academic'] = act_student_dashboard

            # -------------------------------------------------------------
            # 3. 👨‍🏫 نظرسنجی و اساتید (Professor Reviews)
            # -------------------------------------------------------------
            prof_menu = menubar.addMenu("👨‍🏫 نظرسنجی اساتید")
            menus['prof_menu'] = prof_menu

            act_prof_review = QtWidgets.QAction("⭐ نظرسنجی و مقایسه اساتید...", window)
            prof_menu.addAction(act_prof_review)
            actions['prof_review'] = act_prof_review

            # -------------------------------------------------------------
            # 4. 📝 برنامه امتحانات (Exam Timetable)
            # -------------------------------------------------------------
            exam_menu = menubar.addMenu("📝 امتحانات")
            menus['exam_menu'] = exam_menu

            act_show_exams = QtWidgets.QAction("📅 نمایش تقویم و برنامه امتحانات...", window)
            exam_menu.addAction(act_show_exams)
            actions['show_exam_schedule'] = act_show_exams

            act_export_exams = QtWidgets.QAction("📤 دریافت خروجی از برنامه امتحانات (PDF / تصویر)...", window)
            exam_menu.addAction(act_export_exams)
            actions['export_exam_schedule'] = act_export_exams

            # -------------------------------------------------------------
            # 5. ⚙️ تنظیمات و زبان (Settings & Language)
            # -------------------------------------------------------------
            settings_menu = menubar.addMenu("⚙️ تنظیمات")
            menus['settings_menu'] = settings_menu

            lang_submenu = settings_menu.addMenu("🌐 زبان برنامه (Language)")
            menus['lang_menu'] = lang_submenu

            # Language selection with QActionGroup (Exclusive Selection)
            lang_group = QtWidgets.QActionGroup(window)
            lang_group.setExclusive(True)

            act_persian = QtWidgets.QAction("🇮🇷 فارسی", window, checkable=True)
            act_english = QtWidgets.QAction("🇬🇧 English", window, checkable=True)

            lang_group.addAction(act_persian)
            lang_group.addAction(act_english)

            lang_submenu.addAction(act_persian)
            lang_submenu.addAction(act_english)

            actions['persian_lang'] = act_persian
            actions['english_lang'] = act_english
            actions['lang_group'] = lang_group

            settings_menu.addSeparator()

            act_settings = QtWidgets.QAction("⚙️ تنظیمات برنامه...", window)
            settings_menu.addAction(act_settings)
            actions['settings'] = act_settings

            # -------------------------------------------------------------
            # 6. ❓ راهنما و آموزش (Help & Guide)
            # -------------------------------------------------------------
            help_menu = menubar.addMenu("❓ راهنما")
            menus['help_menu'] = help_menu

            act_tutorial = QtWidgets.QAction("💡 آموزش و راهنمای تصویری برنامه...", window)
            help_menu.addAction(act_tutorial)
            actions['tutorial'] = act_tutorial

            act_about = QtWidgets.QAction("ℹ️ درباره گلستون دسکتاپ...", window)
            help_menu.addAction(act_about)
            actions['about'] = act_about

        except Exception as e:
            logger.error(f"Error in MenuBuilder: {e}")

        return menus, actions
