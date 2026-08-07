import re
import time
from random import random
import requests
from typing import List, Dict, Any

from Demos.win32ts_logoff_disconnected import session
# from ...core.logger import setup_logging
# from ...core.course_utils import to_minutes
# from ...data.courses_db import get_db
from requests.cookies import create_cookie
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv
import os
from ...captcha_solver.predict import predict
from ...scrapers.requests_scraper.parsers import parse_student_info, extract_semester_ids, parse_semester_data, \
    parse_enrollment_data, parse_degree_details

# logger = setup_logging()


# def scrape_and_store_courses(status='both', username=None, password=None) -> List[Dict[str, Any]]:
#     """
#     Scrape course data from the source and store it in the database.
#     This function now uses the singleton database instance.
#
#     Args:
#         status: 'available', 'unavailable', or 'both' - for compatibility with old API
#         username: Username for authentication - not used in new API architecture
#         password: Password for authentication - not used in new API architecture
#     """
#     try:
#         # Log that we're using the new API architecture
#         logger.info(
#             "Using API architecture to fetch courses. Username and password arguments are not used in this mode.")
#
#         # In the new architecture, the database itself handles API fetching
#         # We'll just return the courses from the database after ensuring they're fresh
#         db = get_db()
#
#         # The database will handle fetching from API if needed
#         # We just need to make sure the data is fresh
#         db._ensure_fresh_data()
#
#         # Return all courses after ensuring they're up to date
#         courses = db.get_all_courses()
#         logger.info(f"Successfully retrieved {len(courses)} courses from database")
#         return courses
#     except Exception as e:
#         logger.error(f"Error in scrape_and_store_courses: {e}")
#         # Return empty list if there's an error
#         return []


# def fetch_courses_from_source() -> List[Dict[str, Any]]:
#     """
#     Fetch courses from the original source (if needed for specific scraping).
#     This is kept for compatibility if direct scraping is needed.
#     """
#     # This would contain the actual scraping logic if needed
#     # For now, we'll rely on the database's API fallback mechanism
#     db = get_db()
#     return db.get_all_courses()


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

    def _extract_opener_tck(self, html):
        """Extract SetOpenerTck value from response text."""
        # parent.Commander.SetOpenerTck('60F344C1-266E-40');
        pattern = r"SetOpenerTck\('([^']*)'\)"
        match = re.search(pattern, html)
        return match.group(1) if match else None

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

        xml_pub_prm_template = """<Root><N id="4" F1="4041" T1="4041" F2="" T2="" A="" S="" Q="" B=""/><N id="5" F1="10" T1="10" F2="" T2="" A="0" S="1" Q="1" B="B"/><N id="6" F1="{}" T1="{}" F2="" T2="" A="" S="" Q="" B=""/><N id="12" F1="" T1="" F2="" T2="" A="0" S="1" Q="2" B="B"/><N id="16" F1="" T1="" F2="" T2="" A="0" S="1" Q="3" B="B"/><N id="22" F1="" T1="" F2="" T2="" A="" S="" Q="6" B="S"/><N id="24" F1="" T1="" F2="" T2="" A="" S="" Q="7" B="S"/><N id="30" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="32" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="36" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="38" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="40" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="44" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="45" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="46" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="48" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="52" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="56" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="64" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="68" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="99" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="100" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="101" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="103" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="104" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="105" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="107" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/><N id="112" F1="" T1="" F2="" T2="" A="" S="" Q="" B=""/></Root>"""

        results_data = {}

        if status in ['available', 'both']:
            print("📥 Fetching available courses...")
            payload = {
                "__VIEWSTATE": aspnet_fields['viewstate'],
                "__VIEWSTATEGENERATOR": aspnet_fields['viewstategen'],
                "__EVENTVALIDATION": aspnet_fields['eventvalidation'],
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
                "F9999": "", "HelpCode": "", "Ref2": "", "Ref3": "",
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
            tuple: (Student, semester_ids, aspnet_fields, opener_tck)
              - Student: populated student information model
              - semester_ids: now [{'id': '4021', 'status': '...'}, ...]
              - aspnet_fields: ASP.NET session/form fields, to be used for follow-up requests
              - opener_tck: Ticket for opening new tabs/reports
        """

        self.rnd = random()
        get_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0;12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)
        ticket = aspnet_fields['ticket']

        # Extract Opener Tck from first request response
        opener_tck = self._extract_opener_tck(get_resp.text)

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

        return student, semester_ids, aspnet_fields, opener_tck

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
            "TicketTextBox": aspnet_fields['ticket'], "XMLStdHlp": "",
            "TxtMiddle": f'<r F41251="{self.username}" F01951="" F02001="" F43501="{str(semester_id)}"/>', 'ex': ''
        }

        semester_url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0%3b12310&b=10&l=1&tck={self.tck}&&lastm=20250906103728"
        resp = self._safe_request('post', semester_url, data=payload)
        next_results = self._extract_aspnet_fields(resp.text)

        # Parse the response to extract semester and course data
        semester_record = parse_semester_data(resp.text)

        return semester_record, next_results

    def fetch_current_term_enrollment(self, semester_id, prev_semester_id, semester_status, aspnet_fields):
        """
        Fetch active enrollment data.
        Uses prev_semester_id for the request payload (F43501 context).
        """
        txt_middle = f'<r F41251="{self.username}" F01951="" F02001="" F43501="{prev_semester_id}"/>'

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '50',
            "TicketTextBox": aspnet_fields['ticket'],
            "TxtMiddle": txt_middle,
            'ex': ''
        }

        url = f"https://golestan.ikiu.ac.ir/Forms/F1802_PROCESS_MNG_STDJAMEHMON/F1802_01_PROCESS_MNG_STDJAMEHMON_Dat.aspx?r={self.rnd}&fid=0%3b12310&b=10&l=1&tck={self.tck}"

        resp = self._safe_request('post', url, data=payload)

        # Call the updated parser
        semester_record = parse_enrollment_data(resp.text, semester_id, semester_status)
        next_fields = self._extract_aspnet_fields(resp.text)

        return semester_record, next_fields

    def fetch_total_credits(self, opener_tck):
        """
        Fetch the total credits report (Report 272).

        Args:
            opener_tck: The ticket extracted from student info page SetOpenerTck call

        Returns:
            str: The raw XML/HTML response containing the credits data
        """
        print("📊 Fetching total credits report (272)...")
        rnd = random()

        # 1. Initial GET Request for Report 272
        current_seq = self.seq - 1

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '11130'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(current_seq)),
            ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        get_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_Dat.aspx?r={rnd}&fid=1;272&b=10&l=1&tck={opener_tck}&&lastm=20260119060814'
        get_resp = self._safe_request('get', get_url)
        aspnet_fields = self._extract_aspnet_fields(get_resp.text)
        ticket = aspnet_fields['ticket']
        ctck = self.session.cookies.get('ctck')

        # 2. First POST Request (Setup)
        current_seq = current_seq + 2

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("ctck", ctck), ("f", '272'), ("ft", '1'),
            ("lt", self.lt), ("seq", str(current_seq)),
            ("stdno", ""), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '00', "Frm_Type": "", "Frm_No": "", "F_ID": "",
            "XmlPriPrm": "", "XmlPubPrm": "", "XmlMoredi": "",
            "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
            "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
            "TicketTextBox": ticket, "RepSrc": "", "ShowError": "",
            "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
        }

        post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_Dat.aspx?r={rnd}&fid=1%3b272&b=10&l=1&tck={opener_tck}&&lastm=20260119060814'
        post_resp = self._safe_request('post', post_url, data=payload)
        aspnet_fields = self._extract_aspnet_fields(post_resp.text)
        ticket = aspnet_fields['ticket']
        # ctck might change
        ctck = self.session.cookies.get('ctck') or ctck

        # 3. Second POST Request (Fetch Data)
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("ctck", ctck), ("f", '272'), ("ft", '1'),
            ("lt", self.lt), ("seq", str(current_seq)),
            ("stdno", ""), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        xml_pri_prm = '<Root><N UQID="655" id="2" F="0" T="0"/><N UQID="665" id="4" F="0" T="0"/><N UQID="670" id="6" F="0" T="0"/><N UQID="1100" id="8" F="2" T="2"/><N UQID="1075" id="20" F="2" T="2"/><N UQID="553" id="25" F="1" T="1"/><N UQID="352" id="30" F="1" T="1"/><N UQID="1078" id="40" F="" T=""/><N UQID="1079" id="41" F="" T=""/><N UQID="1080" id="42" F="" T=""/></Root>'

        payload = {
            '__VIEWSTATE': aspnet_fields['viewstate'],
            '__VIEWSTATEGENERATOR': aspnet_fields['viewstategen'],
            '__EVENTVALIDATION': aspnet_fields['eventvalidation'],
            'Fm_Action': '09', "Frm_Type": "", "Frm_No": "", "F_ID": "",
            "XmlPriPrm": xml_pri_prm, "XmlPubPrm": "", "XmlMoredi": "",
            "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
            "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
            "TicketTextBox": ticket, "RepSrc": "", "ShowError": "",
            "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
        }

        post_resp = self._safe_request('post', post_url, data=payload)

        return post_resp.text

def get_student_record(username=None, password=None, db=None):
    golestan = GolestanSession()
    try:
        if not golestan.authenticate(username, password):
            raise RuntimeError("Authentication failed")

        student, semesters_data, aspnet_fields, opener_tck = golestan.fetch_student_info()

        if db is None or db.student_id != student.student_id:
            from ...data.student_db import StudentDatabase
            db = StudentDatabase(student.student_id)

        for i, sem_data in enumerate(semesters_data):
            semester_id = sem_data['id']
            semester_status = sem_data.get('status', '')
            is_last_semester = (i == len(semesters_data) - 1)

            if is_last_semester and semester_status == "در حال ثبت نام _ عادي":
                # Get context from previous semester if available
                prev_sem_id = semesters_data[i - 1]['id'] if i > 0 else semester_id

                # Fetch directly into a SemesterRecord
                record, aspnet_fields = golestan.fetch_current_term_enrollment(
                    semester_id,
                    prev_sem_id,
                    semester_status,
                    aspnet_fields
                )
                student.semesters.append(record)
                print(f"✅ Loaded active enrollment: {len(record.courses)} courses")

            else:
                # Standard Mode (Action 80)
                record, aspnet_fields = golestan.fetch_semester_courses(semester_id, aspnet_fields)
                if record:
                    student.semesters.append(record)
                    print(f"✅ Semester {semester_id}: {len(record.courses)} courses")

        # After fetching all semesters, fetch the credits report
        if opener_tck:
            try:
                credits_html = golestan.fetch_total_credits(opener_tck)

                if credits_html:
                    degree_status = parse_degree_details(credits_html)

                    if degree_status:
                        student.degree_status = degree_status
                        print(f"✅ Degree status updated: {len(degree_status.categories)} categories found.")
                        print(f"   Passed: {degree_status.total_passed}, Remaining: {degree_status.remaining_units}")
                    else:
                        print("⚠️ Failed to parse degree status data.")

            except Exception as e:
                print(f"❌ Failed to process credits report: {e}")

        db.save_student(student)
        return student

    finally:
        golestan.session.close()

# def test_student_fetch():
#     # 1. Load credentials from .env
#     load_dotenv()
#     username = 
#     password = 
#
#     print(f"🚀 Starting test for student: {username}")
#     print("-" * 50)
#
#     try:
#         # 2. Execute the logic
#         # This will follow the logic:
#         # If status == 'در حال ثبت نام _ عادي' -> Fm_Action 50
#         # Else -> Fm_Action 80
#         student = get_student_record(username=username, password=password)
#
#         if not student:
#             print("❌ Failed to retrieve student data.")
#             return
#
#         print(f"\n👤 Student: {student.name}")
#         print(f"🎓 Major: {student.major}")
#         print(f"📊 Overall GPA: {student.overall_gpa}")
#         print("-" * 50)
#
#         # 3. Print all semesters
#         for i, semester in enumerate(student.semesters):
#             is_last = (i == len(student.semesters) - 1)
#             marker = "🌟 [LAST SEMESTER]" if is_last else "📅"
#
#             print(f"{marker} {semester.semester_description} (ID: {semester.semester_id})")
#             print(f"   Status: {semester.semester_status}")
#             print(f"   Units: {semester.units_taken} | GPA: {semester.semester_gpa}")
#
#             if is_last:
#                 print(f"   --- Courses Found: {len(semester.courses)} ---")
#                 for course in semester.courses:
#                     grade_info = f"Grade: {course.grade}" if course.grade else f"Status: {course.grade_state}"
#                     print(
#                         f"   - [{course.course_code}] {course.course_name} ({course.course_units} units) -> {grade_info}")
#             else:
#                 print(f"   Courses: {len(semester.courses)}")
#
#             print("." * 30)
#
#     except Exception as e:
#         print(f"💥 An error occurred during testing: {e}")
#         import traceback
#         traceback.print_exc()
#
#
#
# def test_live_degree_status():
#     """
#     Test function to fetch and display Degree Status (Report 272) from the live site.
#     """
#     import os
#     from pathlib import Path
#     from dotenv import load_dotenv
#     from ...scrapers.requests_scraper.parsers import parse_degree_details
#
#
#
#     # username =
#     # password =
#
#     if not username or not password:
#         print("❌ Error: USERNAME or PASSWORD not found in .env")
#         return
#
#     print(f"🚀 Starting Live Degree Status Test for: {username}")
#     print("-" * 50)
#
#     # 2. Initialize Session
#     golestan = GolestanSession()
#
#     try:
#         # 3. Authenticate
#         if not golestan.authenticate(username, password):
#             print("❌ Authentication failed")
#             return
#
#         # 4. Get Opener Ticket
#         print("📥 Fetching student info to get Opener Ticket...")
#         student, _, _, opener_tck = golestan.fetch_student_info()
#
#         if not opener_tck:
#             print("❌ Opener Ticket not found.")
#             return
#
#         # 5. Fetch Credits Report
#         print(f"📊 Fetching Report 272 with Ticket: {opener_tck}")
#         xml_data = golestan.fetch_total_credits(opener_tck)
#
#         if not xml_data:
#             print("❌ Failed to download report data.")
#             return
#
#         # 6. Parse Data
#         print("🧩 Parsing Report Data...")
#         degree_status = parse_degree_details(xml_data)
#
#         # 7. Show Results
#         if degree_status:
#             print("\n✅ LIVE DATA FETCH SUCCESSFUL!")
#             print("=" * 50)
#             print("🎓 DEGREE PROGRESS SUMMARY")
#             print(f"   - Total Passed:      {degree_status.total_passed}")
#             print(f"   - Required:          {degree_status.total_required_min} - {degree_status.total_required_max}")
#             print(f"   - Incomplete:        {degree_status.incomplete_units}")
#             print(f"   - Remaining:         {degree_status.remaining_units}")
#             print("-" * 50)
#             print(f"📚 CATEGORY BREAKDOWN ({len(degree_status.categories)} found)")
#             print(f"   {'CATEGORY':<20} {'MIN':<6} {'MAX':<6} {'PASSED':<6}")
#             print(f"   {'-' * 20} {'-' * 6} {'-' * 6} {'-' * 6}")
#
#             for cat in degree_status.categories:
#                 print(f"   {cat.category_name:<20} {cat.min_units:<6} {cat.max_units:<6} {cat.passed_units:<6}")
#             print("=" * 50)
#         else:
#             print("❌ Parser returned None. Check the XML structure.")
#             # Optional: save the XML to debug if parsing fails
#             with open("debug_live_fail.xml", "w", encoding="utf-8") as f:
#                 f.write(xml_data)
#             print("   (Saved raw XML to 'debug_live_fail.xml' for inspection)")
#
#     except Exception as e:
#         print(f"💥 Error: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         golestan.session.close()
#
#
# if __name__ == "__main__":
#     test_live_degree_status()