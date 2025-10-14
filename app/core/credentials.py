#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Secure local credential management for Golestoon Class Planner.

This module handles secure storage and retrieval of Golestan credentials
using local files with appropriate permission hardening.
"""

import os
import json
import stat
import platform
from pathlib import Path
from typing import Optional, Dict
import base64
import hashlib

# Local credentials file path
LOCAL_CREDENTIALS_FILE = Path(__file__).parent.parent / 'data' / 'local_credentials.json'

# Fallback implementation without cryptography dependency
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

def load_local_credentials() -> Optional[Dict[str, str]]:
    """
    Load local credentials from the secure local file.
    
    Returns:
        dict: {"student_number": "...", "password": "..."} or None if not found/invalid
    """
    try:
        if not LOCAL_CREDENTIALS_FILE.exists():
            return None
            
        # Check file permissions
        check_file_permissions(LOCAL_CREDENTIALS_FILE)
        
        with open(LOCAL_CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Validate required fields
        if 'student_number' not in data or 'password' not in data:
            return None
            
        # Handle encrypted credentials (optional feature)
        if data.get('encrypted', False):
            # TODO: Implement decryption when passphrase is available
            # For now, return None to force re-entry
            return None
            
        return {
            'student_number': data['student_number'],
            'password': data['password']
        }
        
    except Exception as e:
        # Log error but don't expose sensitive information
        from .logger import setup_logging
        logger = setup_logging()
        logger.error(f"Error loading local credentials: {type(e).__name__}")
        return None

def save_local_credentials(student_number: str, password: str, remember: bool = True) -> bool:
    """
    Save credentials to the local file with appropriate security measures.
    
    Args:
        student_number: Golestan student number
        password: Golestan password
        remember: Whether to save credentials (default: True)
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    if not remember:
        return True
        
    try:
        # Create data directory if it doesn't exist
        LOCAL_CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare credential data
        # Note: Encryption is optional and disabled by default as per requirements
        data = {
            'student_number': student_number,
            'password': password,
            'encrypted': False  # Default to plaintext with file permission hardening
        }
        
        # Write credentials to file
        with open(LOCAL_CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Apply file permission hardening
        harden_file_permissions(LOCAL_CREDENTIALS_FILE)
        
        return True
        
    except Exception as e:
        # Log error but don't expose sensitive information
        from .logger import setup_logging
        logger = setup_logging()
        logger.error(f"Error saving local credentials: {type(e).__name__}")
        return False

def delete_local_credentials() -> bool:
    """
    Delete the local credentials file.
    
    Returns:
        bool: True if deleted successfully or file didn't exist, False on error
    """
    try:
        if LOCAL_CREDENTIALS_FILE.exists():
            LOCAL_CREDENTIALS_FILE.unlink()
        return True
    except Exception as e:
        # Log error
        from .logger import setup_logging
        logger = setup_logging()
        logger.error(f"Error deleting local credentials: {type(e).__name__}")
        return False

def harden_file_permissions(file_path: Path):
    """
    Apply appropriate file permissions to restrict access to the current user only.
    
    Args:
        file_path: Path to the file to harden
    """
    try:
        if platform.system() == 'Windows':
            # On Windows, set file attributes to be accessible only to current user
            # This is a basic approach; more sophisticated ACL management could be implemented
            try:
                import win32api
                import win32security
                import ntsecuritycon as con
                
                # Get current user SID
                user_sid = win32security.LookupAccountName('', win32api.GetUserName())[0]
                
                # Set DACL to allow only owner access
                sd = win32security.SECURITY_DESCRIPTOR()
                sd.Initialize()
                sd.SetSecurityDescriptorOwner(user_sid, False)
                
                # Create ACL allowing only owner full control
                acl = win32security.ACL()
                acl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, user_sid)
                sd.SetSecurityDescriptorDacl(1, acl, 0)
                
                # Apply security descriptor
                win32security.SetFileSecurity(str(file_path), win32security.DACL_SECURITY_INFORMATION, sd)
            except ImportError:
                # If win32 modules are not available, just ensure the file exists
                # Basic file permission hardening on Windows is limited without pywin32
                pass
            
        else:
            # On Unix-like systems, set file mode to 0o600 (owner read/write only)
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
            
    except Exception:
        # If permission hardening fails, log but continue
        # The file still has some protection by being in the app directory
        from .logger import setup_logging
        logger = setup_logging()
        logger.warning("Could not harden file permissions for credentials file")

def check_file_permissions(file_path: Path) -> bool:
    """
    Check if the credentials file has appropriate permissions.
    
    Args:
        file_path: Path to the credentials file
        
    Returns:
        bool: True if permissions are acceptable, False otherwise
    """
    try:
        if platform.system() == 'Windows':
            # Basic check on Windows
            # More thorough ACL checking could be implemented
            return True
        else:
            # On Unix-like systems, check if file mode is 0o600 or stricter
            file_stat = os.stat(file_path)
            mode = file_stat.st_mode
            # Check if only owner has read/write permissions
            return (mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0
            
    except Exception:
        return False

def _derive_key_from_passphrase(passphrase: str) -> bytes:
    """
    Derive a 32-byte key from a passphrase using SHA-256.
    
    Args:
        passphrase: User passphrase
        
    Returns:
        bytes: 32-byte key suitable for Fernet
    """
    return base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())

def encrypt_credentials(student_number: str, password: str, passphrase: str) -> Dict[str, str]:
    """
    Encrypt credentials using a user-provided passphrase.
    
    Args:
        student_number: Golestan student number
        password: Golestan password
        passphrase: User-provided passphrase for encryption
        
    Returns:
        dict: Encrypted credentials data
    """
    if not CRYPTO_AVAILABLE:
        # Fallback to plaintext if cryptography is not available
        return {
            'student_number': student_number,
            'password': password,
            'encrypted': False
        }
    
    try:
        # Derive key from passphrase
        key = _derive_key_from_passphrase(passphrase)
        cipher_suite = Fernet(key)
        
        # Encrypt credentials
        encrypted_student_number = cipher_suite.encrypt(student_number.encode()).decode()
        encrypted_password = cipher_suite.encrypt(password.encode()).decode()
        
        return {
            'student_number': encrypted_student_number,
            'password': encrypted_password,
            'encrypted': True,
            'passphrase_required': True
        }
    except Exception:
        # Fallback to plaintext on encryption failure
        return {
            'student_number': student_number,
            'password': password,
            'encrypted': False
        }

def decrypt_credentials(encrypted_data: Dict[str, str], passphrase: str) -> Optional[Dict[str, str]]:
    """
    Decrypt credentials using a user-provided passphrase.
    
    Args:
        encrypted_data: Encrypted credentials data
        passphrase: User-provided passphrase for decryption
        
    Returns:
        dict: Decrypted credentials or None on failure
    """
    if not CRYPTO_AVAILABLE or not encrypted_data.get('encrypted', False):
        return encrypted_data
    
    try:
        # Derive key from passphrase
        key = _derive_key_from_passphrase(passphrase)
        cipher_suite = Fernet(key)
        
        # Decrypt credentials
        student_number = cipher_suite.decrypt(encrypted_data['student_number'].encode()).decode()
        password = cipher_suite.decrypt(encrypted_data['password'].encode()).decode()
        
        return {
            'student_number': student_number,
            'password': password
        }
    except Exception:
        return None