import logging
from PyQt5 import QtWidgets, QtCore
from app.core.config import COURSES
from app.core.data_manager import save_user_added_courses, save_user_data, generate_unique_key

# Import Dialogs
from app.ui.dialogs import AddCourseDialog, EditCourseDialog, DetailedInfoWindow
from app.ui.exam_schedule_window import ExamScheduleWindow

class DialogCoordinator:
    """Coordinator responsible for managing and displaying application dialogs."""
    
    def __init__(self, main_window, logger: logging.Logger):
        self.main_window = main_window
        self.logger = logger
        self.detailed_info_window = None
        self._exam_schedule_window = None

    def open_add_course_dialog(self):
        """Open dialog to add a new custom course"""
        dlg = AddCourseDialog(self.main_window)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
            
        course = dlg.get_course_data()
        if not course:
            return
        
        # Mark as user-added
        course['is_user_added'] = True
        course['custom'] = True
        course['major'] = 'دروس اضافه‌شده توسط کاربر'

        # Generate key and store
        key = generate_unique_key(course['code'], COURSES)
        COURSES[key] = course

        # Save courses to JSON
        save_user_added_courses()
        
        # Save to user data
        self.main_window.user_data.setdefault('custom_courses', []).append(course)
        save_user_data(self.main_window.user_data)
        
        # Refresh list and info panel
        self.main_window.populate_course_list()
        self.main_window.update_course_info_panel()
        QtWidgets.QMessageBox.information(
            self.main_window, 'افزودن درس', 
            f'درس "{course["name"]}" با موفقیت اضافه شد و ذخیره شد.'
        )

    def open_edit_course_dialog(self):
        """Open dialog to edit an existing course from the currently selected item"""
        selected_items = self.main_window.course_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(
                self.main_window, 'انتخاب درس', 
                'لطفا ابتدا درسی را از لیست انتخاب کنید.'
            )
            return
            
        selected_item = selected_items[0]
        course_key = selected_item.data(QtCore.Qt.UserRole)
        self.open_edit_course_dialog_for_course(course_key)

    def open_edit_course_dialog_for_course(self, course_key):
        """Open dialog to edit a specific course by course key"""
        if not course_key or course_key not in COURSES:
            QtWidgets.QMessageBox.warning(
                self.main_window, 'خطا', 
                'درس انتخابی یافت نشد.'
            )
            return
            
        course = COURSES[course_key]
        
        # Check if it's a built-in course
        if not self.main_window.is_editable_course(course_key):
            QtWidgets.QMessageBox.warning(
                self.main_window, 'غیر قابل ویرایش', 
                'دروس پیش‌فرض قابل ویرایش نیستند. فقط دروس سفارشی را می‌توان ویرایش کرد.'
            )
            return
            
        # Open edit dialog with pre-filled data
        dlg = EditCourseDialog(course, self.main_window)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
            
        updated_course = dlg.get_course_data()
        if not updated_course:
            return
            
        # Update the course
        COURSES[course_key] = updated_course
        
        # Save courses to JSON
        save_user_added_courses()
        
        # Update user_data
        custom_courses = self.main_window.user_data.get('custom_courses', [])
        for i, c in enumerate(custom_courses):
            if c.get('code') == course.get('code'):
                custom_courses[i] = updated_course
                break
        
        save_user_data(self.main_window.user_data)
        
        # Remove from schedule if placed
        self.main_window.remove_course_from_schedule(course_key)
        
        # Refresh UI
        self.main_window.populate_course_list()
        self.main_window.update_course_info_panel()
        self.main_window.update_status()
        
        QtWidgets.QMessageBox.information(
            self.main_window, 'ویرایش شد', 
            f'درس "{updated_course["name"]}" با موفقیت ویرایش شد.'
        )

    def show_course_details(self, course_key):
        """Show detailed course information in a dialog"""
        course = COURSES.get(course_key, {})
        if not course:
            return
            
        dialog = DetailedInfoWindow(self.main_window)
        dialog.exec_()

    def open_detailed_info_window(self):
        """Open the detailed information window (Exam Schedule)"""
        # Create window if it doesn't exist or was closed
        if not self.detailed_info_window or not self.detailed_info_window.isVisible():
            self.detailed_info_window = ExamScheduleWindow(self.main_window)
            
        # Show and raise the window
        self.detailed_info_window.show()
        self.detailed_info_window.raise_()
        self.detailed_info_window.activateWindow()
        
        # Update content with latest data
        self.detailed_info_window.update_content()

    def update_detailed_info_if_open(self):
        """Update the detailed info window if it's currently open"""
        if self.detailed_info_window and self.detailed_info_window.isVisible():
            self.detailed_info_window.update_content()

    def on_show_exam_schedule(self):
        """Show exam schedule window directly"""
        try:
            if not self._exam_schedule_window or not self._exam_schedule_window.isVisible():
                self._exam_schedule_window = ExamScheduleWindow(self.main_window)
            self._exam_schedule_window.show()
            self._exam_schedule_window.raise_()
            self._exam_schedule_window.activateWindow()
            self._exam_schedule_window.update_content()
        except Exception as e:
            self.logger.error(f"Error showing exam schedule: {e}")

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog (delegated)"""
        dialog = QtWidgets.QDialog(self.main_window)
        dialog.setWindowTitle('ترکیب‌های بهینه پیشنهادی')
        dialog.resize(600, 400)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        title_label = QtWidgets.QLabel('ترکیب‌های بهینه پیشنهادی')
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        if combos:
            info_label = QtWidgets.QLabel('بهترین ترکیب‌ها بر اساس حداقل روزهای حضور و حداقل فاصله بین جلسات')
        else:
            info_label = QtWidgets.QLabel('هیچ ترکیب بهینه‌ای بدون تداخل پیدا نشد. ترکیب‌هایی با تداخل نشان داده نمی‌شوند.')
        info_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(info_label)
        
        results_list = QtWidgets.QListWidget()
        layout.addWidget(results_list)
        
        if combos:
            for i, combo in enumerate(combos[:10]):
                item_widget = QtWidgets.QWidget()
                item_layout = QtWidgets.QVBoxLayout(item_widget)
                item_layout.setContentsMargins(10, 10, 10, 10)
                
                header_layout = QtWidgets.QHBoxLayout()
                rank_label = QtWidgets.QLabel(f'#{i+1}')
                rank_label.setStyleSheet("font-weight: bold; color: #1976D2; font-size: 14px;")
                rank_label.setFixedWidth(30)
                
                stats_label = QtWidgets.QLabel(f'روزها: {combo["days"]} | فاصله: {combo["empty"]:.1f}h | امتیاز: {combo["score"]:.1f}')
                stats_label.setStyleSheet("color: #7f8c8d;")
                
                apply_btn = QtWidgets.QPushButton('اعمال')
                apply_btn.setObjectName("success_btn")
                apply_btn.setFixedWidth(80)
                apply_btn.clicked.connect(lambda checked, c=combo: self.main_window.apply_optimal_combo(c, dialog))
                
                header_layout.addWidget(rank_label)
                header_layout.addWidget(stats_label)
                header_layout.addStretch()
                header_layout.addWidget(apply_btn)
                
                item_layout.addLayout(header_layout)
                
                course_list = QtWidgets.QListWidget()
                course_list.setMaximumHeight(100)
                course_list.setStyleSheet("border: 1px solid #d5dbdb; border-radius: 5px;")
                
                for course_key in combo['courses']:
                    if course_key in COURSES:
                        course = COURSES[course_key]
                        course_item = QtWidgets.QListWidgetItem(f"{course['name']} - {course['code']} - {course.get('instructor', 'نامشخص')}")
                        course_list.addItem(course_item)
                
                item_layout.addWidget(course_list)
                
                list_item = QtWidgets.QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                results_list.addItem(list_item)
                results_list.setItemWidget(list_item, item_widget)
        else:
            no_results_label = QtWidgets.QLabel('هیچ ترکیبی برای نمایش وجود ندارد.')
            no_results_label.setAlignment(QtCore.Qt.AlignCenter)
            no_results_label.setStyleSheet("color: #95a5a6; font-style: italic; padding: 20px;")
            item_widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QVBoxLayout(item_widget)
            item_layout.addWidget(no_results_label)
            list_item = QtWidgets.QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            results_list.addItem(list_item)
            results_list.setItemWidget(list_item, item_widget)
        
        close_btn = QtWidgets.QPushButton('بستن')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()

    def show_priority_aware_results(self, schedules, original_priority_order):
        """Show results with clear priority information (delegated)"""
        if not schedules:
            QtWidgets.QMessageBox.information(
                self.main_window, "نتیجه", 
                "با توجه به اولویت‌های تعیین شده و تداخل‌های زمانی، برنامه‌ای قابل ساخت نیست."
            )
            return
        
        dialog = QtWidgets.QDialog(self.main_window)
        dialog.setWindowTitle("برنامه‌های پیشنهادی با اولویت")
        dialog.setModal(True)
        dialog.resize(700, 500)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        info_label = QtWidgets.QLabel(f"{len(schedules)} برنامه پیشنهادی یافت شد. روی یکی کلیک کنید:")
        layout.addWidget(info_label)
        
        schedule_list = QtWidgets.QListWidget()
        schedule_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        for i, schedule in enumerate(schedules):
            included_priorities = []
            skipped_priorities = []
            
            for j, course_key in enumerate(original_priority_order):
                priority_num = j + 1
                course_name = COURSES[course_key].get('name', course_key)
                
                if course_key in schedule['courses']:
                    included_priorities.append(f"P{priority_num}: {course_name}")
                else:
                    skipped_priorities.append(f"P{priority_num}: {course_name}")
            
            schedule['display_info'] = {
                'included': included_priorities,
                'skipped': skipped_priorities,
                'priority_success_rate': len(included_priorities) / len(original_priority_order) if original_priority_order else 0
            }
            
            method_text = schedule.get('method', 'Unknown Method')
            course_count = len(schedule['courses'])
            days = schedule.get('days', 0)
            empty_time = schedule.get('empty', 0.0)
            
            schedule_text = f"{method_text}: {course_count} درس - {days} روز - {empty_time:.1f} ساعت خالی"
            
            item = QtWidgets.QListWidgetItem(schedule_text)
            item.setData(QtCore.Qt.UserRole, schedule)
            schedule_list.addItem(item)
        
        layout.addWidget(schedule_list)
        
        button_layout = QtWidgets.QHBoxLayout()
        apply_btn = QtWidgets.QPushButton("اعمال برنامه")
        cancel_btn = QtWidgets.QPushButton("انصراف")
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        def on_apply():
            selected_items = schedule_list.selectedItems()
            if selected_items:
                schedule = selected_items[0].data(QtCore.Qt.UserRole)
                self.main_window.apply_priority_aware_schedule(schedule, dialog)
            else:
                QtWidgets.QMessageBox.warning(dialog, "هشدار", "لطفاً یک برنامه انتخاب کنید.")
        
        def on_item_double_click(item):
            schedule = item.data(QtCore.Qt.UserRole)
            self.main_window.apply_priority_aware_schedule(schedule, dialog)
        
        def on_item_click(item):
            schedule = item.data(QtCore.Qt.UserRole)
            self.main_window.show_schedule_details(schedule)
        
        apply_btn.clicked.connect(on_apply)
        cancel_btn.clicked.connect(dialog.close)
        schedule_list.itemDoubleClicked.connect(on_item_double_click)
        schedule_list.itemClicked.connect(on_item_click)
        
        dialog.exec_()
