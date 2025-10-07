import base64
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchFrameException, TimeoutException
import time
from dotenv import load_dotenv
import os
from app.scrapers.selenium_scraper.html_parser import parse_courses_from_html
from app.captcha_solver.predict import predict

def switch_to_frames(frame_names, driver, wait, max_attempts=3, delay=1):
    """
    Enhanced frame switching with better error handling and debugging
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            # Always start from default content
            driver.switch_to.default_content()
            time.sleep(delay)

            # Switch to each frame in sequence
            for i, name in enumerate(frame_names):
                try:
                    # Debug: Show available frames at current level
                    frames = driver.find_elements(By.TAG_NAME, "frame")
                    frame_names_debug = [f.get_attribute("name") for f in frames]
                    # print(f"🔍 Available frames at level {i}: {frame_names_debug}")

                    # Wait for frame to be available and switch to it
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, name)))
                    # print(f"✅ Switched to frame: {name}")

                except Exception as frame_error:
                    print(f"❌ Failed to switch to frame '{name}': {frame_error}")
                    raise frame_error

            print(f"✅ Successfully switched to frame sequence: {' → '.join(frame_names)}")
            return True

        except Exception as e:
            attempt += 1
            print(f"❌ Attempt {attempt}/{max_attempts}: Frame switch failed | Error: {e}")
            if attempt < max_attempts:
                print(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"❌ All {max_attempts} attempts failed for frame sequence: {frame_names}")

    return False


def download_captcha_base64(driver, wait):
    """
    Download CAPTCHA as base64 and return image bytes
    """
    try:
        img = wait.until(EC.visibility_of_element_located((By.ID, "imgCaptcha")))

        # Use JavaScript to get image as base64
        base64_data = driver.execute_script("""
            var img = arguments[0];
            var canvas = document.createElement('canvas');
            var ctx = canvas.getContext('2d');
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png').substring(22);
        """, img)

        if base64_data:
            # Decode the image
            image_data = base64.b64decode(base64_data)
            print("✅ CAPTCHA extracted successfully")
            return image_data
        else:
            print("❌ Could not extract base64 data")
            return None

    except Exception as e:
        print(f"❌ Failed to download CAPTCHA: {e}")
        return None

def wait_for_captcha_change_optimized(driver, wait, old_captcha_src, timeout=30):
    """
    Wait for CAPTCHA to change - assumes we're already in the correct frame
    """
    if not old_captcha_src:
        return True  # If we don't have old src, assume it changed

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Don't switch frames - assume we're already in the right place
            img = driver.find_element(By.ID, "imgCaptcha")
            new_src = img.get_attribute("src")

            if new_src != old_captcha_src:
                print("✅ CAPTCHA changed!")
                return True

        except Exception as e:
            print(f"⚠️ Error checking CAPTCHA change: {e}")

        time.sleep(0.1)  # Check every 500ms

    print(f"⏰ CAPTCHA didn't change within {timeout} seconds")
    return False

def wait_for_loading(frame, driver, wait, messages=None):
    if messages is None:
        messages = ["لطفا صبر کنيد."]
    try:
        driver.switch_to.default_content()
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, frame))
        )
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, "Message"))
        )
        print("✅ Switched to Message frame")

        # Now safe to check loading table
        table = wait.until(EC.visibility_of_element_located((By.ID, "tbl_Msg")))

        for message in messages:
            WebDriverWait(driver, 30).until(
                lambda d: table.find_element(By.ID, "errtxt").text != message)

        print("✅ Loading completed")
        return True

    except TimeoutException:
        print(f"⚠️ loading didn’t finish")
    except Exception as e:
        print(f"❌ Unexpected error on attempt: {e}")

def check_for_errors(driver, wait):
    """
    Check for login errors with improved error handling
    """
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame("Faci1")
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Message")))

        table = wait.until(EC.visibility_of_element_located((By.ID, "tbl_Msg")))

        # Wait until errtxt text is not 'wait...'
        wait.until(lambda d: table.find_element(By.ID, "errtxt").text != "لطفا صبر کنيد.")

        err_txt = table.find_element(By.ID, "errtxt").text
        err_num = table.find_element(By.ID, "errcnt").text

        if "پيغام" in err_num:
            print(f"📋 Error number: {err_num}")
            print(f"📋 Error text: {err_txt}")
            return True, err_txt
        else:
            return False, None

    except (NoSuchFrameException, TimeoutException):
        print("✅ No error frame found - login likely successful")
        return False, None
    except Exception as e:
        print(f"⚠️ Error checking for login errors: {e}")
        return False, None


def perform_login_sequence(driver, wait, username, password, max_captcha_attempts=5):
    """
    Complete login sequence with CAPTCHA handling and auto-download for training
    """
    print("🚀 Starting login sequence...")

    # Step 1: Fill username and password
    if not switch_to_frames( ["Faci1", "Master", "Form_Body"], driver, wait):
        print("❌ Frame switch failed. Aborting login.")
        return False

    try:
        # Fill username
        username_input = wait.until(EC.visibility_of_element_located((By.ID, "F80351")))
        print("✅ Found username input!")
        username_input.click()
        username_input.clear()
        username_input.send_keys(username)
        print("✅ Username entered successfully!")

        # Fill password
        password_input = wait.until(EC.visibility_of_element_located((By.ID, "F80401")))
        print("✅ Found password input!")
        password_input.click()
        password_input.clear()
        password_input.send_keys(password)
        print("✅ Password entered successfully!")

        # Download initial CAPTCHA
        print("📷 Downloading initial CAPTCHA...")
        image_content = download_captcha_base64(driver, wait)

    except Exception as e:
        print(f"❌ Could not fill login credentials: {e}")
        return False

    # Step 2: CAPTCHA loop with optimized frame handling
    captcha_attempt = 0
    while captcha_attempt < max_captcha_attempts:
        captcha_attempt += 1
        print(f"\n🔐 CAPTCHA attempt {captcha_attempt}/{max_captcha_attempts}")

        # Get current CAPTCHA src (we're already in Form_Body frame)
        try:
            img = wait.until(EC.visibility_of_element_located((By.ID, "imgCaptcha")))
            current_captcha_src = img.get_attribute("src")
        except Exception as e:
            print(f"❌ Could not get CAPTCHA src: {e}")
            current_captcha_src = None

        # Get CAPTCHA text from model
        captcha_text = predict(image_content)
        print(f"🤖 Model predicted: '{captcha_text}' (length: {len(captcha_text)})")

        # Validate CAPTCHA length
        if len(captcha_text) != 5:
            print(f"⚠️ Model returned {len(captcha_text)} characters instead of 5. Refreshing CAPTCHA...")

            # Try manual refresh
            driver.execute_script("return oc();")

            wait_for_captcha_change_optimized(driver, wait, current_captcha_src)

            # Download new CAPTCHA image
            image_content = download_captcha_base64(driver, wait)
            print("📷 Downloaded new CAPTCHA after length validation failure")
            continue

        # Fill CAPTCHA (we're still in Form_Body frame)
        try:
            captcha_input = wait.until(EC.visibility_of_element_located((By.ID, "F51701")))
            print("✅ Found CAPTCHA input field!")
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            print(f"✅ Entered CAPTCHA: {captcha_text}")
        except Exception as e:
            print(f"❌ Could not fill CAPTCHA: {e}")
            continue

        # Click login button (we're still in the same frame)
        try:
            driver.execute_script("F51601.value=1; F51601.UpdateSndData();")
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLog")))
            login_button.click()
            print("✅ Login button clicked")

        except Exception as e:
            print(f"❌ Could not click login button: {e}")
            continue

        # Check for errors
        error_occurred, error_text = check_for_errors(driver, wait)

        if not error_occurred:
            wait_for_loading("Faci2", driver, wait)
            return True

        # Handle different types of errors
        print(f"❌ Login error occurred: {error_text}")

        if error_text == "لطفا كد امنيتي را به صورت صحيح وارد نماييد":
            print("🔄 CAPTCHA was incorrect!")

            # Switch back to CAPTCHA frame for checking change
            if switch_to_frames(["Faci1", "Master", "Form_Body"], driver, wait):
                # Wait for automatic CAPTCHA refresh (already in frame)
                if wait_for_captcha_change_optimized(driver, wait, current_captcha_src):
                    print("✅ CAPTCHA refreshed automatically, downloading new one...")
                    image_content = download_captcha_base64(driver, wait)
                else:
                    print("⚠️ CAPTCHA didn't refresh automatically")

            print("🔄 Please try again with the new CAPTCHA...")
            continue

        elif error_text == "کد1 : شناسه کاربري يا گذرواژه اشتباه است.":
            print("❌ Username or password is incorrect")
            return False
        else:
            print(f"❌ Unknown error: {error_text}")
            return False
    print(f"❌ Failed after {max_captcha_attempts} CAPTCHA attempts")
    return False

def click_ok_with_retry(driver, wait, max_attempts=3):
    """Click OK button and retry if Faci3 frame doesn't appear"""

    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1} to click OK button...")

        # Step 1: Switch to frame (early return on failure)
        if not switch_to_frames(["Faci2", "Master", "Form_Body"], driver, wait):
            print("❌ Frame switch failed.")
            continue

        # Step 2: Execute operations (early return on failure)
        try:
            report_number = wait.until(EC.visibility_of_element_located((By.ID, "F20851")))
            print("✅ Found report input!")
            report_number.clear()
            report_number.send_keys("102")
            print("✅ Sent report number successfully!")

            result = driver.execute_script("return dirok();")
            print(f"JavaScript function result: {result}")

        except Exception as e:
            print(f"❌ Could not locate input: {e}")
            continue


        # Step 4: Check for Faci3 frame
        driver.switch_to.default_content()
        try:
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
            )
            print(f"✅ Success! Faci3 frame found on attempt {attempt + 1}")
            return True

        except TimeoutException:
            print(f"❌ Attempt {attempt + 1}: Faci3 frame not found")
            if attempt < max_attempts - 1:
                print("Retrying...")
                time.sleep(2)

    return False  # All attempts failed


def ensure_on_result_page_with_retry(driver, wait, course_status, max_attempts=3):
    """Ensure we're on result page - Fill form, click View Report, then wait for success"""

    for attempt in range(max_attempts):
        print(f"\n--- Navigation attempt {attempt + 1} ---")

        # STEP 1: Fill the form with course status
        print("📝 Filling course status in form...")
        if switch_to_frames(["Faci3", "Master", "Form_Body"], driver, wait):
            try:
                # Wait for pubTbl table to be visible first
                WebDriverWait(driver, 15).until(
                    EC.visibility_of_element_located((By.ID, "pubTbl"))
                )
                print("✅ pubTbl table is visible! Form ready for input!")

                # Fill course status input
                input_1 = wait.until(EC.visibility_of_element_located((By.ID, "GF10956_0")))
                input_1.clear()
                input_1.send_keys(str(course_status))
                print(f"✅ Course status '{course_status}' entered successfully!")

            except Exception as e:
                print(f"❌ Error filling form: {e}")
                if attempt < max_attempts - 1:
                    print("🔄 Retrying in 3 seconds...")
                    time.sleep(3)
                continue
        else:
            print("❌ Could not switch to form frame")
            if attempt < max_attempts - 1:
                print("🔄 Retrying in 3 seconds...")
                time.sleep(3)
            continue

        # STEP 2: Click View Report button
        success = False
        if switch_to_frames(["Faci3", "Commander"], driver, wait):
            try:
                driver.execute_script("IM16_ViewRep_onclick();")
                print("✅ View Report button clicked!")
                success = True
            except Exception as e:
                print(f"❌ Error clicking View Report: {e}")
        else:
            print("❌ Could not switch to Commander frame for View Report button")

        if not success:
            # Skip remaining steps if Step 2 failed
            if attempt < max_attempts - 1:
                print("🔄 Retrying in 3 seconds...")
                time.sleep(3)
            continue

        # STEP 3: Wait for loading to complete
        wait_for_loading("Faci3", driver, wait)

        # STEP 4: Wait for commTbl table to appear in Commander frame
        print("⏳ Waiting for commTbl table to appear on result page...")
        try:
            # Switch to Commander frame
            driver.switch_to.default_content()
            WebDriverWait(driver, 15).until(
                EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
            )
            driver.switch_to.frame("Commander")

            # Wait for commTbl table (60 second timeout)
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.ID, "commTbl"))
            )

            print("✅ commTbl table found! Navigation to report page complete!")
            return True  # Success!

        except TimeoutException:
            print("❌ commTbl table never appeared on report page within 60 seconds")
        except Exception as e:
            print(f"⚠️ Error waiting for commTbl table: {e}")

        # If we reach here, failed this attempt
        if attempt < max_attempts - 1:
            print("🔄 Retrying in 3 seconds...")
            time.sleep(3)

    print(f"❌ Failed to reach result page after {max_attempts} attempts")
    return False

def _attempt_export(driver):
    """
    Single export attempt - returns HTML or None
    """
    try:
        # Switch to Commander frame for export
        driver.switch_to.default_content()
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
        )
        driver.switch_to.frame("Commander")

        # Wait for export button to be ready
        export_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ExToEx"))
        )

        # Override window.open to capture the HTML instead of opening a popup
        driver.execute_script("""
            window.capturedHTML = null;
            window.exportComplete = false;
            window.originalOpen = window.open;
            window.open = function(url, name, features) {
                console.log('Export window.open called with:', url);
                // Create a fake window object
                var fakeWindow = {
                    document: {
                        write: function(html) {
                            console.log('HTML captured, length:', html.length);
                            window.capturedHTML = html;
                            window.exportComplete = true;
                        },
                        close: function() {
                            console.log('Document close called');
                        }
                    },
                    close: function() {
                        console.log('Window close called');
                    }
                };
                return fakeWindow;
            };
        """)

        # Click the export button
        export_btn.click()
        print("🔄 Export button clicked, waiting for response...")

        # Wait for export to complete with timeout
        max_wait_time = 10
        waited = 0
        while waited < max_wait_time:
            export_complete = driver.execute_script("return window.exportComplete;")
            if export_complete:
                break
            time.sleep(0.5)
            waited += 0.5

        # Get the captured HTML
        html = driver.execute_script("return window.capturedHTML;")

        # Restore original window.open
        driver.execute_script("window.open = window.originalOpen;")

        # Log result
        if html:
            print(f"✅ HTML captured successfully! Length: {len(html)} characters")
        else:
            print("⚠️ No HTML captured in this attempt")

        return html

    except Exception as e:
        print(f"❌ Export attempt failed with error: {e}")
        # Restore window.open even on error
        try:
            driver.execute_script("if (window.originalOpen) window.open = window.originalOpen;")
        except:
            pass
        return None


def _refresh_export_state(driver):
    """
    Refresh the export state between retries
    """
    try:
        print("🔄 Refreshing export state...")

        # Clear any lingering JavaScript state
        driver.execute_script("""
            if (window.capturedHTML) delete window.capturedHTML;
            if (window.exportComplete) delete window.exportComplete;
            if (window.originalOpen && window.open !== window.originalOpen) {
                window.open = window.originalOpen;
            }
        """)

        # Optional: Click something else and then back to export to refresh state
        driver.switch_to.default_content()
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
        )
        driver.switch_to.frame("Commander")

        # Wait a moment for any pending operations
        time.sleep(1)

    except Exception as e:
        print(f"⚠️ Could not refresh export state: {e}")


def _return_to_filter_page(driver):
    """
    Always return to filter page regardless of export success/failure
    """
    try:
        driver.switch_to.default_content()
        WebDriverWait(driver, 5).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
        )
        driver.switch_to.frame("Commander")
        back_to_filter = driver.find_element(By.ID, 'IM91_gofilter')
        time.sleep(1)
        back_to_filter.click()
        print("✅ Returned to filter page")
    except Exception as e:
        print(f"⚠️ Could not return to filter page: {e}")

def export_table_simple(driver, wait, max_retries=3, retry_delay=2):
    """
    Simpler approach that overrides window.open to capture HTML content with retry logic
    """
    # Try export with retry logic
    html = None
    for attempt in range(max_retries):
        print(f"🔄 Export attempt {attempt + 1}/{max_retries}")

        html = _attempt_export(driver)

        if html:
            print(f"✅ Table data captured successfully on attempt {attempt + 1}!")
            break
        else:
            print(f"⚠️ No HTML captured on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                print(f"⏳ Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
                # Optional: Refresh the export button state
                _refresh_export_state(driver)
            else:
                print("❌ All export attempts failed")

    # Always return to filter page
    _return_to_filter_page(driver)

    return html


def get_fast_chrome_options():
    """
    Optimized Chrome options for fastest Selenium execution
    """
    chrome_options = Options()

    # Core headless and performance options
    chrome_options.add_argument("--headless=new")  # New headless mode (faster)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    # Memory and resource optimization
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max-old-space-size=4096")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    #
    # JavaScript optimization
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-features=BlinkGenPropertyTrees")
    #
    # # Network and loading optimization
    chrome_options.add_argument("--aggressive-cache-discard")
    chrome_options.add_argument("--disable-background-downloads")
    chrome_options.add_argument("--disable-background-sync")
    chrome_options.add_argument("--disable-sync")
    #
    # # UI and visual optimization
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--disable-popup-blocking")
    # chrome_options.add_argument("--disable-prompt-on-repost")
    #
    # # Security features that can be disabled for speed
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-features=VizServiceDisplayCompositor")
    #
    # # Process optimization
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-logging-redirect")
    chrome_options.add_argument("--log-level=3")

    # Set preferences for better performance
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2,  # Block notifications
            "geolocation": 2,  # Block location requests
            "media_stream": 2,  # Block media requests
        },
        "profile.default_content_settings.popups": 0,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Additional experimental options for speed
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", [
        "enable-automation",
        "enable-logging",
        "disable-extensions"
    ])

    return chrome_options

def scrape_golestan_courses(course_status, username=None, password=None):

    load_dotenv(override=True)
    if username is None:
        username = int(os.getenv("USERNAME"))

    if password is None:
        password = os.getenv("PASSWORD")

    chrome_options = get_fast_chrome_options()

    url = "https://golestan.ikiu.ac.ir/forms/authenticateuser/main.htm"   # change if needed

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    try:
        wait_for_loading('Faci1', driver, wait)

        # Perform the complete login sequence
        successful_login = perform_login_sequence(driver, wait, username, password)

        if successful_login:
            print("🎉 Login completed successfully!")
        else:
            print("❌ Login failed after all attempts")

        # Usage
        navigation_success = click_ok_with_retry(driver, wait)
        if not navigation_success:
            print("❌ Could not navigate to course report dashboard.")

        print("✅ Successfully navigated to course report dashboard!")

        wait_for_loading("Faci3", driver, wait, messages=['', "لطفا صبر کنيد."])

        # Get app root (parent of scrapers)
        app_root = Path(__file__).resolve().parents[2]

        courses_data_dir = os.path.join(app_root, 'data', 'courses_data')
        os.makedirs(courses_data_dir, exist_ok=True)

        if course_status == "available":
            if not ensure_on_result_page_with_retry(driver, wait, 1):
                print("❌ Could not navigate to result page for available courses, aborting export")
                raise Exception("Available courses navigation failed")  # Go to log out

            print("📚 Scraping available courses...")
            html_available = export_table_simple(driver, wait)
            if html_available:
                # Parse and save to JSON - function creates file and returns True
                success = parse_courses_from_html(html_available, os.path.join(courses_data_dir, 'available_courses.json'))
                if success:
                    print("✅ Available courses saved to JSON file")
            else:
                print("⚠️ No available courses HTML retrieved")

        elif course_status == "unavailable":
            if not ensure_on_result_page_with_retry(driver, wait, 0):
                print("❌ Could not navigate to result page for unavailable courses, aborting export")
                raise Exception("Available courses navigation failed")  # Go to log out

            print("📚 Scraping unavailable courses...")
            html_unavailable = export_table_simple(driver, wait)
            if html_unavailable:
                success = parse_courses_from_html(html_unavailable, os.path.join(courses_data_dir, 'unavailable_courses.json'))
                if success:
                    print("✅ Unavailable courses saved to JSON file")
            else:
                print("⚠️ No unavailable courses HTML retrieved")

        elif course_status == "both":
            print("📚 Scraping both available and unavailable courses...")

            if not ensure_on_result_page_with_retry(driver, wait, 1):
                print("❌ Could not navigate to result page for available courses, aborting export")
                raise Exception("Available courses navigation failed")  # Go to log out

            # Scrape available first
            print("  📋 Getting available courses...")
            html_available = export_table_simple(driver, wait)
            if html_available:
                success = parse_courses_from_html(html_available, os.path.join(courses_data_dir, 'available_courses.json'))
                if success:
                    print("✅ Available courses saved to JSON file")
            else:
                print("⚠️ No available courses HTML retrieved")

            if not ensure_on_result_page_with_retry(driver, wait, 0):
                print("❌ Could not navigate to result page for unavailable courses, aborting export")
                raise Exception("Available courses navigation failed")  # Go to log out

            # Scrape unavailable second
            print("  📋 Getting unavailable courses...")
            html_unavailable = export_table_simple(driver, wait)
            if html_unavailable:
                success = parse_courses_from_html(html_unavailable, os.path.join(courses_data_dir, 'unavailable_courses.json'))
                if success:
                    print("✅ Unavailable courses saved to JSON file")
            else:
                print("⚠️ No unavailable courses HTML retrieved")

        # Step 4: Logout
        print("🔓 Logging out...")
        try:
            driver.switch_to.default_content()
            logout_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='خروج']"))
            )
            logout_element.click()
            print("✅ Logout successful!")
        except Exception as e:
            print(f"⚠️ Logout warning: {e}")

    except Exception as e:
        print(f"❌ Scraping error: {e}")

    finally:
        driver.quit()
        print("✅ Browser closed successfully!")

scrape_golestan_courses('both')