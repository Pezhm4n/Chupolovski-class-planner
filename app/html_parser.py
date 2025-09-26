import json
import re
from bs4 import BeautifulSoup


def parse_courses_from_html(html, output_path):
    """
    Parses HTML and creates the complete courses structure with data in one pass.
    No structure file needed - everything is built dynamically from HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    courses = {}

    for row in soup.select("tr:not(.DTitle)"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if not cells or len(cells) < 17:
            continue

        try:
            # Get faculty and department names directly from HTML columns
            fac_name = cells[3]  # Column 3: faculty name
            dept_name = cells[5]  # Column 5: department name
        except IndexError:
            continue

        # Create structure on-the-fly if not exists
        courses.setdefault(fac_name, {}).setdefault(dept_name, [])

        # Parse course data
        try:
            credits = int(cells[8])
        except:
            credits = 0

        schedule = []
        for m in re.finditer(r"(?P<day>\S+)\s+(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})(?:\s*(?P<parity>[فز])?)",
                             cells[15]):
            schedule.append({
                "day": m.group("day"),
                "start": m.group("start"),
                "end": m.group("end"),
                "parity": m.group("parity") or ""
            })


        location = ""
        location_match = re.search(r"مکان:\s*(.+?)(?:\s*تاريخ:|$)", cells[15])
        if location_match:
            location = location_match.group(1).strip()

        exam_time = ""
        m = re.search(r"(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}-\d{2}:\d{2})", cells[16])
        if m:
            exam_time = f"{m.group(1)} - {m.group(2)}"

        course = {
            "code": cells[6],
            "name": cells[7],
            "credits": credits,
            "gender": cells[13],
            "capacity": cells[10],
            "instructor": (cells[14] or "اساتيد گروه آموزشي").strip(),
            "schedule": schedule,
            "location": location,
            "description": cells[22] + ' - ' + cells[17] if cells[22] and cells[17] else cells[22] + cells[17] ,
            "exam_time": exam_time
        }

        courses[fac_name][dept_name].append(course)

    # Save final result
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)

    return True


# faculties = {
#   11: 'علوم و تحقيقات اسلامي',
#   12: 'ادبيات و علوم انساني',
#   13: 'علوم اجتماعي',
#   14: 'علوم پايه',
#   16: 'فني و مهندسي',
#   17: 'كشاورزي و منابع طبيعي',
#   18: 'معماري و شهرسازي'
# }
#
# departments = {
#   11: {
#     19: 'تاريخ  تمدن و فرهنگ ملل اسلامي',
#     20: 'فقه و حقوق اسلامي',
#     21: 'فلسفه و حكمت اسلامي',
#     22: 'علوم قرآني و حديث',
#     42: 'معارف اسلامي'
#   },
#   12: {
#     14: 'تاريخ',
#     26: 'زبان و ادبيات عربي',
#     30: 'زبانشناسي و آزفا',
#     34: 'فلسفه',
#     38: 'زبان انگليسي'
#   },
#   13: {
#     0: "مجازي",
#     10: "بدون گروه",
#     16: "علوم ورزشي",
#     18: "حسابداري",
#     22: "حقوق",
#     24: "روانشناسي",
#     32: "علوم سياسي",
#     34: "آينده پژوهي",
#     36: "مديريت صنعتي",
#     38: "جامعه شناسي - پژوهشگري"
#   },
#   14: {
#     0: "مجازي",
#     10: "بدون گروه - علوم پايه",
#     11: "آزاد",
#     12: "آمار",
#     14: "رياضي محض",
#     15: "رياضي كاربردي",
#     16: "زمين شناسي",
#     18: "شيمي",
#     22: "فيزيك"
#   },
#   16: {
#     11: "مهندسي برق - كنترل",
#     12: "مهندسي برق - مخابرات",
#     13: "مهندسي برق - قدرت",
#     14: "مهندسي عمران",
#     15: "مهندسي عمران - مكانيك خاك و پي",
#     16: "مهندسي عمران - برنامه ريزي حمل و نقل",
#     18: "كامپيوتر",
#     24: "معدن",
#     26: "مهندسي مكانيك",
#     28: "مهندسي مواد"
#   },
#   17: {
#     10: "ژنتيك و به نژادي",
#     12: "مهندسي بيوتكنولوژي",
#     14: "مهندسي علوم باغباني",
#     16: "علوم و مهندسي آب"
#   },
#   18: {
#     12: "مهندسي شهرسازي",
#     14: "مهندسي معماري",
#     16: "مرمت و احياي بناهاي تاريخي"
#   }
# }

