#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timedelta
from functools import reduce
from math import ceil
from os import path
from time import sleep

import tweepy
from api_key import key
from bs4 import BeautifulSoup
from requests import get, codes
from requests_oauthlib import OAuth1
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

######################### METADATA ATTRIBUTES ##########################
# created_at, id, id_str, full_text, truncated, display_text_range,
# entities, source, in_reply_to_status_id, in_reply_to_status_id_str,
# in_reply_to_user_id, in_reply_to_user_id_str, in_reply_to_screen_name,
# user, geo, coordinates, place, contributors, is_quote_status,
# retweet_count, favorite_count, favorited, retweeted, lang
########################################################################

METADATA_LIST = [  # note: "id" is automatically included (hash key)
    "created_at",
    "in_reply_to_status_id",
    "full_text"
]

# CONSTANTS
DATE_FORMAT = "%Y-%m-%d"
BATCH_SIZE = 100  # http://docs.tweepy.org/en/v3.5.0/api.html#API.statuses_lookup
API_DELAY = 6  # seconds
TWEET_LIMIT = 3200  # recent tweets
API_LIMIT = 200  # tweets at once

# OUTPUT COLORS
RESET = "\033[0m"
bw = lambda s: "\033[1m\033[37m" + str(s) + RESET  # bold white
w = lambda s: "\033[1m" + str(s) + RESET  # white
g = lambda s: "\033[32m" + str(s) + RESET  # green
y = lambda s: "\033[33m" + str(s) + RESET  # yellow


class Scraper:

    def __init__(self, handle):
        self.api = self.__authorize()
        self.handle = handle.lower()
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

    def __can_quickscrape(self):
        usr = self.api.get_user(self.handle)
        return usr.statuses_count <= TWEET_LIMIT

    def scrape(self, start, end, by, loading_delay):
        self.__check_if_scrapable()
        pprint(g("scraping user"), w("@") + y(self.handle) + g("..."))
        pprint(w(len(self.tweets)), g("existing tweets in"), y(self.outfile))
        pprint(g("searching for tweets..."))
        if self.__can_quickscrape():
            pprint(g("user has fewer than"), y(TWEET_LIMIT), g("tweets, conducting quickscrape..."))
            self.__quickscrape(start, end)
        else:
            self.__find_tweets(start, end, by, loading_delay)
            pprint(g("found"), w(len(self.new_tweets)), g("new tweets"))
            pprint(g("retrieving new tweets (estimated time: ") +
                   y(str(ceil(len(self.new_tweets) / BATCH_SIZE) * API_DELAY) + " seconds") + g(")..."))
            self.__retrieve_new_tweets()
        pprint(g("finished scraping"))

    def __quickscrape(self, start, end):
        # can't use Tweepy, need to call actual API
        def authorize():
            return OAuth1(key["consumer_key"], key["consumer_secret"], key["access_token"], key["access_token_secret"])

        def form_initial_query():
            base_url = "https://api.twitter.com/1.1/statuses/user_timeline.json"
            query = "?screen_name={}&count={}&tweet_mode=extended".format(self.handle, API_LIMIT)
            return base_url + query

        def form_subsequent_query(max_id):
            base_url = "https://api.twitter.com/1.1/statuses/user_timeline.json"  # don't use the is_retweet field!
            query = "?screen_name={}&count={}&tweet_mode=extended&max_id={}".format(self.handle, API_LIMIT, max_id)
            return base_url + query

        def make_request(query):
            request = get(query, auth=authorize())
            if request.status_code is codes.ok:
                return dict((tw["id_str"], tw) for tw in request.json())
            else:
                request.raise_for_status()

        def retrieve_payload():
            recent_payload = make_request(form_initial_query())  # query initial 200 tweets
            all_tweets = dict(recent_payload)
            for _ in range(ceil(TWEET_LIMIT / API_LIMIT) - 1):  # retrieve the other 3000 tweets
                oldest_tweet = list(recent_payload.keys())[-1]  # most recently added tweet is oldest
                recent_payload = make_request(form_subsequent_query(max_id=oldest_tweet))
                all_tweets.update(recent_payload)
            return all_tweets

        def filter_tweets(tweets):
            def get_date(tw):  # parse the timestamp as a datetime and remove timezone
                return datetime.strptime(tw[1]["created_at"], "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)

            def retweet(tw):
                return "retweeted_status" in tw[1]

            return dict(filter(lambda tweet: start <= get_date(tweet) <= end and not retweet(tweet), tweets.items()))

        def extract_metadata(tweets):
            return dict((id, {attr: tw[attr] for attr in METADATA_LIST}) for id, tw in tweets.items())

        new_tweets = extract_metadata(filter_tweets(retrieve_payload()))
        pprint(g("found"), w(len(new_tweets.keys() - self.tweets.keys())), g("new tweets"))
        self.tweets.update(new_tweets)

    def __find_tweets(self, start, end, by, delay):
        # gross CSS stuff -- don't touch
        id_selector = "article > div > div > div > div > div > div > div.r-1d09ksm > a"
        tweet_selector = "article"  # each tweet is an 'article'

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
                    found_tweets = driver.find_elements_by_tag_name(tweet_selector)
                    increment = 10

                    while len(found_tweets) >= increment:
                        # print("scrolling down to load more tweets")
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        sleep(delay)
                        found_tweets = driver.find_elements_by_tag_name(tweet_selector)
                        increment += 10

                    for tw in found_tweets:
                        try:
                            tweet_id = tw.find_element_by_css_selector(id_selector).get_attribute("href").split("/")[-1]
                            ids.add(tweet_id)
                        except StaleElementReferenceException:
                            print("lost element reference", tw)
                except NoSuchElementException:
                    print(g("> no tweets in time period {} -- {}".format(since, until)))

            self.new_tweets = ids - self.tweets.keys()  # remove known tweets from newly found tweets

    def __retrieve_new_tweets(self):
        tweets = self.__collect_new_tweet_metadata()
        self.tweets.update(tweets)
        self.new_tweets = set()  # reset

    def __collect_new_tweet_metadata(self):
        batch_indices = range(0, len(self.new_tweets), BATCH_SIZE)
        new_tweet_list = list(self.new_tweets)
        batches = [new_tweet_list[i:i + BATCH_SIZE] for i in batch_indices]
        batch_num = 0  # used for enumerating batches

        def extract_data(tweet_list):  # dictionary of id: metadata key-value pairs
            return dict((tw["id"], {attr: tw[attr] for attr in METADATA_LIST}) for tw in tweet_list)

        def staggered_lookup(id_batch):
            nonlocal batch_num
            batch_num += 1
            print(bw("-"), g("batch %s of %s" % (y(batch_num), y(len(batches)))))
            queried_tweets = self.api.statuses_lookup(id_batch, tweet_mode="extended")
            sleep(API_DELAY)  # don't hit API rate limit
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
        pprint(g("stored tweets in"), y(self.outfile))


# HELPER
def get_join_date(handle):
    """
    Helper method - checks a user's twitter page for the date they joined
    :return: the "%day %month %year" a user joined
    """
    baby_scraper = Scraper(handle)
    join_date = baby_scraper.api.get_user(handle).created_at
    return join_date


def pprint(*arguments):  # output formatting
    print(bw("["), *arguments, bw("]"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="scrape.py", usage="python3 %(prog)s [options]",
                                     description="scrape.py - Twitter Scraping Tool")
    parser.add_argument("-u", "--username", help="Scrape this user's Tweets", required=True)
    parser.add_argument("--since", help="Get Tweets after this date (Example: 2010-01-01).")
    parser.add_argument("--until", help="Get Tweets before this date (Example: 2018-12-07).")
    parser.add_argument("--by", help="Scrape this many days at a time", type=int, default=7)
    parser.add_argument("--delay", help="Time given to load a page before scraping it (seconds)", type=int, default=3)
    args = parser.parse_args()

    begin = datetime.strptime(args.since, DATE_FORMAT) if args.since else get_join_date(args.username)
    end = datetime.strptime(args.until, DATE_FORMAT) if args.until else datetime.now()

    user = Scraper(args.username)
    user.scrape(begin, end, args.by, args.delay)
    user.dump_tweets()
