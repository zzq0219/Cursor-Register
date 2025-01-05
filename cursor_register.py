import os
import re
import csv
import time
import random
import argparse
import concurrent.futures
from datetime import datetime
from faker import Faker
from tempmail import EMail
from DrissionPage import ChromiumOptions, Chromium

CURSOR_LOGIN_URL = "https://authenticator.cursor.sh"
CURSOR_SIGN_UP_URL =  "https://authenticator.cursor.sh/sign-up"
CURSOR_SETTINGS_URL = "https://www.cursor.com/settings"

def cursor_turnstile(tab):
    if tab.wait.eles_loaded("@id=cf-turnstile", timeout=60, any_one = True):
        challenge_shadow_root = tab.ele('@id=cf-turnstile').child().shadow_root
        challenge_shadow_button = challenge_shadow_root.ele("tag:iframe", timeout=60).ele("tag:body").sr("xpath=//input[@type='checkbox']")
        challenge_shadow_button.click()
    tab.wait.load_start()

def sign_up(browser):
    
    empty_return = {'username': None, 'password': None, 'token': None}

    # Get temp email address
    temp_email = EMail()
    email = temp_email.address

    # Get password and name by faker
    fake = Faker()
    password = fake.password(length=12, special_chars=True, digits=True, upper_case=True, lower_case=True)
    first_name, last_name = fake.name().split(' ')

    tab = browser.new_tab(CURSOR_SIGN_UP_URL)

    try:
        tab.ele("@name=first_name").input(first_name)
        tab.ele("@name=last_name").input(last_name)
        tab.ele("@name=email").input(email)
        tab.ele("@type=submit").click()
    except Exception as e:
        print(e)
        return empty_return

    try:
        cursor_turnstile(tab)            
    except Exception as e:
        print(e)
        return empty_return
    
    try:
        tab.ele('@name=password').input(password)
        tab.ele('@type=submit').click()
    except Exception as e:
        return empty_return

    if tab.ele('This email is not available.'):
        print('This email is not available.')
        return empty_return

    try:
        cursor_turnstile(tab)            
    except Exception as e:
        print(e)
        return empty_return
    
    message = temp_email.wait_for_message()
    message_text = message.body.strip().replace('\n', '').replace('\r', '').replace('=', '')
    verify_code = re.search(r'Your verification code is (\d+)', message_text).group(1).strip()

    try:
        for idx, digit in enumerate(verify_code, start = 0):
            tab.ele(f'@data-index={idx}').input(digit)
            browser.wait(0.1, 0.3)
    except Exception as e:
        print(e)

    try:
        cursor_turnstile(tab)            
    except Exception as e:
        print(e)
        return empty_return
    
    cookies = tab.cookies().as_dict()
    token = cookies.get('WorkosCursorSessionToken', None)

    tab.close()

    print("Cursor Email: " + email)
    print("Cursor Password: " + password)
    print("Cursor Token: " + token)
    return {
        'username': email,
        'password': password,
        'token': token
    }

def register_cursor(number):

    max_workers = 5

    options = ChromiumOptions()
    options.auto_port()
    #options.headless()

    # Use turnstilePatch from https://github.com/TheFalloutOf76/CDP-bug-MouseEvent-.screenX-.screenY-patcher
    options.add_extension("turnstilePatch")
    browser = Chromium(options)

    # Run the code using multithreading
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers = max_workers) as executor:
        futures = [executor.submit(sign_up, browser) for i in range(number)]
        for future in concurrent.futures.as_completed(futures):
            print(future.result())
            result = future.result()
            results.append(result)

    browser.quit()

    print(results)
    if len(results)>0:
        formatted_date = datetime.now().strftime("%Y-%m-%d")

        csv_file = f"./output_{formatted_date}.csv"
        token_file = f"./token_{formatted_date}.csv"

        results = [result for result in results if result["token"] is not None]

        fieldnames = results[0].keys()

        # Write username, password, token into a csv file
        with open(csv_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not os.path.isfile(csv_file): writer.writeheader()
            writer.writerows(results)

        # Only write token to csv file, without header
        selected_column = 'token'
        selected_data = [{selected_column: row[selected_column]} for row in results]
        with open(token_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=[selected_column])
            writer.writerows(selected_data)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Cursor Registor')
    parser.add_argument('-n', '--number', type=int, default=2,
                        help="How many account you want")
    
    args = parser.parse_args()
    number = args.number

    register_cursor(number)
