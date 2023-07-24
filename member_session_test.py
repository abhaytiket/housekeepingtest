from selenium import webdriver
from pymongo import MongoClient
from bson import ObjectId
import os
import time
import json
import base64
import redis
import sys

#get database client
def delete_db_token(token_id):
    client = MongoClient(os.environ['mongodb_uri'])
    db = client["tix_member_session"]
    collection = db["sessions"]
    collection.delete_one({"_id": ObjectId(token_id)})
    client.close()

#get cache client
def delete_cache_key(token_id):
    r = redis.Redis(host=os.environ['redis_host'], port=os.environ['redis_port'])
    r.delete("com.tix.member.session-session-data-"+token_id)
    r.close()

#get driver for chrome
def get_selenium_driver():
    ##set chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--ignore-certificate-errors')

    driver = webdriver.Remote(
        command_executor='http://housekeepingtest-selenium-chrome:4444',
        options=options
    )

    ##maximize the window size
    driver.maximize_window()
    time.sleep(0.5)

    return driver

#navigate to url and get the id for guest user access token
def get_token_id(driver, url):
    driver.get(url)
    time.sleep(0.5)

    ##get the guest user access token from cookie 
    guest_access_token = driver.get_cookie("session_access_token")

    ##get key for decoding jwt guest user access token
    base64_encoded_key = guest_access_token["value"].split(".")[0]
    base64_decoded_key = base64.b64decode(base64_encoded_key)
    key = json.loads(base64_decoded_key)["kid"]

    ##get id for guest user access token in database
    base64_encoded_payload = guest_access_token["value"].split(".")[1]
    #add padding to base64_encoded_payload to fix binascii.Error: Incorrect padding error
    base64_encoded_payload += "=" * ((4 - len(base64_encoded_payload) % 4) % 4)
    base64_decoded_payload = base64.b64decode(base64_encoded_payload)
    payload = json.loads(base64_decoded_payload)
    return payload["sub"]
    
#close the driver and terminate session
def close_selenium_driver(driver):
    driver.close()
    driver.quit()

##execution begins

inf = open("list.csv", "r")
for url in inf:
    driver = get_selenium_driver()
    old_token_id = get_token_id(driver, url)

    # delete document from database corresponding to token_id
    delete_db_token(old_token_id)
    
    # delete key from cache corresponding to token_id
    delete_cache_key(old_token_id)

    # refresh the page
    driver.refresh()
    new_token_id = get_token_id(driver, url)
    
    token_mismatch = old_token_id == new_token_id
    error_message_shown = ("Tenang, kami sedang beraksi mengatasinya. Coba lagi, yuk!" in driver.page_source) and ("Maaf ya, ada sedikit gangguan" in driver.page_source) 
    if token_mismatch or error_message_shown:
        sys.stdout.write(url)

    close_selenium_driver(driver)
inf.close()
print("Test execution complete")

##execution ends
