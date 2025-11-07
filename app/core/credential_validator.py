"""
Credential validation utilities for Golestan login.
"""

import re
from typing import Tuple, Optional


def validate_student_number(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate student number format.
    
    Args:
        username: Student number to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "شماره دانشجویی نمی‌تواند خالی باشد."
    
    username = username.strip()
    
    if len(username) < 8 or len(username) > 12:
        return False, "شماره دانشجویی باید بین 8 تا 12 رقم باشد."
    
    if not username.isdigit():
        return False, "شماره دانشجویی باید فقط شامل اعداد باشد."
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password format.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "رمز عبور نمی‌تواند خالی باشد."
    
    password = password.strip()
    
    if len(password) < 4:
        return False, "رمز عبور باید حداقل 4 کاراکتر باشد."
    
    if len(password) > 50:
        return False, "رمز عبور نمی‌تواند بیشتر از 50 کاراکتر باشد."
    
    return True, None


def validate_credentials(username: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate both username and password.
    
    Args:
        username: Student number
        password: Password
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    username_valid, username_error = validate_student_number(username)
    if not username_valid:
        return False, username_error
    
    password_valid, password_error = validate_password(password)
    if not password_valid:
        return False, password_error
    
    return True, None

