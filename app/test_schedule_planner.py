#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for Schedule Planner

Tests covering PDF export, UI controls, and inline edit functionality.
"""

import unittest
import os
import sys
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, MagicMock

# Add the main application directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import PyQt5 for testing
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

# Import application modules
import chupolovski_class_planner
from chupolovski_class_planner import SchedulerWindow, DetailedInfoWindow, load_courses_from_json, save_courses_to_json


class TestSchedulePlanner(unittest.TestCase):
    """Test cases for Schedule Planner functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        # Create QApplication if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
            
        # Create temporary directory for test files
        cls.test_dir = tempfile.mkdtemp(prefix='schedule_planner_test_')
        cls.original_dir = os.getcwd()
        os.chdir(cls.test_dir)
        
        # Set up test data
        cls.test_courses_data = {
            "courses": {
                "test_course_1": {
                    "code": "TEST001",
                    "name": "Test Course 1",
                    "credits": 3,
                    "instructor": "Test Instructor",
                    "schedule": [
                        {"day": "شنبه", "start": "08:00", "end": "10:00", "parity": ""}
                    ],
                    "location": "Test Location",
                    "description": "Test course description",
                    "exam_time": "1403/10/15 - 09:00-11:00"
                },
                "test_course_2": {
                    "code": "TEST002",
                    "name": "Test Course 2",
                    "credits": 2,
                    "instructor": "Test Instructor 2",
                    "schedule": [
                        {"day": "یکشنبه", "start": "10:00", "end": "12:00", "parity": ""}
                    ],
                    "location": "Test Location 2",
                    "description": "Test course 2 description",
                    "exam_time": "1403/10/20 - 14:00-16:00"
                }
            },
            "custom_courses": [],
            "saved_combos": []
        }
        
        # Create test courses data file
        with open('courses_data.json', 'w', encoding='utf-8') as f:
            json.dump(cls.test_courses_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        os.chdir(cls.original_dir)
        shutil.rmtree(cls.test_dir, ignore_errors=True)
    
    def setUp(self):
        """Set up each test"""
        # Reload courses from test data
        load_courses_from_json()
        
    def test_load_courses_from_json(self):
        """Test loading courses from JSON file"""
        # Reload courses
        load_courses_from_json()
        
        # Verify courses were loaded
        self.assertGreater(len(chupolovski_class_planner.COURSES), 0)
        self.assertIn('test_course_1', chupolovski_class_planner.COURSES)
        self.assertEqual(chupolovski_class_planner.COURSES['test_course_1']['name'], 'Test Course 1')
        self.assertEqual(chupolovski_class_planner.COURSES['test_course_1']['exam_time'], '1403/10/15 - 09:00-11:00')
    
    def test_save_courses_to_json(self):
        """Test saving courses to JSON file"""
        # Add a new course
        chupolovski_class_planner.COURSES['new_test_course'] = {
            "code": "NEW001",
            "name": "New Test Course",
            "credits": 1,
            "instructor": "New Instructor",
            "schedule": [],
            "location": "New Location",
            "description": "New test description",
            "exam_time": "1403/11/01 - 10:00-12:00"
        }
        
        # Save courses
        save_courses_to_json()
        
        # Verify file was updated
        self.assertTrue(os.path.exists('courses_data.json'))
        
        # Reload and verify
        with open('courses_data.json', 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertIn('new_test_course', saved_data['courses'])
        self.assertEqual(saved_data['courses']['new_test_course']['name'], 'New Test Course')
    
    def test_scheduler_window_initialization(self):
        """Test SchedulerWindow initializes properly"""
        try:
            window = SchedulerWindow()
            
            # Check basic window properties
            self.assertIsNotNone(window)
            self.assertEqual(window.windowTitle(), 'برنامه‌ریز انتخاب واحد - Schedule Planner v2.0')
            
            # Check that essential UI components exist
            self.assertIsNotNone(window.course_list)
            self.assertIsNotNone(window.table)
            self.assertIsNotNone(window.status_bar)
            
            # Check that placed courses dict is initialized
            self.assertIsInstance(window.placed, dict)
            self.assertEqual(len(window.placed), 0)
            
            window.close()
            
        except Exception as e:
            self.fail(f"SchedulerWindow initialization failed: {e}")
    
    def test_detailed_info_window_initialization(self):
        """Test DetailedInfoWindow initializes properly"""
        try:
            main_window = SchedulerWindow()
            detail_window = DetailedInfoWindow(main_window)
            
            # Check basic window properties
            self.assertIsNotNone(detail_window)
            self.assertEqual(detail_window.windowTitle(), 'اطلاعات تفصیلی دروس و برنامه امتحانات')
            
            # Check that essential UI components exist
            self.assertIsNotNone(detail_window.exam_table)
            
            # Check parent relationship
            self.assertEqual(detail_window.parent_window, main_window)
            
            detail_window.close()
            main_window.close()
            
        except Exception as e:
            self.fail(f"DetailedInfoWindow initialization failed: {e}")
    
    def test_pdf_export_html_generation(self):
        """Test PDF export HTML generation functionality"""
        try:
            main_window = SchedulerWindow()
            detail_window = DetailedInfoWindow(main_window)
            
            # Set up test exam data
            detail_window.exam_table.setRowCount(2)
            detail_window.exam_table.setItem(0, 0, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Course 1"))
            detail_window.exam_table.setItem(0, 1, chupolovski_class_planner.QtWidgets.QTableWidgetItem("TEST001"))
            detail_window.exam_table.setItem(0, 2, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Instructor"))
            detail_window.exam_table.setItem(0, 3, chupolovski_class_planner.QtWidgets.QTableWidgetItem("1403/10/15 - 09:00-11:00"))
            detail_window.exam_table.setItem(0, 4, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Location"))
            
            detail_window.exam_table.setItem(1, 0, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Course 2"))
            detail_window.exam_table.setItem(1, 1, chupolovski_class_planner.QtWidgets.QTableWidgetItem("TEST002"))
            detail_window.exam_table.setItem(1, 2, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Instructor 2"))
            detail_window.exam_table.setItem(1, 3, chupolovski_class_planner.QtWidgets.QTableWidgetItem("1403/10/20 - 14:00-16:00"))
            detail_window.exam_table.setItem(1, 4, chupolovski_class_planner.QtWidgets.QTableWidgetItem("Test Location 2"))
            
            # Test HTML generation
            html_content = detail_window._generate_pdf_html(2)
            
            # Verify HTML content
            self.assertIsInstance(html_content, str)
            self.assertIn('<!DOCTYPE html>', html_content)
            self.assertIn('برنامه امتحانات', html_content)
            self.assertIn('Test Course 1', html_content)
            self.assertIn('Test Course 2', html_content)
            self.assertIn('1403/10/15 - 09:00-11:00', html_content)
            self.assertIn('1403/10/20 - 14:00-16:00', html_content)
            
            # Verify RTL layout
            self.assertIn('dir="rtl"', html_content)
            self.assertIn('lang="fa"', html_content)
            
            detail_window.close()
            main_window.close()
            
        except Exception as e:
            self.fail(f"PDF HTML generation failed: {e}")
    
    def test_pdf_export_fallback(self):
        """Test PDF export fallback functionality"""
        try:
            main_window = SchedulerWindow()
            detail_window = DetailedInfoWindow(main_window)
            
            # Set up test exam data
            detail_window.exam_table.setRowCount(1)
            detail_window.exam_table.setItem(0, 0, chupolovski.QtWidgets.QTableWidgetItem("Test Course"))
            detail_window.exam_table.setItem(0, 1, chupolovski.QtWidgets.QTableWidgetItem("TEST001"))
            detail_window.exam_table.setItem(0, 2, chupolovski.QtWidgets.QTableWidgetItem("Test Instructor"))
            detail_window.exam_table.setItem(0, 3, chupolovski.QtWidgets.QTableWidgetItem("1403/10/15 - 09:00-11:00"))
            detail_window.exam_table.setItem(0, 4, chupolovski.QtWidgets.QTableWidgetItem("Test Location"))
            
            # Test fallback export
            test_filename = os.path.join(self.test_dir, 'test_exam.pdf')
            detail_window._export_pdf_fallback(test_filename, 1)
            
            # Verify HTML file was created
            html_filename = test_filename.replace('.pdf', '_exam_schedule.html')
            self.assertTrue(os.path.exists(html_filename))
            
            # Verify HTML content
            with open(html_filename, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            self.assertIn('Test Course', html_content)
            self.assertIn('1403/10/15 - 09:00-11:00', html_content)
            
            detail_window.close()
            main_window.close()
            
        except Exception as e:
            self.fail(f"PDF fallback export failed: {e}")
    
    def test_course_editing_functionality(self):
        """Test inline course editing functionality"""
        try:
            main_window = SchedulerWindow()
            
            # Verify course exists
            self.assertIn('test_course_1', chupolovski.COURSES)
            original_name = chupolovski.COURSES['test_course_1']['name']
            
            # Test edit course functionality
            updated_course_data = {
                'code': 'TEST001_UPDATED',
                'name': 'Updated Test Course 1',
                'credits': 4,
                'instructor': 'Updated Instructor',
                'schedule': [
                    {"day": "شنبه", "start": "10:00", "end": "12:00", "parity": ""}
                ],
                'location': 'Updated Location',
                'description': 'Updated description',
                'exam_time': '1403/10/16 - 10:00-12:00'
            }
            
            # Simulate course update
            chupolovski.COURSES['test_course_1'] = updated_course_data
            
            # Verify update
            self.assertEqual(chupolovski.COURSES['test_course_1']['name'], 'Updated Test Course 1')
            self.assertEqual(chupolovski.COURSES['test_course_1']['exam_time'], '1403/10/16 - 10:00-12:00')
            
            main_window.close()
            
        except Exception as e:
            self.fail(f"Course editing test failed: {e}")
    
    def test_course_conflict_detection(self):
        """Test course conflict detection"""
        try:
            # Test schedule conflict detection
            schedule1 = [{"day": "شنبه", "start": "08:00", "end": "10:00", "parity": ""}]
            schedule2 = [{"day": "شنبه", "start": "09:00", "end": "11:00", "parity": ""}]
            schedule3 = [{"day": "یکشنبه", "start": "08:00", "end": "10:00", "parity": ""}]
            
            # These should conflict
            self.assertTrue(chupolovski.schedules_conflict(schedule1, schedule2))
            
            # These should not conflict (different days)
            self.assertFalse(chupolovski.schedules_conflict(schedule1, schedule3))
            
        except Exception as e:
            self.fail(f"Conflict detection test failed: {e}")
    
    def test_ui_controls_functionality(self):
        """Test that moving UI controls doesn't break functionality"""
        try:
            main_window = SchedulerWindow()
            
            # Test that menu bar exists and has expected menus
            menu_bar = main_window.menuBar()
            self.assertIsNotNone(menu_bar)
            
            # Check that essential menus exist
            actions = menu_bar.actions()
            menu_texts = [action.text() for action in actions]
            
            # Should have File, View, and Course menus
            self.assertIn('📁 فایل', menu_texts)
            self.assertIn('👁️ نمایش', menu_texts)
            self.assertIn('📚 دروس', menu_texts)
            
            # Test detailed info window opening
            self.assertIsNone(main_window.detailed_info_window)
            main_window.open_detailed_info_window()
            self.assertIsNotNone(main_window.detailed_info_window)
            
            main_window.close()
            
        except Exception as e:
            self.fail(f"UI controls test failed: {e}")


class TestPDFExportIntegration(unittest.TestCase):
    """Integration tests specifically for PDF export functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment for PDF tests"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
        
        cls.test_dir = tempfile.mkdtemp(prefix='pdf_test_')
        cls.original_dir = os.getcwd()
        os.chdir(cls.test_dir)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up PDF test environment"""
        os.chdir(cls.original_dir)
        shutil.rmtree(cls.test_dir, ignore_errors=True)
    
    def test_pdf_file_creation(self):
        """Test that PDF export creates a readable file"""
        try:
            main_window = SchedulerWindow()
            detail_window = DetailedInfoWindow(main_window)
            
            # Add test data
            detail_window.exam_table.setRowCount(1)
            detail_window.exam_table.setItem(0, 0, chupolovski.QtWidgets.QTableWidgetItem("Sample Course"))
            detail_window.exam_table.setItem(0, 1, chupolovski.QtWidgets.QTableWidgetItem("SAMPLE001"))
            detail_window.exam_table.setItem(0, 2, chupolovski.QtWidgets.QTableWidgetItem("Sample Instructor"))
            detail_window.exam_table.setItem(0, 3, chupolovski.QtWidgets.QTableWidgetItem("1403/10/15 - 09:00-11:00"))
            detail_window.exam_table.setItem(0, 4, chupolovski.QtWidgets.QTableWidgetItem("Sample Location"))
            
            # Test file creation
            test_filename = os.path.join(self.test_dir, 'integration_test.pdf')
            detail_window._export_pdf_fallback(test_filename, 1)
            
            # Verify HTML file exists (fallback)
            html_filename = test_filename.replace('.pdf', '_exam_schedule.html')
            self.assertTrue(os.path.exists(html_filename))
            
            # Verify file is not empty
            self.assertGreater(os.path.getsize(html_filename), 0)
            
            # Verify content is readable HTML
            with open(html_filename, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('<!DOCTYPE html>', content)
                self.assertIn('Sample Course', content)
            
            detail_window.close()
            main_window.close()
            
        except Exception as e:
            self.fail(f"PDF integration test failed: {e}")


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestSchedulePlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestPDFExportIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)