import re
import time
from random import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.cookies import create_cookie
from pathlib import Path
from app.data.student_db import StudentDatabase
from app.scrapers.requests_scraper.parsers import parse_courses_from_xml, parse_student_info, parse_semester_data, extract_semester_ids
import os
from app.captcha_solver.predict import predict

class GolestanSession:
    """Manages Golestan session and authentication."""

    def __init__(self):
        self.session = requests.Session()
        self.session_id = None
        self.lt = None
        self.u = None
        self.tck = None
        self.ctck = None
        self.seq = 1
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            }

    def _add_cookies(self, cookie_tuples):
        """Clear and add cookies to session."""
        self.session.cookies.clear()
        for name, value in cookie_tuples:
            cookie_obj = create_cookie(name=name, value=value, domain="golestan.ikiu.ac.ir")
            self.session.cookies.set_cookie(cookie_obj)

    def _extract_aspnet_fields(self, html):
        """Extract ASP.NET form fields from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        fields = {}
        fields['viewstate'] = soup.find('input', {'name': '__VIEWSTATE'})['value']
        fields['viewstategen'] = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
        fields['eventvalidation'] = soup.find('input', {'name': '__EVENTVALIDATION'})['value']
        ticket_box = soup.find('input', {'name': 'TicketTextBox'})
        fields['ticket'] = ticket_box.get('value') if ticket_box else None
        return fields

    def _extract_xmldat(self, text):
        """Extract xmlDat value from response text."""
        pattern = r'xmlDat\s*=\s*["\'](.*?)["\'];'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else None

    def _safe_request(self, method, url, **kwargs):
        """
        Perform HTTP request with error handling.
        
        Args:
            method: 'get' or 'post'
            url: Request URL
            **kwargs: Additional arguments for requests.get/post
            
        Returns:
            Response object
            
        Raises:
            RuntimeError: With appropriate error prefix (SSL_ERROR, CONNECTION_ERROR, etc.)
        """
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        
        try:
            if method.lower() == 'get':
                return self.session.get(url, headers=self.headers, **kwargs)
            elif method.lower() == 'post':
                return self.session.post(url, headers=self.headers, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.SSLError as e:
            # Check if it's an SSL verification error (likely VPN/proxy issue)
            error_str = str(e).lower()
            if 'certificate' in error_str or 'ssl' in error_str or 'verify' in error_str:
                raise RuntimeError("SSL_ERROR: VPN or proxy detected. Please disable VPN/proxy and try again.")
            raise RuntimeError("SSL_ERROR: " + str(e))
        except requests.exceptions.ConnectionError as e:
            # Check if it's a connection error that might be due to SSL/VPN
            error_str = str(e).lower()
            if 'ssl' in error_str or 'certificate' in error_str:
                raise RuntimeError("SSL_ERROR: VPN or proxy detected. Please disable VPN/proxy and try again.")
            raise RuntimeError("CONNECTION_ERROR: " + str(e))
        except requests.exceptions.Timeout as e:
            raise RuntimeError("TIMEOUT_ERROR: " + str(e))
        except Exception as e:
            raise RuntimeError("UNKNOWN_ERROR: " + str(e))

    def authenticate(self, username=None, password=None, max_attempts=5):
        """
        Authenticate with Golestan system.

        Args:
            username: Username for login (defaults to env USERNAME)
            password: Password for login (defaults to env PASSWORD)
            max_attempts: Maximum captcha solving attempts

        Returns:
            bool: True if authentication successful, False otherwise
        """
        
        # Get the path to the scrapers directory where .env should be located
        app_dir = Path(__file__).resolve().parent.parent.parent
        env_path = app_dir / '.env'
        
        # Load the .env file from the correct location
        load_dotenv(dotenv_path=env_path, override=True)

        self.username = username or os.getenv("USERNAME")
        password = password or os.getenv("PASSWORD")

        # Get session ID
        url = "https://golestan.ikiu.ac.ir/_templates/unvarm/unvarm.aspx?typ=1"
        response = self._safe_request('get', url)
        self.session_id = self.session.cookies.get("ASP.NET_SessionId")

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", ""), ("ft", ""), ("lt", ""),
            ("seq", ""), ("su", ""), ("u", "")
        ]
        self._add_cookies(cookie_tuples)

        # Get login page
        get_url = 'https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/AuthUser.aspx?fid=0;1&tck=&&&lastm=20240303092318'
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)

        # Step 4: Initial POST
        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'TxtMiddle': '<r/>',
            'Fm_Action': '00',
            'Frm_Type': '', 'Frm_No': '', 'TicketTextBox': ''
        }

        post_url = 'https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/AuthUser.aspx?fid=0%3b1&tck=&&&lastm=20240303092318'
        post_resp = self._safe_request('post', post_url, data=payload)
        aspnet_fields = self._extract_aspnet_fields(post_resp.text)

        # Captcha solving loop
        for i in range(max_attempts):
            print(f"🔄 Authentication attempt {i + 1}/{max_attempts}...")

            # Get captcha
            captcha_url = f"https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/captcha.aspx?{random()}"
            resp = self._safe_request('get', captcha_url, stream=True)

            if resp.status_code == 200:
                print("✅ Captcha image received. Running recognition...")
                captcha_text = predict(resp.content)
            else:
                print("❌ Failed to download captcha")
                continue  # Skips to next loop iteration

            payload = {
                '__VIEWSTATE': aspnet_fields['viewstate'],
                '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
                '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
                'TxtMiddle': f'<r F51851="" F80351="{self.username}" F80401="{password}" F51701="{captcha_text}" F83181="1" F51602="" F51803="0" F51601="1"/>',
                'Fm_Action': '09',
                'Frm_Type': '', 'Frm_No': '', 'TicketTextBox': ''
            }

            resp_post = self._safe_request('post', post_url, data=payload)

            # Check if login successful
            self.lt = self.session.cookies.get("lt")
            self.u = self.session.cookies.get("u")

            if self.lt and self.u:
                print(f"✅ Authentication successful on attempt {i + 1}")
                aspnet_fields = self._extract_aspnet_fields(resp_post.text)
                self.tck = aspnet_fields['ticket']
                self.session_id = self.session.cookies.get("ASP.NET_SessionId", domain="golestan.ikiu.ac.ir")
                break
            else:
                print(f"❌ Failed attempt {i + 1}: Invalid captcha or credentials")
                time.sleep(1)
                continue
        else:
            print("🚫 All authentication attempts failed")
            # If we've tried max_attempts times and still failed, 
            # it's likely due to incorrect username/password or captcha issues
            raise RuntimeError("CAPTCHA_FAILED: Authentication failed. Please check your username and password.")

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '1'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("stdno", ''),
            ("su", '0'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        rnd = random()
        get_url = f'https://golestan.ikiu.ac.ir/Forms/F0213_PROCESS_SYSMENU/F0213_01_PROCESS_SYSMENU_Dat.aspx?r={rnd}&fid=0;11130&b=&l=&tck={self.tck}&&lastm=20240303092316'
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)
        ticket = aspnet_fields['ticket']

        self.seq += 1
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '11130'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '00', "Frm_Type": "", "Frm_No": "",
            "TicketTextBox": ticket, "XMLStdHlp": "",
            "TxtMiddle": "<r/>", 'ex': ''
        }

        post_url = f'https://golestan.ikiu.ac.ir/Forms/F0213_PROCESS_SYSMENU/F0213_01_PROCESS_SYSMENU_Dat.aspx?r={rnd}&fid=0%3b11130&b=&l=&tck={self.tck}&&lastm=20240303092316'
        post_resp = self._safe_request('post', post_url, data=payload)
        aspnet_fields = self._extract_aspnet_fields(post_resp.text)
        self.tck = aspnet_fields['ticket']

        return True

    def fetch_courses(self, status='both'):
        """
        Fetch course data based on status.

        Args:
            status: 'available', 'unavailable', or 'both'

        Returns:
            dict: Contains 'available' and/or 'unavailable' course data
        """

        # Enter 102 and click
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '11130'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        rnd = random()
        get_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={rnd}&fid=1;102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)
        ticket = aspnet_fields['ticket']
        self.ctck = self.session.cookies.get('ctck')

        self.seq += 1
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("ctck", self.ctck), ("f", '102'), ("ft", '1'),
            ("lt", self.lt), ("seq", str(self.seq)),
            ("stdno", ''), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        payload = {
            "__VIEWSTATE": aspnet_fields['viewstate'],
            "__VIEWSTATEGENERATOR": aspnet_fields['viewstategen'],
            "__EVENTVALIDATION": aspnet_fields['eventvalidation'],
            "Fm_Action": "00", "Frm_Type": "", "Frm_No": "", "F_ID": "",
            "XmlPriPrm": "", "XmlPubPrm": "", "XmlMoredi": "",
            "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
            "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
            "TicketTextBox": ticket, "RepSrc": "", "ShowError": "",
            "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
        }

        post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
        post_resp = self._safe_request('post', post_url, data=payload)

        aspnet_fields = self._extract_aspnet_fields(post_resp.text)
        self.report_ticket = aspnet_fields['ticket']

        print("✅ Navigated to course report dashboard")

        # Click show result
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("ctck", self.ctck), ("f", '102'), ("ft", '1'),
            ("lt", self.lt), ("seq", str(self.seq)),
            ("su", '0'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        # XML parameters
        xml_pri_prm = """<Root><N UQID="48" id="4" F="" T=""/><N UQID="50" id="8" F="" T=""/><N UQID="52" id="12" F="" T=""/><N UQID="62" id="16" F="" T=""/><N UQID="14" id="18" F="" T=""/><N UQID="16" id="20" F="" T=""/><N UQID="18" id="22" F="" T=""/><N UQID="20" id="24" F="" T=""/><N UQID="22" id="26" F="" T=""/></Root>"""

        xml_pub_prm_template = """<Root><N id="4" F1="4041" T1="4041" F2="" T2="" A="" S="" Q="" B=""/><N id="5" F1="10" T1="10" F2="" T2="" A="0" S="1" Q="1" B="B"/><N id="6" F1="{}" T1="{}" F2="" T2="" A="" S="" Q="" B=""/><N id="12" F1="" T1="" F2="" T2="" A="0" S="1" Q="2" B="B"/><N id="16" F1="" T1="" F2="" T2="" A="0" S="1" Q="3" B="B"/><N id="22" F1="" T1="" F2="" T2="" A="0" S="" Q="6" B="S"/><N id="24" F1="" T1="" F2="" T2="" A="0" S="" Q="7" B="S"/><N id="30" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="32" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="36" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="38" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="40" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="44" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="45" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="46" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="48" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="52" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="56" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="64" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="68" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="99" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="100" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="101" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="103" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="104" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="105" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="107" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="112" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/></Root>"""

        results_data = {}

        if status in ['available', 'both']:
            print("📥 Fetching available courses...")
            payload = {
                "__VIEWSTATE": aspnet_fields['viewstate'],
                "__VIEWSTATEGENERATOR": aspnet_fields['viewstategen'],
                "__EVENTVALIDATION": aspnet_fields ['eventvalidation'],
                "Fm_Action": "09", "Frm_Type": "", "Frm_No": "", "F_ID": "",
                "XmlPriPrm": xml_pri_prm.replace('\n', ''),
                "XmlPubPrm": xml_pub_prm_template.format(1, 1).replace('\n', ''),
                "XmlMoredi": "<Root/>",
                "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
                "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
                "TicketTextBox": self.report_ticket, "RepSrc": "", "ShowError": "",
                "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
            }

            post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
            post_resp = self._safe_request('post', post_url, data=payload)

            xml_string = self._extract_xmldat(post_resp.text)
            if xml_string:
                results_data['available'] = xml_string
                print("✅ Available courses data retrieved")
            else:
                print("❌ Failed to extract available courses data")

            # Update state for next request
            aspnet_fields = self._extract_aspnet_fields(post_resp.text)
            self.report_ticket = aspnet_fields['ticket']
            self.ctck = self.session.cookies.get('ctck')

        # Fetch unavailable courses
        if status in ['unavailable', 'both']:
            print("📥 Fetching unavailable courses...")

            # Update cookies (just different ctck as previous request)
            cookie_tuples[1] = ("ctck", self.ctck)
            self._add_cookies(cookie_tuples)

            payload = {
                "__VIEWSTATE": aspnet_fields['viewstate'],
                "__VIEWSTATEGENERATOR": aspnet_fields['viewstategen'],
                "__EVENTVALIDATION": aspnet_fields['eventvalidation'],
                "Fm_Action": "09", "Frm_Type": "", "Frm_No": "", "F_ID": "",
                "XmlPriPrm": xml_pri_prm.replace('\n', ''),
                "XmlPubPrm": xml_pub_prm_template.format(0, 0).replace('\n', ''),
                "XmlMoredi": "<Root/>",
                "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
                "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
                "TicketTextBox": self.report_ticket, "RepSrc": "", "ShowError": "0",
                "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
            }

            post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
            post_resp = self._safe_request('post', post_url, data=payload)

            xml_string = self._extract_xmldat(post_resp.text)
            if xml_string:
                results_data['unavailable'] = xml_string
                print("✅ Unavailable courses data retrieved")
            else:
                print("❌ Failed to extract unavailable courses data")

        return results_data

    def fetch_student_info(self):
        """
        Scrape the 'اطلاعات جامع دانشجو' (Comprehensive Student Information) page.

        Returns:
            tuple: (Student, semester_ids, aspnet_fields)
              - Student: populated student information model
              - semester_ids: list of codes for each academic semester found
              - aspnet_fields: ASP.NET session/form fields, to be used for follow-up requests
        """

        self.rnd = random()
        get_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0;12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)
        ticket = aspnet_fields['ticket']

        self.seq += 1
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '12310'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("sno", ""), ("stdno", ""),
            ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '00', "Frm_Type": "", "Frm_No": "",
            "TicketTextBox": ticket, "XMLStdHlp": "",
            "TxtMiddle": "<r/>", 'ex': ''
        }

        post_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0%3b12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        post_resp = self._safe_request('post', post_url, data=payload)
        aspnet_fields = self._extract_aspnet_fields(post_resp.text)
        ticket = aspnet_fields['ticket']

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '08', "Frm_Type": "", "Frm_No": "",
            "TicketTextBox": ticket, "XMLStdHlp": "",
            "TxtMiddle": f'<r F41251="{self.username}" F01951="" F02001=""/>', 'ex': ''
        }

        post_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0%3b12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        post_resp = self._safe_request('post', post_url, data=payload)
        aspnet_fields = self._extract_aspnet_fields(post_resp.text)

        # Parse student info
        student = parse_student_info(post_resp.text)
        student.student_id = self.username

        # Extract semester IDs for later requests
        semester_ids = extract_semester_ids(post_resp.text)

        return student, semester_ids, aspnet_fields

    def fetch_semester_courses(self, semester_id, aspnet_fields):
        """
        Fetch course details for a single semester, passing ASP.NET form fields.

        Args:
            semester_id: Semester code (e.g., '4021')
            aspnet_fields: ASP.NET hidden field values (dict)

        Returns:
            (SemesterRecord, next_results): SemesterRecord object and updated aspnet_fields for next request
        """

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '80', "Frm_Type": "", "Frm_No": "",
            "TicketTextBox": aspnet_fields['ticket'] , "XMLStdHlp": "",
            "TxtMiddle": f'<r F41251="{self.username}" F01951="" F02001="" F43501="{str(semester_id)}"/>', 'ex': ''
        }

        semester_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0%3b12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        resp = self._safe_request('post', semester_url, data=payload)
        next_results = self._extract_aspnet_fields(resp.text)

        # Parse the response to extract semester and course data
        semester_record = parse_semester_data(resp.text)

        return semester_record, next_results

def get_student_record(username=None, password=None, db=None):
    """
    Fetches student info, semesters, and courses as full transcript.
    Returns a Student object with all semesters and courses populated.

    Args:
        username: Student username for authentication
        password: Student password for authentication
        db: Optional StudentDatabase instance. If provided and student_id matches,
            it will be used. Otherwise, a new instance will be created.

    Returns:
        Student object with all data populated
    """
    golestan = GolestanSession()
    try:
        if not golestan.authenticate(username, password):
            raise RuntimeError("Authentication failed")

        # Fetch personal info
        student, semester_ids, aspnet_fields = golestan.fetch_student_info()

        print(f"📋 Semesters: {', '.join(semester_ids)} for student {student.name}")

        # Create or validate database instance
        if db is None or db.student_id != student.student_id:
            # Create new database instance for this student
            if db is not None:
                print(f"⚠️  Student ID mismatch: Database is for '{db.student_id}', "
                      f"creating new instance for '{student.student_id}'")
            db = StudentDatabase(student.student_id)

        # Fetch each semester and add to student
        for semester_id in semester_ids:
            semester_record, aspnet_fields = golestan.fetch_semester_courses(semester_id, aspnet_fields)
            if semester_record:
                student.semesters.append(semester_record)
                print(
                    f"✅ Semester {semester_id}: {len(semester_record.courses)} courses, GPA: {semester_record.semester_gpa}")
            else:
                print(f"❌ Failed to fetch semester {semester_id}")

        # Check if student already exists
        if db.student_exists():
            print(f"Student {student.student_id} already exists. Updating...")
        else:
            print(f"Creating new record for student {student.student_id}...")

        # Save student (this will update if exists)
        db.save_student(student)

        return student

    finally:
        golestan.session.close()

def get_courses(status='both', username=None, password=None, db=None):
    """
    Fetch course data from Golestan and store to database.

    Args:
        db: Existing CourseDatabase instance (if None, creates new one)
        status: 'available', 'unavailable', or 'both'
        username: Login username (defaults to env USERNAME)
        password: Login password (defaults to env PASSWORD)
    """
    from app.data.courses_db import CourseDatabase

    # Use provided database instance or create new one
    if db is None:
        db = CourseDatabase()

    golestan = GolestanSession()

    try:
        if not golestan.authenticate(username, password):
            raise RuntimeError("Authentication failed")

        results = golestan.fetch_courses(status)

        # Parse courses
        available_courses = None
        unavailable_courses = None

        if 'available' in results:
            available_courses = parse_courses_from_xml(results['available'])
            # Count actual courses (nested in faculty -> department structure)
            available_count = sum(
                len(courses)
                for faculty in available_courses.values()
                for courses in faculty.values()
            )
            print(f"✓ Parsed {available_count} available courses")

        if 'unavailable' in results:
            unavailable_courses = parse_courses_from_xml(results['unavailable'])
            # Count actual courses
            unavailable_count = sum(
                len(courses)
                for faculty in unavailable_courses.values()
                for courses in faculty.values()
            )
            print(f"✓ Parsed {unavailable_count} unavailable courses")

        # Store to database
        db.store_courses(available_courses, unavailable_courses)

        # Also save to JSON files for backward compatibility
        save_courses_to_json_files(available_courses, unavailable_courses)

    finally:
        golestan.session.close()

def save_courses_to_json_files(available_courses, unavailable_courses):
    """
    Save courses to JSON files for backward compatibility.
    
    Args:
        available_courses: Dictionary of available courses
        unavailable_courses: Dictionary of unavailable courses
    """
    import json
    import os
    from pathlib import Path
    
    try:
        # Get the app directory
        app_dir = Path(__file__).resolve().parent.parent.parent
        courses_data_dir = app_dir / 'data' / 'courses_data'
        
        # Ensure directory exists
        courses_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Save available courses
        if available_courses:
            available_file = courses_data_dir / 'available_courses.json'
            with open(available_file, 'w', encoding='utf-8') as f:
                json.dump(available_courses, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved available courses to {available_file}")
        
        # Save unavailable courses
        if unavailable_courses:
            unavailable_file = courses_data_dir / 'unavailable_courses.json'
            with open(unavailable_file, 'w', encoding='utf-8') as f:
                json.dump(unavailable_courses, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved unavailable courses to {unavailable_file}")
            
    except Exception as e:
        print(f"⚠ Warning: Failed to save courses to JSON files: {e}")
