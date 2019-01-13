#!/usr/bin/env python3

import argparse
import datetime
import json
from time import sleep

import metadata
from bs4 import BeautifulSoup
from requests import get
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys


def get_join_date(handle):
    """
    Helper method - checks a user's twitter page for the date they joined
    :return: the "%day %month %year" a user joined
    """
    page = get("https://twitter.com/" + handle).text
    soup = BeautifulSoup(page, "html.parser")
    date_string = soup.find("span", {"class": "ProfileHeaderCard-joinDateText"})["title"].split(" - ")[1]
    date_string = "0" + date_string if date_string[1] is " " else date_string  # add on leading 0 if needed
    return datetime.datetime.strptime(date_string, "%d %b %Y")


def format_day(date):
    day = "0" + str(date.day) if len(str(date.day)) is 1 else str(date.day)
    month = "0" + str(date.month) if len(str(date.month)) is 1 else str(date.month)
    year = str(date.year)
    return "-".join([year, month, day])


def form_url(user, start, end):
    base_url = "https://twitter.com/search"
    query = "?f=tweets&vertical=default&q=from%3A{}%20since%3A{}%20until%3A{}include%3Aretweets&src=typd"
    return base_url + query.format(user, start, end)


def increment_day(date, i):
    return date + datetime.timedelta(days=i)


def scrape(start, end, user, by=31):  # 31 days at a time
    # no touchie
    id_selector = ".time a.tweet-timestamp"
    tweet_selector = "li.js-stream-item"

    # customize
    delay = 2  # time to wait in seconds on each page load before reading the page
    driver = webdriver.Chrome()  # options are Chrome() Firefox() Safari()
    days = (end - start).days + 1
    ids = []

    for __ in range(days)[::by]:
        d1 = format_day(increment_day(start, 0))
        d2 = format_day(increment_day(start, by))
        url = form_url(user, start=d1, end=d2)
        driver.get(url)
        sleep(delay)

        try:
            found_tweets = driver.find_elements_by_css_selector(tweet_selector)
            increment = 10

            while len(found_tweets) >= increment:
                # print("scrolling down to load more tweets")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(delay)
                found_tweets = driver.find_elements_by_css_selector(tweet_selector)
                increment += 10

            # print("{} tweets found, {} total".format(len(found_tweets), len(ids)))

            for tweet in found_tweets:
                try:
                    tweet_id = tweet.find_element_by_css_selector(id_selector).get_attribute("href").split("/")[-1]
                    ids.append(tweet_id)
                except StaleElementReferenceException:
                    print("lost element reference", tweet)
        except NoSuchElementException:
            print("no tweets in this time period")

        start = increment_day(start, by)

    print("scrape completed. found", len(ids), "tweets")
    driver.close()
    return ids


def dump_data(ids, twitter_ids_filename="all_ids.json"):
    all_ids = set(ids)
    try:  # combine old and new tweets
        with open(twitter_ids_filename) as f:
            old_ids = set(json.load(f))
            print("new tweets found on this scrape:", len(old_ids - all_ids))
            all_ids &= old_ids  # unique
    except FileNotFoundError:
        pass

    with open(twitter_ids_filename, "w") as outfile:
        data_to_write = list(all_ids)
        json.dump(data_to_write, outfile)
        print("total tweet count:", len(data_to_write))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="scrape.py", usage="python3 %(prog)s [options]",
                                     description="scrape.py - Twitter Scraping Tool")
    parser.add_argument("-u", help="Scrape this user's Tweets")
    parser.add_argument("--since", help="Get Tweets after this date (Example: 2010-01-01).")
    parser.add_argument("--until", help="Get Tweets before this date (Example: 2018-12-07.")
    args = parser.parse_args()

    date_format = "%Y-%m-%d"
    parse_date = datetime.datetime.strptime
    _from = parse_date(args.since, date_format) if args.since is not None else get_join_date(args.u)
    _to = parse_date(args.until, date_format) if args.until is not None else datetime.datetime.now()

    tweet_ids = scrape(_from, _to, user=args.u)
    metadata.retrieve(outfile=args.u + ".json", tweet_ids=tweet_ids)
