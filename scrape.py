#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timedelta
from functools import reduce
from os import path
from time import sleep

import tweepy
from bs4 import BeautifulSoup
from requests import get
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from api_key import key

######################### METADATA ATTRIBUTES ##########################
# created_at, id, id_str, full_text, truncated, display_text_range,
# entities, source, in_reply_to_status_id, in_reply_to_status_id_str,
# in_reply_to_user_id, in_reply_to_user_id_str, in_reply_to_screen_name,
# user, geo, coordinates, place, contributors, is_quote_status,
# retweet_count, favorite_count, favorited, retweeted, lang
########################################################################

DATE_FORMAT = "%Y-%m-%d"
METADATA_LIST = [  # note: "id" is already used later
    "full_text",
    "in_reply_to_status_id"
]

# colors for output
RESET = "\033[0m"
bw = lambda s: "\033[1m\033[37m" + s + RESET  # bold white
w = lambda s: "\033[1m" + s + RESET  # white
g = lambda s: "\033[32m" + s + RESET  # green
y = lambda s: "\033[33m" + s + RESET  # yellow


class Scraper:

    def __init__(self, handle):
        self.api = self.__authorize()
        self.handle = handle
        self.outfile = self.handle + ".json"
        self.new_tweets = set()  # ids
        self.tweets = self.__retrieve_existing()  # actual tweets

    @staticmethod
    def __authorize():
        consumer_key = key["consumer_key"]
        consumer_secret = key["consumer_secret"]
        access_token = key["access_token"]
        access_token_secret = key["access_token_secret"]

        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth)
        return api

    def __retrieve_existing(self):
        tweets = dict()
        if path.exists(self.outfile):
            with open(self.outfile) as o:
                tweets = json.load(o)
        return tweets

    def __check_if_scrapable(self):
        try:
            u = self.api.get_user(self.handle)
            if not u.following and u.protected:
                exit("Cannot scrape a private user unless this API account is following them.")
        except tweepy.TweepError as e:
            if e.api_code is 50:
                exit("This user does not exist.")
            else:
                raise e

    def scrape(self, start, end, by, loading_delay):
        self.__check_if_scrapable()
        print(bw("["), g("scraping user"), w("@") + y(self.handle) + g("..."), bw("]"))
        print(bw("["), g("found"), w(str(len(self.tweets))), g("existing tweets"), bw("]"))
        self.__find_tweets(start, end, by, loading_delay)
        print(bw("["), g("found"), w(str(len(self.new_tweets))), g("new tweets"), bw("]"))
        self.__retrieve_new_tweets()
        print(bw("["), g("finished scraping"), bw("]"))

    def __find_tweets(self, start, end, by, delay):
        # gross CSS stuff -- don't touch
        id_selector = ".time a.tweet-timestamp"
        tweet_selector = "li.js-stream-item"

        def slide(date, i):
            return date + timedelta(days=i)

        def form_url(start, end):
            base_url = "https://twitter.com/search"
            query = "?f=tweets&vertical=default&q=from%3A{}%20since%3A{}%20until%3A{}include%3Aretweets&src=typd"
            return base_url + query.format(self.handle, start, end)

        with webdriver.Chrome() as driver:  # options are Chrome(), Firefox(), Safari()
            days = (end - start).days + 1

            # scrape tweets using a sliding window
            window_start, ids = start, set()
            for _ in range(days)[::by]:
                # scrape the proper window of time for tweets (must format window beginning and end)
                since = window_start.strftime(DATE_FORMAT)
                until = slide(window_start, by).strftime(DATE_FORMAT)

                # query tweets and slide window along
                driver.get(form_url(since, until))
                window_start = slide(window_start, by)

                # load
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

                    for tw in found_tweets:
                        try:
                            tweet_id = tw.find_element_by_css_selector(id_selector).get_attribute("href").split("/")[-1]
                            ids.add(tweet_id)
                        except StaleElementReferenceException:
                            print("lost element reference", tw)
                except NoSuchElementException:
                    print("no tweets in time period {} -- {}".format(since, until))

            self.new_tweets = ids - self.tweets.keys()  # remove known tweets from newly found tweets

    def __retrieve_new_tweets(self):
        tweets = self.__collect_new_tweet_metadata()
        self.tweets.update(tweets)
        self.new_tweets = set()  # reset

    def __collect_new_tweet_metadata(self):
        batch_size = 100  # http://docs.tweepy.org/en/v3.5.0/api.html#API.statuses_lookup
        batch_indices = range(0, len(self.new_tweets), batch_size)
        new_tweet_list = list(self.new_tweets)
        batches = [new_tweet_list[i:i + batch_size] for i in batch_indices]

        def extract_data(tweet_list):  # dictionary of id: metadata key-value pairs
            return dict((tw["id"], {attr: tw[attr] for attr in METADATA_LIST}) for tw in tweet_list)

        def staggered_lookup(id_batch):
            queried_tweets = self.api.statuses_lookup(id_batch, tweet_mode='extended')
            sleep(6)  # don't hit API rate limit
            return extract_data(t._json for t in queried_tweets)

        # collect all tweets as a list of dictionaries
        tweet_batches = [staggered_lookup(batch) for batch in batches]

        def dict_combiner(d1, d2): return d1.update(d2) or d1  # cheeky

        # consolidate all tweet dictionaries
        tweets = reduce(dict_combiner, tweet_batches) if len(tweet_batches) is not 0 else dict()
        return tweets

    def dump_tweets(self):
        # write out
        with open(self.outfile, "w") as o:
            json.dump(self.tweets, o)
        print(bw("["), g("stored tweets in"), y(self.outfile), bw("]"))


# HELPER
def get_join_date(handle):
    """
    Helper method - checks a user's twitter page for the date they joined
    :return: the "%day %month %year" a user joined
    """
    page = get("https://twitter.com/" + handle).text
    soup = BeautifulSoup(page, "html.parser")
    date_string = soup.find("span", {"class": "ProfileHeaderCard-joinDateText"})["title"].split(" - ")[1]
    date_string = "0" + date_string if date_string[1] is " " else date_string  # add on leading 0 if needed
    return datetime.strptime(date_string, "%d %b %Y")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="scrape.py", usage="python3 %(prog)s [options]",
                                     description="scrape.py - Twitter Scraping Tool")
    parser.add_argument("-u", "--username", help="Scrape this user's Tweets", required=True)
    parser.add_argument("--since", help="Get Tweets after this date (Example: 2010-01-01).")
    parser.add_argument("--until", help="Get Tweets before this date (Example: 2018-12-07.")
    parser.add_argument("--by", help="Scrape this many days at a time", type=int, default=14)
    parser.add_argument("--delay", help="Time given to load a page before scraping it (seconds)", type=int, default=2)
    args = parser.parse_args()

    begin = datetime.strptime(args.since, DATE_FORMAT) if args.since else get_join_date(args.username)
    end = datetime.strptime(args.until, DATE_FORMAT) if args.until else datetime.now()

    user = Scraper(args.username)
    user.scrape(begin, end, args.by, args.delay)
    user.dump_tweets()
