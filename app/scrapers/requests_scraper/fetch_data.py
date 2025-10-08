import re
import time
from random import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.cookies import create_cookie
from pathlib import Path
from app.scrapers.requests_scraper.xml_parser import parse_courses_from_xml
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
        scrapers_dir = Path(__file__).resolve().parent.parent
        env_path = scrapers_dir / '.env'
        
        # Load the .env file from the correct location
        load_dotenv(dotenv_path=env_path, override=True)
        
        # Fix: Don't convert username to int, keep it as string
        username = username or os.getenv("USERNAME")
        password = password or os.getenv("PASSWORD")

        # Get session ID
        url = "https://golestan.ikiu.ac.ir/_templates/unvarm/unvarm.aspx?typ=1"
        response = self.session.get(url, headers=self.headers)
        self.session_id = self.session.cookies.get("ASP.NET_SessionId")

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", ""), ("ft", ""), ("lt", ""),
            ("seq", ""), ("su", ""), ("u", "")
        ]
        self._add_cookies(cookie_tuples)

        # Get login page
        get_url = 'https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/AuthUser.aspx?fid=0;1&tck=&&&lastm=20240303092318'
        get_resp = self.session.get(get_url, headers=self.headers)
        results = self._extract_aspnet_fields(get_resp.text)

        # Step 4: Initial POST
        payload = {
            '__VIEWSTATE': results['viewstate'],
            '__VIEWSTATEGENERATOR': results['viewstategen'],
            '__EVENTVALIDATION': results['eventvalidation'],
            'TxtMiddle': '<r/>',
            'Fm_Action': '00',
            'Frm_Type': '', 'Frm_No': '', 'TicketTextBox': ''
        }

        post_url = 'https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/AuthUser.aspx?fid=0%3b1&tck=&&&lastm=20240303092318'
        post_resp = self.session.post(post_url, data=payload, headers=self.headers)
        results = self._extract_aspnet_fields(post_resp.text)

        # Captcha solving loop
        for i in range(max_attempts):
            print(f"🔄 Authentication attempt {i + 1}/{max_attempts}...")

            # Get captcha
            captcha_url = f"https://golestan.ikiu.ac.ir/Forms/AuthenticateUser/captcha.aspx?{random()}"
            resp = self.session.get(captcha_url, headers=self.headers, stream=True)

            if resp.status_code == 200:
                print("✅ Captcha image received. Running recognition...")
                captcha_text = predict(resp.content)
            else:
                print("❌ Failed to download captcha")
                continue  # Skips to next loop iteration

            payload = {
                '__VIEWSTATE': results['viewstate'],
                '__VIEWSTATEGENERATOR': results['viewstategen'],
                '__EVENTVALIDATION': results['eventvalidation'],
                'TxtMiddle': f'<r F51851="" F80351="{username}" F80401="{password}" F51701="{captcha_text}" F83181="1" F51602="" F51803="0" F51601="1"/>',
                'Fm_Action': '09',
                'Frm_Type': '', 'Frm_No': '', 'TicketTextBox': ''
            }

            resp_post = self.session.post(post_url, data=payload, headers=self.headers)

            # Check if login successful
            self.lt = self.session.cookies.get("lt")
            self.u = self.session.cookies.get("u")

            if self.lt and self.u:
                print(f"✅ Authentication successful on attempt {i + 1}")
                results = self._extract_aspnet_fields(resp_post.text)
                self.tck = results['ticket']
                self.session_id = self.session.cookies.get("ASP.NET_SessionId", domain="golestan.ikiu.ac.ir")
                break
            else:
                print(f"❌ Failed attempt {i + 1}: Invalid captcha or credentials")
                time.sleep(1)
                continue
        else:
            print("🚫 All authentication attempts failed")
            return False

        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '1'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("stdno", ''),
            ("su", '0'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        rnd = random()
        get_url = f'https://golestan.ikiu.ac.ir/Forms/F0213_PROCESS_SYSMENU/F0213_01_PROCESS_SYSMENU_Dat.aspx?r={rnd}&fid=0;11130&b=&l=&tck={self.tck}&&lastm=20240303092316'
        get_resp = self.session.get(get_url, headers=self.headers)
        results = self._extract_aspnet_fields(get_resp.text)
        ticket = results['ticket']

        self.seq += 1
        cookie_tuples = [
            ("ASP.NET_SessionId", self.session_id),
            ("f", '11130'), ("ft", '0'), ("lt", self.lt),
            ("seq", str(self.seq)), ("su", '3'), ("u", self.u)
        ]
        self._add_cookies(cookie_tuples)

        payload = {
            '__VIEWSTATE': results['viewstate'],
            '__VIEWSTATEGENERATOR': results['viewstategen'],
            '__EVENTVALIDATION': results['eventvalidation'],
            'Fm_Action': '00', "Frm_Type": "", "Frm_No": "",
            "TicketTextBox": ticket, "XMLStdHlp": "",
            "TxtMiddle": "<r/>", 'ex': ''
        }

        post_url = f'https://golestan.ikiu.ac.ir/Forms/F0213_PROCESS_SYSMENU/F0213_01_PROCESS_SYSMENU_Dat.aspx?r={rnd}&fid=0%3b11130&b=&l=&tck={self.tck}&&lastm=20240303092316'
        post_resp = self.session.post(post_url, headers=self.headers, data=payload)
        results = self._extract_aspnet_fields(post_resp.text)
        self.tck = results['ticket']

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

        self.report_rnd = random()
        get_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={self.report_rnd}&fid=1;102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
        get_resp = self.session.get(get_url, headers=self.headers)
        results = self._extract_aspnet_fields(get_resp.text)
        ticket = results['ticket']
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
            "__VIEWSTATE": results['viewstate'],
            "__VIEWSTATEGENERATOR": results['viewstategen'],
            "__EVENTVALIDATION": results['eventvalidation'],
            "Fm_Action": "00", "Frm_Type": "", "Frm_No": "", "F_ID": "",
            "XmlPriPrm": "", "XmlPubPrm": "", "XmlMoredi": "",
            "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
            "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
            "TicketTextBox": ticket, "RepSrc": "", "ShowError": "",
            "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
        }

        post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={self.report_rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
        post_resp = self.session.post(post_url, headers=self.headers, data=payload)

        results = self._extract_aspnet_fields(post_resp.text)
        self.report_ticket = results['ticket']

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
                "__VIEWSTATE": results['viewstate'],
                "__VIEWSTATEGENERATOR": results['viewstategen'],
                "__EVENTVALIDATION": results['eventvalidation'],
                "Fm_Action": "09", "Frm_Type": "", "Frm_No": "", "F_ID": "",
                "XmlPriPrm": xml_pri_prm.replace('\n', ''),
                "XmlPubPrm": xml_pub_prm_template.format(1, 1).replace('\n', ''),
                "XmlMoredi": "<Root/>",
                "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
                "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
                "TicketTextBox": self.report_ticket, "RepSrc": "", "ShowError": "",
                "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
            }

            post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={self.report_rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
            post_resp = self.session.post(post_url, headers=self.headers, data=payload)

            xml_string = self._extract_xmldat(post_resp.text)
            if xml_string:
                results_data['available'] = xml_string
                print("✅ Available courses data retrieved")
            else:
                print("❌ Failed to extract available courses data")

            # Update state for next request
            results = self._extract_aspnet_fields(post_resp.text)
            self.report_ticket = results['ticket']
            self.ctck = self.session.cookies.get('ctck')

        # Fetch unavailable courses
        if status in ['unavailable', 'both']:
            print("📥 Fetching unavailable courses...")

            # Update cookies (just different ctck as previous request)
            cookie_tuples[1] = ("ctck", self.ctck)
            self._add_cookies(cookie_tuples)

            payload = {
                "__VIEWSTATE": results['viewstate'],
                "__VIEWSTATEGENERATOR": results['viewstategen'],
                "__EVENTVALIDATION": results['eventvalidation'],
                "Fm_Action": "09", "Frm_Type": "", "Frm_No": "", "F_ID": "",
                "XmlPriPrm": xml_pri_prm.replace('\n', ''),
                "XmlPubPrm": xml_pub_prm_template.format(0, 0).replace('\n', ''),
                "XmlMoredi": "<Root/>",
                "F9999": "", "HelpCode": "", "Ref1": "", "Ref2": "", "Ref3": "",
                "Ref4": "", "Ref5": "", "NameH": "", "FacNoH": "", "GrpNoH": "",
                "TicketTextBox": self.report_ticket, "RepSrc": "", "ShowError": "0",
                "TxtMiddle": "<r/>", "tbExcel": "", "txtuqid": "", "ex": ""
            }

            post_url = f'https://golestan.ikiu.ac.ir/Forms/F0202_PROCESS_REP_FILTER/F0202_01_PROCESS_REP_FILTER_DAT.ASPX?r={self.report_rnd}&fid=1%3b102&b=10&l=1&tck={self.tck}&&lastm=20230828062456'
            post_resp = self.session.post(post_url, headers=self.headers, data=payload)

            xml_string = self._extract_xmldat(post_resp.text)
            if xml_string:
                results_data['unavailable'] = xml_string
                print("✅ Unavailable courses data retrieved")
            else:
                print("❌ Failed to extract unavailable courses data")

        return results_data


def get_courses(status='both', username=None, password=None):
    """
    High-level function to fetch course data from Golestan.

    Args:
        status: 'available', 'unavailable', or 'both'
        username: Login username (defaults to env USERNAME)
        password: Login password (defaults to env PASSWORD)

    Returns:
        dict: Dictionary with 'available' and/or 'unavailable' keys containing course data
    """
    golestan = GolestanSession()

    try:
        if not golestan.authenticate(username, password):
            raise RuntimeError("Authentication failed")

        results = golestan.fetch_courses(status)

        # Get the path to the app root
        app_root = Path(__file__).resolve().parent.parent.parent
        project_super_root = app_root.parent

        data_dir = app_root / 'data' / 'courses_data'
        os.makedirs(data_dir, exist_ok=True)

        if 'available' in results:
            available_path = data_dir / 'available_courses.json'
            parse_courses_from_xml(results['available'], str(available_path))
            print(f"💾 Available courses saved to {available_path.relative_to(project_super_root)}")
        if 'unavailable' in results:
            unavailable_path = data_dir / 'unavailable_courses.json'
            parse_courses_from_xml(results['unavailable'], str(unavailable_path))
            print(f"💾 Unavailable courses saved to {unavailable_path.relative_to(project_super_root)}")

    finally:
        golestan.session.close()


if __name__ == "__main__":
    # Example usage
    courses = get_courses(status='both')
    print("✅ Course fetching complete!")