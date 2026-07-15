from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
driver.get('http://127.0.0.1:5000/login')
time.sleep(1)

# Login
driver.find_element(By.NAME, 'email').send_keys('admin@example.com')
driver.find_element(By.NAME, 'password').send_keys('password123')
driver.find_element(By.TAG_NAME, 'button').click()
time.sleep(2)

print("Current URL:", driver.current_url)

# Execute showToast
try:
    driver.execute_script('window.showToast("Test Toast", "success");')
    print("Executed showToast successfully.")
except Exception as e:
    print("Error executing showToast:", e)

time.sleep(1)
html = driver.page_source
if "Test Toast" in html:
    print("Toast is in the DOM.")
else:
    print("Toast NOT in DOM.")

# Check for browser logs
logs = driver.get_log('browser')
for log in logs:
    print("Browser log:", log)

driver.quit()
