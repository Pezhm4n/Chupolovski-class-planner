#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Course utility functions for Schedule Planner
Contains helper functions for time calculations and schedule optimization

Priority System:
- Lower priority numbers have higher priority (1 = highest priority)
- Priority is stored in UserRole + 1 data role of QListWidget items
- When conflicts occur, courses with higher priority (lower numbers) replace courses with lower priority (higher numbers)
- Drag & drop reordering automatically updates priorities based on item position
"""

import itertools
from itertools import product
import sys
import os

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import COURSES, DAYS, TIME_SLOTS

# ---------------------- Time Utility Functions ----------------------

def to_minutes(tstr):
    """Convert time string (HH:MM) to minutes since midnight"""
    h, mm = map(int, tstr.split(':'))
    return h * 60 + mm


def overlap(s1, e1, s2, e2):
    """Check if two time intervals overlap"""
    return not (e1 <= s2 or e2 <= s1)


def schedules_conflict(sch1, sch2):
    """Check if two schedules have time conflicts"""
    for a in sch1:
        for b in sch2:
            if a['day'] != b['day']:
                continue
            if a.get('parity') and b.get('parity') and a['parity'] != b['parity']:
                continue
            if overlap(to_minutes(a['start']), to_minutes(a['end']), to_minutes(b['start']), to_minutes(b['end'])):
                return True
    return False


def calculate_days_needed_for_combo(combo_keys):
    """Calculate the number of days needed for a combination of courses"""
    days = set()
    for key in combo_keys:
        for item in COURSES[key]['schedule']:
            days.add(item['day'])
    return len(days)


def calculate_empty_time_for_combo(combo_keys):
    """Calculate the empty time (gaps) for a combination of courses"""
    daily = {}
    for key in combo_keys:
        for item in COURSES[key]['schedule']:
            day = item['day']
            if day not in daily:
                daily[day] = []
            daily[day].append((to_minutes(item['start']), to_minutes(item['end'])))
    penalty = 0.0
    for intervals in daily.values():
        intervals.sort()
        for i in range(len(intervals) - 1):
            gap = intervals[i + 1][0] - intervals[i][1]
            if gap > 15:
                penalty += gap / 60.0
    return penalty


# ---------------------- Schedule Optimization Functions ----------------------

def generate_best_combinations_for_groups(group_keys):
    """Generate best schedule combinations for groups of courses (minimizing days and gaps)
    
    Note: This function does not consider priorities. Priority-based conflict resolution
    is handled in the main window's add_course_to_table method.
    """
    # group_keys: list of group_key strings (base code)
    # build candidate lists for each group: course keys in COURSES whose code startswith group_key
    groups = []
    for g in group_keys:
        candidates = [k for k, v in COURSES.items() if v.get('code', '').split('_')[0] == g]
        if not candidates:
            # fallback: try match by name contains g
            candidates = [k for k, v in COURSES.items() if v.get('code', '') == g or g in v.get('name', '')]
        if not candidates:
            # can't produce combos
            return []
        groups.append(candidates)

    combos = []
    for pick in product(*groups):
        # pick is a tuple of course keys (one per group)
        keys = list(pick)
        # check conflicts pairwise
        ok = True
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                if schedules_conflict(COURSES[keys[i]]['schedule'], COURSES[keys[j]]['schedule']):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        days = calculate_days_needed_for_combo(keys)
        empty = calculate_empty_time_for_combo(keys)
        score = days + 0.5 * empty
        combos.append({'courses': keys, 'days': days, 'empty': empty, 'score': score})
    combos.sort(key=lambda x: (x['days'], x['empty'], x['score']))
    return combos


def generate_priority_based_schedules(ordered_course_keys):
    """Generate schedules respecting user-defined priority order"""
    valid_schedules = []
    
    # Method 1: Pure greedy - add courses in priority order until conflict
    greedy_schedule = create_greedy_schedule(ordered_course_keys)
    if greedy_schedule:
        valid_schedules.append({
            'courses': greedy_schedule,
            'method': 'Priority Greedy',
            'score': len(greedy_schedule) * 100,  # Higher score for more courses
            'priority_preserved': True,
            'days': calculate_days_needed_for_combo(greedy_schedule),
            'empty': calculate_empty_time_for_combo(greedy_schedule)
        })
    
    # Method 2: Generate alternatives by skipping lower-priority conflicts
    for skip_count in range(1, min(4, len(ordered_course_keys))):
        alternative = create_alternative_schedule(ordered_course_keys, skip_count)
        if alternative and alternative not in [s['courses'] for s in valid_schedules]:
            valid_schedules.append({
                'courses': alternative,
                'method': f'Skip {skip_count} Lower Priority',
                'score': len(alternative) * 100 - skip_count * 10,
                'priority_preserved': True,
                'days': calculate_days_needed_for_combo(alternative),
                'empty': calculate_empty_time_for_combo(alternative)
            })
    
    return sorted(valid_schedules, key=lambda x: x['score'], reverse=True)


def create_greedy_schedule(ordered_course_keys):
    """Build schedule by adding courses in priority order"""
    selected_courses = []
    
    for priority_index, course_key in enumerate(ordered_course_keys):
        if course_key not in COURSES:
            continue
            
        # Check conflicts with already selected courses
        current_schedule = COURSES[course_key].get('schedule', [])
        has_conflict = False
        
        for selected_key in selected_courses:
            selected_schedule = COURSES[selected_key].get('schedule', [])
            if schedules_conflict(current_schedule, selected_schedule):
                has_conflict = True
                break
        
        # Add course only if no conflicts (priority-first principle)
        if not has_conflict:
            selected_courses.append(course_key)
    
    return selected_courses


def create_alternative_schedule(ordered_course_keys, skip_count):
    """Create alternative by temporarily skipping problematic courses"""
    remaining_courses = ordered_course_keys[:]
    selected_courses = []
    skipped_courses = []
    
    # First, try to add courses in priority order, skipping up to skip_count courses
    for course_key in remaining_courses:
        if len(skipped_courses) >= skip_count:
            break
            
        # Check if this course conflicts with already selected courses
        current_schedule = COURSES[course_key].get('schedule', [])
        has_conflict = any(
            schedules_conflict(current_schedule, COURSES[sel].get('schedule', []))
            for sel in selected_courses
        )
        
        if has_conflict:
            skipped_courses.append(course_key)  # Skip this course
        else:
            selected_courses.append(course_key)  # Add this course
    
    # Try to add remaining courses that weren't skipped
    for course_key in remaining_courses:
        if course_key not in selected_courses and course_key not in skipped_courses:
            current_schedule = COURSES[course_key].get('schedule', [])
            has_conflict = any(
                schedules_conflict(current_schedule, COURSES[sel].get('schedule', []))
                for sel in selected_courses
            )
            if not has_conflict:
                selected_courses.append(course_key)
    
    return selected_courses