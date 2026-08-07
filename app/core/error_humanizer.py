#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized Error Humanizer module for Golestoon Class Planner.
Converts raw technical exceptions, HTTP errors, and DB traces into clear, warm, and helpful Persian text for end users.
"""

import logging

logger = logging.getLogger("golestoon.error_humanizer")

def humanize_error(exception_or_msg, default_message: str = "برنامه با مشکل مواجه شد. لطفاً دوباره تلاش کنید.") -> str:
    """
    Converts a technical exception object or raw error string into a friendly Persian user message.
    Log the raw technical details internally.
    """
    raw_str = str(exception_or_msg) if exception_or_msg else ""
    logger.error(f"[Raw Error Logged]: {raw_str}")

    if not raw_str:
        return default_message

    lower_str = raw_str.lower()

    # Network & Connection Errors
    if "connection" in lower_str or "failed to connect" in lower_str or "unreachable" in lower_str or "name or service not known" in lower_str:
        return "ارتباط با اینترنت یا سرور برقرار نشد. لطفاً اتصال اینترنت خود را بررسی کنید."
    
    if "timeout" in lower_str or "timed out" in lower_str:
        return "پاسخی از سرور دریافت نشد. لطفاً چند لحظه بعد مجدداً تلاش کنید."

    # Authentication & Authorization Errors (HTTP 401 / 403)
    if "401" in lower_str or "unauthorized" in lower_str or "credentials" in lower_str:
        return "نشست شما منقضی شده است یا اطلاعات ورود اشتباه است. لطفاً دوباره وارد شوید."
    
    if "403" in lower_str or "forbidden" in lower_str:
        return "شما دسترسی لازم برای انجام این کار را ندارید."

    # HTTP 404
    if "404" in lower_str or "not found" in lower_str:
        return "اطلاعات مورد نظر یافت نشد."

    # Server Errors (HTTP 500 / 502 / 503)
    if "500" in lower_str or "502" in lower_str or "503" in lower_str or "internal server error" in lower_str:
        return "سرور در حال حاضر پاسخگو نیست. لطفاً چند دقیقه دیگر امتحان کنید."

    # File System / Permission Errors
    if "permission denied" in lower_str or "errno 13" in lower_str:
        return "دسترسی به فایل یا پوشه انتخابی امکان‌پذیر نیست. بررسی کنید فایل در برنامه دیگری باز نباشد."
    
    if "no space left" in lower_str or "disk full" in lower_str:
        return "فضای کافی روی ذخیره‌ساز دستگاه شما وجود ندارد."

    # Database / Storage Errors
    if "sqlite" in lower_str or "database" in lower_str or "operationalerror" in lower_str or "corrupt" in lower_str:
        return "اطلاعات محلی برنامه با مشکل مواجه شده است. می‌توانید از بخش تنظیمات پیشرفته نسخه پشتیبان را بازیابی کنید."

    return default_message
