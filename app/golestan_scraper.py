
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchFrameException
import time
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import json

load_dotenv(override=True)

# Configure ChromeOptions to speed up Selenium
chrome_options = Options()
#chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--force-device-scale-factor=2")

url = "https://golestan.ikiu.ac.ir/forms/authenticateuser/main.htm"   # change if needed
USERNAME = int(os.getenv("USERNAME"))
PASSWORD = os.getenv("PASSWORD")

driver = webdriver.Chrome()
driver.get(url)
wait = WebDriverWait(driver, 10)

def switch_to_frames(frame_names, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            time.sleep(2)
            driver.switch_to.default_content()
            for name in frame_names:
                # For debugging
                frames = driver.find_elements(By.TAG_NAME, "frame")
                print([f.get_attribute("name") for f in frames])
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, name)))
            return True  # All frames switched successfully
        except Exception as e:
            print(f"❌ Attempt {attempt+1}: Could not switch to frame sequence {frame_names} | Error: {e}")
            attempt += 1
            time.sleep(1)  # Wait a bit longer before retrying
    return False  # All attempts failed



if switch_to_frames(["Faci1", "Master", "Form_Body"]):
    try:
        username_input = wait.until(EC.visibility_of_element_located((By.ID, "F80351")))
        print("✅ Found username input!")
        username_input.click()
        username_input.clear()
        username_input.send_keys(USERNAME)
        print("✅ Sent username keys successfully!")

        password_input = wait.until(EC.visibility_of_element_located((By.ID, "F80401")))
        print("✅ Found password input!")
        password_input.click()
        password_input.clear()
        password_input.send_keys(PASSWORD)
        print("✅ Sent password keys successfully!")

        img = wait.until(EC.visibility_of_element_located((By.ID, "imgCaptcha")))
        print(img.location, img.size)
        img.screenshot("captcha.png")

    except Exception as e:
        print("❌ Could not locate input:", e)
        driver.switch_to.default_content()
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        for f in frames:
            print("Frame candidate:", f.get_attribute("name"), f.get_attribute("id"), f.get_attribute("src"))
else:
    print("❌ Frame switch failed. Aborting.")


refresh_capcha = False
while  True:
    if refresh_capcha:
        if switch_to_frames(["Faci1", "Master", "Form_Body"]):
            try:
                img = wait.until(EC.visibility_of_element_located((By.ID, "imgCaptcha")))
                img.screenshot("captcha.png")
            except Exception as e:
                print("❌ Unable to locate CAPTCHA image:", e)
        else:
            print("❌ Frame switch failed for getting CAPTCHA. Aborting.")


    # First, locate the captcha input field
    capcha_input = wait.until(EC.visibility_of_element_located((By.ID, "F51701")))
    print("✅ Found capcha input!")
    capcha_input.click()
    capcha_input.clear()

    # Wait for user to enter exactly 5 characters
    print("Please enter the 5-character captcha...")
    WebDriverWait(driver, 120).until(lambda driver: len(driver.find_element(By.ID, "F51701").get_attribute("value")) == 5)
    print("✅ 5 characters entered, proceeding...")


    # Press log in
    login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLog")))
    login_button.click()

    # Try waiting for the error table
    error_happened = False
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame("Faci1")
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Message")))
        table = wait.until(EC.visibility_of_element_located((By.ID, "tbl_Msg")))

        # Wait until errtxt text is not 'wait...' (use correct string as in UI)
        wait.until(lambda d: table.find_element(By.ID, "errtxt").text != "لطفا صبر کنيد.")

        err_txt = table.find_element(By.ID, "errtxt").text

        err_num = table.find_element(By.ID, "errcnt").text
        print(err_num)
        if "پيغام" in err_num:
            error_happened = True
    except NoSuchFrameException:
        error_happened = False

    # If CAPTCHA error, refresh it and repeat
    if error_happened:
        print('an error occurred:', err_txt)
        if err_txt == "لطفا كد امنيتي را به صورت صحيح وارد نماييد":
            print("CAPTCHA was incorrect. Refreshing CAPTCHA, please try again.")

            # click on CAPCHA to generate new one
            # switch_to_frames(["Faci1", "Master", "Form_Body"])
            # captcha_img = wait.until(EC.element_to_be_clickable((By.ID, "imgCaptcha")))
            # captcha_img.click()

            refresh_capcha = True
            continue  # Loop back for user to enter new CAPTCHA
        elif err_txt == "کد1 : شناسه کاربري يا گذرواژه اشتباه است.":
            pass
        else: # other error
            break
    else:
        break  # Login succeeded OR other error; exit loop


# Proceed with the rest of your automation...
print("Login successful or unhandled error encountered.")

# if switch_to_frames(["Faci2", "Master", "Form_Body"]):
#     try:
#         report_number = wait.until(EC.visibility_of_element_located((By.ID, "F20851")))
#         print("✅ Found username input!")
#         report_number.send_keys(102)
#         print("✅ Sent report number successfully!")
#
#         # ok_button = wait.until(EC.element_to_be_clickable((By.ID, "OK")))
#         # print("✅ Found OK button!")
#         # time.sleep(1)
#         # ok_button.click()
#         # print("✅ OK button clicked!")
#
#         # Call the JavaScript function directly
#         result = driver.execute_script("return dirok();")
#         print(f"JavaScript function result: {result}")
#
#     except Exception as e:
#         print("❌ Could not locate input:", e)
#         driver.switch_to.default_content()
#         frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
#         for f in frames:
#             print("Frame candidate:", f.get_attribute("name"), f.get_attribute("id"), f.get_attribute("src"))
# else:
#     print("❌ Frame switch failed. Aborting.")

def click_ok_with_retry(max_attempts=3):
    """Click OK button and retry if Faci3 frame doesn't appear"""

    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1} to click OK button...")

        # Switch to frame and click
        if switch_to_frames(["Faci2", "Master", "Form_Body"]):
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


# Usage
success = click_ok_with_retry()
if success:
    print("✅ Successfully navigated to report page!")
    # Continue with your export_table_simple function here
else:
    print("❌ Could not navigate to report page")


def get_target_frameset_rows_direct():
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
                print(f"✅ Switched to frame: {frame_name}")
            except:
                print(f"⚠️ Frame {frame_name} not found, continuing...")
                continue

        # Get the frameset rows
        frameset = driver.find_element(By.TAG_NAME, "frameset")
        rows = frameset.get_attribute("rows")
        return rows

    except Exception as e:
        print(f"❌ Error in direct navigation: {e}")
        return None


def ensure_on_result_page_with_retry(max_attempts=3):
    """Ensure we're on result page using nested frameset check with retry"""

    for attempt in range(max_attempts):
        print(f"\n--- Navigation attempt {attempt + 1} ---")

        target_rows = get_target_frameset_rows_direct()
        print(f"Current frameset rows: {target_rows}")

        if target_rows == "0,*,0,0":
            print("✅ On result page!")
            return True
        elif target_rows == "40,0,*,0":
            print("⚠️ Still on report page, clicking View Report...")

            # Click View Report button
            if switch_to_frames(["Faci3", "Commander"]):
                try:
                    driver.execute_script("IM16_ViewRep_onclick();")
                    print("✅ View Report button clicked!")
                    time.sleep(3)  # Wait for navigation
                except Exception as e:
                    print(f"❌ Error clicking View Report: {e}")
            else:
                print("❌ Could not switch to Commander frame")
        else:
            print(f"❓ Unknown state: {target_rows}")

        if attempt < max_attempts - 1:
            time.sleep(2)  # Wait before retry

    print(f"❌ Failed to reach result page after {max_attempts} attempts")
    return False

def export_table_simple(driver, wait, first_value):
    """
    Simpler approach that overrides window.open to capture HTML content
    """
    # ---- go into the Master → Form_Body frame again ----
    if switch_to_frames(["Faci3", "Master", "Form_Body"]):
        # ---- fill the three inputs ----
        input_1 = wait.until(EC.visibility_of_element_located((By.ID, "GF10956_0")))
        input_2 = wait.until(EC.visibility_of_element_located((By.ID, "GF078012_0")))
        input_3 = wait.until(EC.visibility_of_element_located((By.ID, "GF078516_0")))

        input_1.clear(); input_1.send_keys(str(first_value))
        input_2.clear(); input_2.send_keys("16")
        input_3.clear(); input_3.send_keys("18")
    else:
        print("❌ Frame switch failed. Aborting.")
        return None

    if not ensure_on_result_page_with_retry():
        print("❌ Could not navigate to result page, aborting export")
        return None

    # Step 3: Proceed with export (we're confirmed to be on result page)
    print("✅ Confirmed on result page, proceeding with export...")

    # Switch to Commander frame for export
    driver.switch_to.default_content()
    WebDriverWait(driver, 15).until(
        EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
    )
    driver.switch_to.frame("Commander")

    # Override window.open to capture the HTML instead of opening a popup
    driver.execute_script("""
        window.capturedHTML = null;
        window.originalOpen = window.open;
        window.open = function(url, name, features) {
            // Create a fake window object
            var fakeWindow = {
                document: {
                    write: function(html) {
                        window.capturedHTML = html;
                    },
                    close: function() {}
                },
                close: function() {}
            };
            return fakeWindow;
        };
    """)

    # Now click the export button - it will use our overridden window.open
    try:
        export_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ExToEx"))
        )
        export_btn.click()

        # Give it a moment to execute
        time.sleep(1)

        # Get the captured HTML
        html = driver.execute_script("return window.capturedHTML;")

        # Restore original window.open
        driver.execute_script("window.open = window.originalOpen;")

        if html:
            print("✅ Table data captured successfully!")
        else:
            print("⚠️ No HTML captured")

    except Exception as e:
        print(f"❌ Export failed: {e}")
        html = None
        # Restore window.open even on error
        driver.execute_script("if (window.originalOpen) window.open = window.originalOpen;")

    # ---- click "Back to Filter" ----
    driver.switch_to.default_content()
    WebDriverWait(driver, 5).until(
        EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3"))
    )
    driver.switch_to.frame("Commander")
    back_to_filter = driver.find_element(By.ID, 'IM91_gofilter')
    time.sleep(1)
    back_to_filter.click()

    return html

# Usage
wait = WebDriverWait(driver, 10)
html_zero = export_table_simple(driver, wait, 0) # غیرقابل اخذ
html_one  = export_table_simple(driver, wait, 1) # قابل اخذ


# Wait for the element to be clickable and click it
driver.switch_to.default_content()
logout_element = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//span[text()='خروج']"))
)
logout_element.click()
print("✅ Clicked logout successfully!")
driver.quit()
print("✅ Driver closed successfully!")

soup = BeautifulSoup(html_one, "html.parser")

courses = {}

# skip the header row (.DTitle)
for row in soup.select("tr:not(.DTitle)"):
    cells = [c.get_text(strip=True) for c in row.find_all("td")]
    if not cells or len(cells) < 17:
        continue

    code = cells[6]                      # شماره و گروه درس
    name = cells[7]                      # نام درس
    credits = int(cells[8])              # کل واحد
    instructor = cells[14] or "اساتيد گروه آموزشي"
    schedule_raw = cells[15]             # زمان و مكان ارائه
    exam_raw = cells[16]                 # زمان و مكان امتحان
    location_desc = cells[23] if len(cells) > 23 else ""

    # --- parse schedule ---
    schedule = []
    import re
    # Example: "درس(ت): شنبه 13:00-15:00 ز مکان: آتليه ..."
    for m in re.finditer(r"(?P<day>\S+)\s+(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})(?:\s*(?P<parity>[فز])?)", schedule_raw):
        schedule.append({
            "day": m.group("day"),
            "start": m.group("start"),
            "end": m.group("end"),
            "parity": m.group("parity") or ""
        })

    # --- parse exam date/time ---
    exam_time = ""
    m = re.search(r"(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}-\d{2}:\d{2})", exam_raw)
    if m:
        exam_time = f"{m.group(1)} - {m.group(2)}"

    courses[code] = {
        "code": code,
        "name": name,
        "credits": credits,
        "instructor": instructor.strip(),
        "schedule": schedule,
        "location": location_desc,
        "description": "",
        "exam_time": exam_time
    }

result = {"courses": courses}

print(json.dumps(result, ensure_ascii=False, indent=2))
