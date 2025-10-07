"""
Asset loader module for the Chupolovski Class Planner application.

This module provides utilities for loading application assets such as icons,
images, and fonts from the assets directory.
"""

import os
from pathlib import Path

def get_asset_path(asset_type, filename):
    """
    Get the full path to an asset file.
    
    Args:
        asset_type (str): Type of asset ('icons', 'images', 'fonts')
        filename (str): Name of the asset file
        
    Returns:
        str: Full path to the asset file
    """
    app_dir = Path(__file__).parent.parent
    asset_path = app_dir / 'assets' / asset_type / filename
    return str(asset_path)

def load_icon(icon_name):
    """
    Load an icon from the assets/icons directory.
    
    Args:
        icon_name (str): Name of the icon file
        
    Returns:
        str: Path to the icon file
    """
    return get_asset_path('icons', icon_name)

def load_image(image_name):
    """
    Load an image from the assets/images directory.
    
    Args:
        image_name (str): Name of the image file
        
    Returns:
        str: Path to the image file
    """
    return get_asset_path('images', image_name)

def load_font(font_name):
    """
    Load a font from the assets/fonts directory.
    
    Args:
        font_name (str): Name of the font file
        
    Returns:
        str: Path to the font file
    """
    return get_asset_path('fonts', font_name)