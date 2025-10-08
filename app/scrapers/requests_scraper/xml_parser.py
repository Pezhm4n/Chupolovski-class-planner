import xml.etree.ElementTree as ET
import json
import re

def normalize_to_persian(text):
    """Convert Arabic characters to Persian equivalents."""
    if not text:
        return text

    # Arabic to Persian character mappings
    replacements = {
        'ي': 'ی',
        'ك': 'ک',
    }

    for arabic, persian in replacements.items():
        text = text.replace(arabic, persian)

    return text

def normalize_day_name(day_name):
    """
    Normalize Persian weekday names to standard format matching config.DAYS.
    Handles variations in spacing, ZWNJ, and character encoding.
    
    Args:
        day_name (str): Raw day name from parsed data
        
    Returns:
        str: Normalized day name matching config.DAYS format
    """
    if not day_name:
        return day_name
    
    # First normalize to Persian characters (Arabic → Persian)
    day_name = normalize_to_persian(day_name)
    
    # Remove all whitespace and ZWNJ to create base form
    day_clean = day_name.replace(' ', '').replace('\u200c', '').strip()
    
    # Map all variations to standard format with proper ZWNJ
    day_mapping = {
        'شنبه': 'شنبه',
        'یکشنبه': 'یکشنبه',
        'یکشنبه': 'یکشنبه',      # Alternative spelling
        'دوشنبه': 'دوشنبه',
        'دوشنبه': 'دوشنبه',      # Alternative spelling
        'سهشنبه': 'سه\u200cشنبه',   # Add ZWNJ
        'سهشنبه': 'سه\u200cشنبه',   # Alternative spelling
        'چهارشنبه': 'چهارشنبه',
        'چهارشنبه': 'چهارشنبه',  # Alternative spelling
        'پنجشنبه': 'پنج\u200cشنبه', # Add ZWNJ
        'پنجشنبه': 'پنج\u200cشنبه', # Alternative spelling
        'جمعه': 'جمعه'
    }
    
    # Return normalized form
    normalized = day_mapping.get(day_clean, day_name)
    
    return normalized

def parse_courses_from_xml(xml_string, output_path):
    with open('output.txt', 'w', encoding='utf-8') as f:
        f.write(xml_string)

    root = ET.fromstring(xml_string)
    courses = {}

    for row in root.findall("row"):
        attrib = row.attrib

        # Fill with fallback/defaults if missing
        fac_name = attrib.get("B4", "")
        dept_name = attrib.get("B6", "")

        courses.setdefault(fac_name, {}).setdefault(dept_name, [])

        credits = 0
        try:
            credits = int(re.sub(r'<.*?>', '', attrib.get("C3", "0")))
        except:
            pass

        schedule_text = normalize_to_persian(attrib.get("C12", ""))

        schedule = []

        if schedule_text and schedule_text.strip():
            # Persian weekday names with variations
            day_pattern = r'(?:شنبه|یک\s*شنبه|يك\s*شنبه|یکشنبه|يكشنبه|دو\s*شنبه|دوشنبه|سه\s*شنبه|سهشنبه|چهار\s*شنبه|چهارشنبه|پنج\s*شنبه|پنجشنبه|جمعه)'

            # Split by "درس(ت):" or "درس(ع):" or comma before درس
            schedule_entries = re.split(r'(?:درس\([تع]\)):\s*|،\s*(?=درس\([تع]\):)', schedule_text)
            schedule_entries = [e.strip() for e in schedule_entries if e.strip()]

            for entry in schedule_entries:
                # Find all day-time patterns
                time_matches = list(re.finditer(
                    rf'({day_pattern})\s+(\d{{2}}:\d{{2}})-(\d{{2}}:\d{{2}})(?:\s*([فز]))?',
                    entry
                ))

                if not time_matches:
                    continue

                # Extract location - everything after "مکان:" until comma or end
                location_match = re.search(r'مکان:\s*(.+?)(?:،|$)', entry)
                location = location_match.group(1).strip() if location_match else ""

                for match in time_matches:
                    day_raw = re.sub(r'\s+', ' ', match.group(1)).strip()
                    day_normalized = normalize_day_name(day_raw)  # ← ADD THIS
                    
                    schedule.append({
                        "day": day_normalized,  # ← Use normalized instead of day_raw
                        "start": match.group(2),
                        "end": match.group(3),
                        "parity": match.group(4) or "",
                        "location": location
                    })

        exam_time = ""
        exam_text = attrib.get("C13", "")
        m = re.search(r"(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}-\d{2}:\d{2})", exam_text)
        if m:
            exam_time = f"{m.group(1)} - {m.group(2)}"

        c25 = attrib.get("C25", "")
        c15 = attrib.get("C15", "")
        c16 = attrib.get("C16", "")

        if c16.strip() == "بي اثر":
            enrollment_conditions = c15.rstrip('، ')
        else:
            enrollment_conditions = c15 + c16

        course = {
            "code": attrib.get("C1", ""),
            "name": normalize_to_persian(attrib.get("C2", "")),
            "credits": credits,
            "gender": attrib.get("C10", ""),
            "capacity": attrib.get("C7", ""),
            "instructor": normalize_to_persian(attrib.get("C11", "اساتید گروه آموزشی")).replace("<BR>", "").strip(),
            "schedule": schedule,  # Already normalized during parsing
            "enrollment_conditions": normalize_to_persian(enrollment_conditions).replace("<BR>", "").strip(),
            "description": normalize_to_persian(c25).replace("<BR>", ""),
            "exam_time": exam_time
        }

        courses[fac_name][dept_name].append(course)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)

    return True
