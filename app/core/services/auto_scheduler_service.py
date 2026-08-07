import logging
from typing import List, Dict, Any
from app.core.services.result import Result
from app.core.course_utils import generate_best_combinations_for_groups, generate_priority_based_schedules

class AutoSchedulerService:
    """Service responsible for generating optimal schedules."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def generate_optimal_schedule(self, all_courses: List[str]) -> Result:
        """Generate optimal schedule combinations with conflict handling"""
        if not all_courses:
            return Result(success=False, message="هیچ درسی برای برنامه‌ریزی وجود ندارد.")
            
        try:
            self.logger.debug(f"Generating optimal schedules for {len(all_courses)} courses")
            combos = generate_best_combinations_for_groups(all_courses)
            return Result(success=True, data={'combinations': combos})
        except Exception as e:
            self.logger.error(f"Error in generate_optimal_schedule: {e}")
            return Result(success=False, error=str(e))
            
    def generate_priority_aware_schedule(self, ordered_course_keys: List[str]) -> Result:
        """Generate schedules that respect user priority order"""
        if not ordered_course_keys:
            return Result(success=False, message="لیست اولویت خالی است.")
            
        try:
            self.logger.debug(f"Generating priority schedules for {len(ordered_course_keys)} courses")
            schedules = generate_priority_based_schedules(ordered_course_keys)
            return Result(success=True, data={'schedules': schedules})
        except Exception as e:
            self.logger.error(f"Error in generate_priority_aware_schedule: {e}")
            return Result(success=False, error=str(e))
