import xml.etree.ElementTree as ET
import json
import re
import persianutils as pu

def parse_courses_from_xml(xml_string, output_path):

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

        schedule = []
        schedule_text = attrib.get("C12", "")
        for m in re.finditer(r"(?P<day>\S+)\s+(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})(?:\s*(?P<parity>[فز])?)",
                             schedule_text):
            schedule.append({
                "day": m.group("day"),
                "start": m.group("start"),
                "end": m.group("end"),
                "parity": m.group("parity") or ""
            })

        location = ""
        location_match = re.search(r"مکان:\s*(.+?)(?:\s*تاريخ:|$)", schedule_text)
        if location_match:
            location = location_match.group(1).strip()

        exam_time = ""
        exam_text = attrib.get("C13", "")
        m = re.search(r"(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}-\d{2}:\d{2})", exam_text)
        if m:
            exam_time = f"{m.group(1)} - {m.group(2)}"

        c25 = attrib.get("C25", "")
        c15 = attrib.get("C15", "")
        c16 = attrib.get("C16", "")

        # Apply lstrip to c15 only if c16 equals 'بي اثر'
        if c16.strip() == "بي اثر":
            c15 = c15.lstrip(' ،')

        if c25 and c15:
            description = f"{c25} - {c15}{attrib.get('C16', '')}"
        else:
            description = f"{c25}{c15}"

        course = {
            "code": attrib.get("C1", ""),
            "name": attrib.get("C2", ""),
            "credits": credits,
            "gender": attrib.get("C10", ""),
            "capacity": attrib.get("C7", ""),
            "instructor": attrib.get("C11", "اساتيد گروه آموزشي").strip().replace("<BR>", ""),
            "schedule": schedule,
            "location": location,
            "description": description.replace("<BR>", ""),
            "exam_time": exam_time
        }

        courses[fac_name][dept_name].append(course)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)

    return True
