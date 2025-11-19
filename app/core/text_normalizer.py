#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text normalization utilities for Persian text matching
"""

import re


def normalize_persian_text(text):
    """Normalize Persian text for matching"""
    if not text:
        return ""
    
    text = str(text).strip()
    
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    english_digits = '0123456789'
    
    persian_to_english = str.maketrans(persian_digits, english_digits)
    arabic_to_english = str.maketrans(arabic_digits, english_digits)
    
    text = text.translate(persian_to_english)
    text = text.translate(arabic_to_english)
    
    # Normalize common Arabic characters to Persian equivalents
    arabic_char_map = str.maketrans({
        'ي': 'ی',
        'ى': 'ی',
        'ئ': 'ی',
        'ك': 'ک',
        'ؤ': 'و',
        'إ': 'ا',
        'أ': 'ا',
        'آ': 'ا',
        'ۀ': 'ه',
        'ة': 'ه',
        'ء': '',
    })
    text = text.translate(arabic_char_map)
    
    # Replace zero-width characters and different dash/quote variations
    text = text.replace('\u200c', '')
    text = text.replace('\u200d', '')
    text = text.replace('ـ', '')
    text = text.replace('–', ' ')
    text = text.replace('-', ' ')
    text = text.replace('—', ' ')
    text = text.replace('_', ' ')
    text = text.replace('‎', '')
    text = text.replace('‏', '')
    text = text.replace('"', '')
    text = text.replace("'", '')
    
    # Remove bracketed/parenthetical annotations entirely (e.g., "(کارشناسی)")
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    text = re.sub(r'\{[^}]*\}', ' ', text)
    
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    text = re.sub(r'[()\[\]{}()]', '', text)
    text = re.sub(r'[،؛:؛٬«»]', '', text)
    text = text.replace('اسالم', 'اسلام')
    text = text.lower()
    
    return text


def fuzzy_match(text1, text2, threshold=0.7):
    """Check if two normalized texts match with fuzzy logic"""
    norm1 = normalize_persian_text(text1)
    norm2 = normalize_persian_text(text2)
    
    if not norm1 or not norm2:
        return False
    
    if norm1 == norm2:
        return True
    
    if norm1 in norm2 or norm2 in norm1:
        return True
    
    set1 = set(norm1.replace(' ', ''))
    set2 = set(norm2.replace(' ', ''))
    
    if not set1 or not set2:
        return False
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return False
    
    similarity = intersection / union
    return similarity >= threshold


def is_general_course_match(course_name, general_course_pattern):
    """Check if course name matches general course pattern"""
    if not course_name or not general_course_pattern:
        return False
    
    norm_course = normalize_persian_text(course_name)
    norm_pattern = normalize_persian_text(general_course_pattern)
    
    if not norm_course or not norm_pattern:
        return False
    
    if norm_course == norm_pattern:
        return True
    
    norm_course_no_num = re.sub(r'\d+', '', norm_course).strip()
    norm_pattern_no_num = re.sub(r'\d+', '', norm_pattern).strip()
    
    if norm_course_no_num == norm_pattern_no_num:
        return True
    
    if norm_course_no_num.startswith(norm_pattern_no_num):
        after = norm_course_no_num[len(norm_pattern_no_num):].strip()
        if after and re.search(r'[آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]', after):
            return False
    
    if norm_course.startswith(norm_pattern):
        remaining = norm_course[len(norm_pattern):].strip()
        if not remaining:
            return True
        if remaining and remaining[0] in ' 0123456789۰۱۲۳۴۵۶۷۸۹':
            if all(c in ' 0123456789۰۱۲۳۴۵۶۷۸۹' for c in remaining):
                return True
    
    if norm_pattern.startswith(norm_course):
        remaining = norm_pattern[len(norm_course):].strip()
        if not remaining:
            return True
        if remaining and remaining[0] in ' 0123456789۰۱۲۳۴۵۶۷۸۹':
            if all(c in '0123456789۰۱۲۳۴۵۶۷۸۹' for c in remaining):
                return True
    
    if len(norm_pattern) <= 5:
        if norm_course == norm_pattern:
            return True
        if norm_course.startswith(norm_pattern):
            remaining = norm_course[len(norm_pattern):].strip()
            if remaining and all(c in '0123456789۰۱۲۳۴۵۶۷۸۹ ' for c in remaining):
                remaining_no_space = remaining.replace(' ', '')
                if remaining_no_space and all(c in '0123456789۰۱۲۳۴۵۶۷۸۹' for c in remaining_no_space):
                    return True
    
    if norm_pattern in norm_course:
        pattern_start = norm_course.find(norm_pattern)
        if pattern_start >= 0:
            before = norm_course[:pattern_start].strip()
            after = norm_course[pattern_start + len(norm_pattern):].strip()
            
            allowed_chars = ' 0123456789۰۱۲۳۴۵۶۷۸۹'
            
            def is_numeric_segment(segment):
                if not segment:
                    return True
                return all(c in allowed_chars for c in segment)
            
            if is_numeric_segment(before) and is_numeric_segment(after):
                return True
    
    return False
