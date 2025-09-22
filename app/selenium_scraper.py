import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchFrameException, TimeoutException
import time
from dotenv import load_dotenv
import os
from html_parser import parse_courses_from_html

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
    Download CAPTCHA as base64 with timestamp and optional user input
    """
    try:
        if not switch_to_frames(["Faci1", "Master", "Form_Body"], driver, wait):
            print("❌ Could not switch to CAPTCHA frame")
            return False

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

            # Decode and save the image
            image_data = base64.b64decode(base64_data)

            # Save main file
            with open('current_capcha.png', "wb") as f:
                f.write(image_data)
            print("✅ CAPTCHA saved as: 'current_capcha.png'")

        else:
            print("❌ Could not extract base64 data")
            return False

    except Exception as e:
        print(f"❌ Failed to download CAPTCHA: {e}")
        return False


def wait_for_captcha_input_optimized(driver, wait, timeout=120):
    """
    Wait for user to enter CAPTCHA with better UX - stays in frame
    """
    try:
        # Switch to CAPTCHA input frame ONCE
        if not switch_to_frames(["Faci1", "Master", "Form_Body"], driver, wait):
            print("❌ Could not switch to CAPTCHA input frame")
            return False, None

        # Get current CAPTCHA src while we're already in the frame
        try:
            img = wait.until(EC.visibility_of_element_located((By.ID, "imgCaptcha")))
            current_captcha_src = img.get_attribute("src")
        except Exception as e:
            print(f"❌ Could not get CAPTCHA src: {e}")
            current_captcha_src = None

        captcha_input = wait.until(EC.visibility_of_element_located((By.ID, "F51701")))
        print("✅ Found CAPTCHA input field!")

        captcha_input.clear()
        captcha_input.click()


        print("📝 Please enter the 5-character CAPTCHA...")
        print("   Waiting for exactly 5 characters...")

        # Wait for user to enter exactly 5 characters with progress indicator
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                current_value = driver.find_element(By.ID, "F51701").get_attribute("value")
                if len(current_value) == 5:
                    print("✅ 5 characters entered, proceeding...")
                    return True, current_captcha_src
            except:
                time.sleep(.5)

        print(f"⏰ Timeout after {timeout} seconds")
        return False, None

    except Exception as e:
        print(f"❌ Error waiting for CAPTCHA input: {e}")
        return False, None


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

        print(f"📋 Error number: {err_num}")
        print(f"📋 Error text: {err_txt}")

        if "پيغام" in err_num:
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
        download_captcha_base64(driver, wait)

    except Exception as e:
        print(f"❌ Could not fill login credentials: {e}")
        return False

    # Step 2: CAPTCHA loop with optimized frame handling
    captcha_attempt = 0
    while captcha_attempt < max_captcha_attempts:
        captcha_attempt += 1
        print(f"\n🔐 CAPTCHA attempt {captcha_attempt}/{max_captcha_attempts}")

        # Get CAPTCHA input and current src in one frame switch
        captcha_success, current_captcha_src = wait_for_captcha_input_optimized(driver, wait)
        if not captcha_success:
            print("❌ Failed to get CAPTCHA input")
            continue

        # Click login button (we're still in the same frame)
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLog")))
            login_button.click()
            print("✅ Login button clicked")

        except Exception as e:
            print(f"❌ Could not click login button: {e}")
            continue

        # Check for errors
        error_occurred, error_text = check_for_errors(driver, wait)

        if not error_occurred:
            print("🎉 Login successful!")
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
                    download_captcha_base64(driver, wait)
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

# print(f"📚 Saving incorrect CAPTCHA with user input '{captcha_input}' for training...")
# timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# dest_path = os.path.join('incorrect_captcha', f"{captcha_input}_{timestamp}.png")
# shutil.copy2('current_capcha.png', dest_path)

def click_ok_with_retry(driver, wait, max_attempts=3):
    """Click OK button and retry if Faci3 frame doesn't appear"""

    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1} to click OK button...")

        # Switch to frame and click
        if switch_to_frames(["Faci2", "Master", "Form_Body"], driver, wait):
            try:
                report_number = wait.until(EC.visibility_of_element_located((By.ID, "F20851")))
                print("✅ Found report input!")
                report_number.clear()  # Clear first to avoid duplicate values
                report_number.send_keys("102")
                print("✅ Sent report number successfully!")

                # Call the JavaScript function directly
                result = driver.execute_script("return dirok();")
                print(f"JavaScript function result: {result}")

            except Exception as e:
                print(f"❌ Could not locate input: {e}")
                continue
        else:
            print("❌ Frame switch failed.")
            continue

        # Wait a moment for navigation to happen
        time.sleep(3)

        # Check if Faci3 frame appeared
        driver.switch_to.default_content()
        try:
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
            )
            print(f"✅ Success! Faci3 frame found on attempt {attempt + 1}")
            return True

        except:
            print(f"❌ Attempt {attempt + 1}: Faci3 frame not found")

            # Check what frames are available for debugging
            available_frames = [f.get_attribute("name") for f in driver.find_elements(By.TAG_NAME, "frame")]
            print(f"Available frames: {available_frames}")

            if attempt < max_attempts - 1:
                print("Retrying...")
                time.sleep(2)  # Wait before retry

    print(f"❌ Failed to find Faci3 frame after {max_attempts} attempts")
    return False

def get_target_frameset_rows_direct(driver, wait):
    """Direct navigation to the target frameset"""
    try:
        driver.switch_to.default_content()

        # Navigate the full path in one go
        frame_path = ["Faci3", "Master"]  # Adjust based on actual structure

        for frame_name in frame_path:
            try:
                WebDriverWait(driver, 1).until(
                    EC.frame_to_be_available_and_switch_to_it((By.NAME, frame_name))
                )
                print(f"✅ Switched to frame: {frame_name} for current rows")
            except:
                print(f"⚠️ Frame {frame_name} not found for finding current rows, continuing...")
                continue

        # Get the frameset rows
        frameset = driver.find_element(By.TAG_NAME, "frameset")
        rows = frameset.get_attribute("rows")
        return rows

    except Exception as e:
        print(f"❌ Error in direct navigation: {e}")
        return None


def ensure_on_result_page_with_retry(driver, wait, max_attempts=3):
    """Ensure we're on result page - Click first, then wait for success"""

    for attempt in range(max_attempts):
        for attempt in range(max_attempts):
            print(f"\n--- Navigation attempt {attempt + 1} ---")

            success = False  # track whether step 1 worked

            # STEP 1: Always click View Report first
            if switch_to_frames(["Faci3", "Commander"], driver, wait):
                try:
                    driver.execute_script("IM16_ViewRep_onclick();")
                    print("✅ View Report button clicked!")
                    success = True
                except Exception as e:
                    print(f"❌ Error clicking View Report: {e}")
            else:
                print("❌ Could not switch for finding View Report button")

            if not success:
                # Skip Step 2 if Step 1 failed
                if attempt < max_attempts - 1:
                    print("🔄 Retrying in 3 seconds...")
                    time.sleep(3)
                continue

            # STEP 2: Wait for Message frame after click
            try:
                driver.switch_to.default_content()
                WebDriverWait(driver, 15).until(
                    EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
                )
                WebDriverWait(driver, 15).until(
                    EC.frame_to_be_available_and_switch_to_it((By.NAME, "Message"))
                )
                print("✅ Switched to Message frame")

                # Now safe to check loading table
                table = wait.until(EC.visibility_of_element_located((By.ID, "tbl_Msg")))
                WebDriverWait(driver, 120).until(
                    lambda d: table.find_element(By.ID, "errtxt").text != "لطفا صبر کنيد."
                )
                print("✅ Loading completed - 'لطفا صبر کنيد.' message cleared!")
                return True

            except TimeoutException:
                print(f"⚠️ Attempt {attempt + 1}: Message frame or loading didn’t finish")
            except Exception as e:
                print(f"❌ Unexpected error on attempt {attempt + 1}: {e}")

            # STEP 3: Verify we're actually on result page by checking frameset
            target_rows = get_target_frameset_rows_direct()
            print(f"Current frameset rows: {target_rows}")

            if target_rows == "0,*,0,0":
                print("✅ Successfully navigated to result page!")
                return True
            else:
                print(f"⚠️ Click successful but wrong page state: {target_rows}")
                # Continue to next attempt

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

def export_table_simple(driver, wait, first_value, max_retries=3, retry_delay=2):
    """
    Simpler approach that overrides window.open to capture HTML content with retry logic
    """
    # ---- go into the Master → Form_Body frame again ----
    if switch_to_frames(["Faci3", "Master", "Form_Body"], driver, wait):
        # ---- fill the three inputs ----
        input_1 = wait.until(EC.visibility_of_element_located((By.ID, "GF10956_0")))
        # input_2 = wait.until(EC.visibility_of_element_located((By.ID, "GF078012_0")))
        # input_3 = wait.until(EC.visibility_of_element_located((By.ID, "GF078516_0")))

        input_1.clear();
        input_1.send_keys(str(first_value))
        # input_2.clear(); input_2.send_keys("16")
        # input_3.clear(); input_3.send_keys("18")
    else:
        print("❌ Frame switch failed. Aborting.")
        return None

    if not ensure_on_result_page_with_retry(driver, wait):
        print("❌ Could not navigate to result page, aborting export")
        return None

    # Step 3: Proceed with export (we're confirmed to be on result page)
    print("✅ Confirmed on result page, proceeding with export...")

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

def scrape_golestan_courses(course_status, username=None, password=None):

    load_dotenv(override=True)
    if username is None:
        username = int(os.getenv("USERNAME"))

    if password is None:
        password = os.getenv("PASSWORD")

    # Configure ChromeOptions to speed up Selenium
    chrome_options = Options()
    #chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--force-device-scale-factor=2")

    url = "https://golestan.ikiu.ac.ir/forms/authenticateuser/main.htm"   # change if needed

    driver = webdriver.Chrome()
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    try:
        # Perform the complete login sequence
        successful_login = perform_login_sequence(driver, wait, username, password)

        if successful_login:
            print("🎉 Login completed successfully!")
        else:
            print("❌ Login failed after all attempts")

        # Usage
        navigation_success = click_ok_with_retry(driver, wait)
        if not navigation_success:
            print("❌ Could not navigate to report page")

        print("✅ Successfully navigated to course page!")

        if course_status == "available":
            print("📚 Scraping available courses...")
            html_available = export_table_simple(driver, wait, 1)  # قابل اخذ
            if html_available:
                # Parse and save to JSON - function creates file and returns True
                success = parse_courses_from_html(html_available, 'available_courses.json')
                if success:
                    print("✅ Available courses saved to JSON file")
            else:
                print("⚠️ No available courses HTML retrieved")

        elif course_status == "unavailable":
            print("📚 Scraping unavailable courses...")
            html_unavailable = export_table_simple(driver, wait, 0)  # غیرقابل اخذ
            if html_unavailable:
                success = parse_courses_from_html(html_unavailable, 'unavailable_courses.json')
                if success:
                    print("✅ Unavailable courses saved to JSON file")
            else:
                print("⚠️ No unavailable courses HTML retrieved")

        elif course_status == "both":
            print("📚 Scraping both available and unavailable courses...")

            # Scrape available first
            print("  📋 Getting available courses...")
            html_available = export_table_simple(driver, wait, 1)  # قابل اخذ
            if html_available:
                success = parse_courses_from_html(html_available, 'available_courses.json')
                if success:
                    print("✅ Available courses saved to JSON file")
            else:
                print("⚠️ No available courses HTML retrieved")

            # Scrape unavailable second
            print("  📋 Getting unavailable courses...")
            html_unavailable = export_table_simple(driver, wait, 0)  # غیرقابل اخذ
            if html_unavailable:
                success = parse_courses_from_html(html_unavailable, 'unavailable_courses.json')
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

scrape_golestan_courses('unavailable')