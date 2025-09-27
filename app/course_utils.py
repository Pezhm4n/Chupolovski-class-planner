#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Course utility functions for Schedule Planner
Contains helper functions for time calculations and schedule optimization
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
    """Generate best schedule combinations for groups of courses (minimizing days and gaps)"""
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