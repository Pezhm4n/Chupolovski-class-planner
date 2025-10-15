import xml.etree.ElementTree as ET
import json
import re
from bs4 import BeautifulSoup
from decimal import Decimal
from datetime import datetime
from app.scrapers.requests_scraper.models import Student, SemesterRecord, CourseEnrollment

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

def parse_courses_from_xml(xml_string):

    root = ET.fromstring(xml_string)
    courses = {}

    for row in root.findall("row"):
        attrib = row.attrib

        fac_name = normalize_to_persian(attrib.get("B4", ""))
        dept_name = normalize_to_persian(attrib.get("B6", ""))

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

    return courses

def parse_student_info(html_response):
    """Extract student information from the response HTML and return Student object"""

    soup = BeautifulSoup(html_response, 'html.parser')
    script = soup.find('script', {'id': 'clientEventHandlersJS'})

    if not script:
        return None

    script_text = script.string

    # Helper function to extract JavaScript variable values
    def extract_var(var_name):
        pattern = rf"{var_name}\s*=\s*'([^']*)';"
        match = re.search(pattern, script_text)
        return match.group(1) if match else ""

    # Extract all fields
    name = extract_var("F51851")  # شاه محمدي شايان (full name)
    father_name = extract_var("F34501")
    faculty = extract_var("F61151")
    department = extract_var("F16451")
    major = extract_var("F17551")
    degree_level = extract_var("F41301")
    study_type = extract_var("F41351")
    enrollment_status = extract_var("F43301")
    registration_permission = extract_var("F42251") == "دارد"

    # Extract image - F15871 contains the base64 image
    image_b64 = extract_var("F15871").split(',')[1]  # This is the student photo

    # Numeric fields with defaults
    overall_gpa_str = extract_var("F41701")
    total_units_str = extract_var("F41801")
    total_probation_str = extract_var("F42401")
    consecutive_probation_str = extract_var("F42451")
    special_probation_str = extract_var("F42371")

    # Create and return Student object
    student = Student(
        student_id="",  # Fill this if you have it from elsewhere
        name=name,
        father_name=father_name,
        faculty=faculty,
        department=department,
        major=major,
        degree_level=degree_level,
        study_type=study_type,
        enrollment_status=enrollment_status,
        registration_permission=registration_permission,
        overall_gpa=Decimal(overall_gpa_str) if overall_gpa_str else None,
        total_units_passed=Decimal(total_units_str) if total_units_str else Decimal('0.00'),
        total_probation=int(total_probation_str) if total_probation_str else 0,
        consecutive_probation=int(consecutive_probation_str) if consecutive_probation_str else 0,
        special_probation=int(special_probation_str) if special_probation_str else 0,
        semesters=[],  # Will be populated later
        updated_at=datetime.now(),
        image_b64=image_b64
    )

    return student


def parse_semester_data(html_response):
    """
    Parse semester information and courses from HTML response.
    """
    import re
    import xml.etree.ElementTree as ET
    from decimal import Decimal

    # Extract JavaScript variables
    def extract_var(var_name):
        pattern = rf"{var_name}\s*=\s*'([^']*)';"
        match = re.search(pattern, html_response)
        return match.group(1) if match else ""

    # Helper to safely convert to Decimal
    def safe_decimal(value, default='0.00'):
        """Convert value to Decimal, handling empty strings and None"""
        if not value or value.strip() == '':
            return Decimal(default)
        try:
            return Decimal(value)
        except (ValueError, TypeError):
            return Decimal(default)

    def compute_gpa_from_courses(courses_list):
        """Calculate GPA from courses, skipping courses without grades"""
        total_points = Decimal('0.00')
        total_units = Decimal('0.00')

        for c in courses_list:
            # Skip courses that don't have a grade yet
            if c.grade is None:
                continue

            total_units += c.course_units
            total_points += c.grade * c.course_units

        if total_units > 0:
            return (total_points / total_units).quantize(Decimal('0.01'))
        return Decimal('0.00')

    # Get semester metadata
    semester_number = extract_var("F43501")
    semester_description = extract_var("F57551")
    semester_status = extract_var("F44551")
    semester_type = extract_var("F43551")
    probation_status = extract_var("F44151")

    # Extract T01XML (semester summary info)
    t01_pattern = r"T01XML\s*=\s*'([^']*)';"
    t01_match = re.search(t01_pattern, html_response)
    semester_gpa = Decimal('0.00')
    units_taken = Decimal('0.00')
    units_passed = Decimal('0.00')
    cumulative_gpa = Decimal('0.00')
    cumulative_units_passed = Decimal('0.00')
    units_failed_str = Decimal('0.00')
    units_dropped_str = Decimal('0.00')

    if t01_match:
        t01_xml = t01_match.group(1)
        try:
            root = ET.fromstring(t01_xml)
            nodes = root.findall('N')

            if len(nodes) >= 1:
                # First row: current semester stats
                first_node = nodes[0]
                gpa_str = first_node.get('F4360', '').strip()
                semester_gpa = safe_decimal(gpa_str) if gpa_str else None
                units_taken = safe_decimal(first_node.get('F4365'))
                units_passed = safe_decimal(first_node.get('F4370'))
                units_failed_str = extract_var("F4385")
                units_dropped_str = extract_var("F4375")

            if len(nodes) >= 2:
                # Second row: cumulative stats
                second_node = nodes[1]
                cumulative_gpa = safe_decimal(second_node.get('F4360', '0.00'))
                cumulative_units_passed = safe_decimal(second_node.get('F4370', '0.00'))
        except (ET.ParseError, ValueError) as e:
            print(f"Warning: Failed to parse T01XML: {e}")

    # Extract T02XML (courses)
    t02_pattern = r"T02XML\s*=\s*'([^']*)';"
    t02_match = re.search(t02_pattern, html_response)

    courses = []

    if t02_match:
        t02_xml = t02_match.group(1)
        try:
            root = ET.fromstring(t02_xml)

            for node in root.findall('N'):
                course_code = node.get('F5560', '') + '_' + node.get('F5565', '')
                course_name = node.get('F0200', '')
                course_units = node.get('F0205', '0')
                course_type = node.get('F3952', '')
                grade_state = node.get('F3965', '')
                grade_str = node.get('F3945', '').strip()

                # Create course with grade (numeric or None)
                course = CourseEnrollment(
                    course_code=course_code,
                    course_name=course_name,
                    course_units=safe_decimal(course_units),
                    course_type=course_type,
                    grade_state=grade_state,
                    grade=safe_decimal(grade_str) if grade_str else None
                )

                courses.append(course)

        except (ET.ParseError, ValueError) as e:
            print(f"Warning: Failed to parse T02XML: {e}")

    # Recalculate GPA if needed
    if semester_gpa == Decimal('0.00'):
        semester_gpa = compute_gpa_from_courses(courses)

    # Create and populate SemesterRecord
    semester = SemesterRecord(
        semester_id=int(semester_number) if semester_number else 0,
        semester_description=semester_description,
        semester_gpa=semester_gpa,
        units_taken=units_taken,
        units_passed=units_passed,
        units_failed=safe_decimal(units_failed_str),
        units_dropped=safe_decimal(units_dropped_str),
        cumulative_gpa=cumulative_gpa,
        cumulative_units_passed=cumulative_units_passed,
        probation_status=probation_status,
        semester_status=semester_status,
        semester_type=semester_type,
        courses=courses
    )

    return semester

def extract_semester_ids(html_response):
    """Extract semester IDs from T01XML in response"""
    import re
    import xml.etree.ElementTree as ET

    # Find T01XML variable
    pattern = r"T01XML\s*=\s*'([^']*)';"
    match = re.search(pattern, html_response)

    if not match:
        return []

    xml_string = match.group(1)

    try:
        root = ET.fromstring(xml_string)
        semester_ids = []

        for node in root.findall('N'):
            semester_id = node.get('F4350')  # e.g., "4021", "4022", etc.
            if semester_id:
                semester_ids.append(semester_id)

        return semester_ids
    except ET.ParseError:
        return []
