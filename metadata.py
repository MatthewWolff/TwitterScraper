#!/usr/bin/env python3
import json
from functools import reduce
from time import sleep
from os import path

import tweepy
from api_key import key

consumer_key = key["consumer_key"]
consumer_secret = key["consumer_secret"]
access_token = key["access_token"]
access_token_secret = key["access_token_secret"]

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

######################### METADATA ATTRIBUTES ##########################
# created_at, id, id_str, full_text, truncated, display_text_range, 
# entities, source, in_reply_to_status_id, in_reply_to_status_id_str,
# in_reply_to_user_id, in_reply_to_user_id_str, in_reply_to_screen_name,
# user, geo, coordinates, place, contributors, is_quote_status,
# retweet_count, favorite_count, favorited, retweeted, lang
########################################################################

METADATA_LIST = [  # note: "id" is already used later
    "full_text",
    "in_reply_to_status_id"
]


def collect(id_list):
    batch_size = 100  # http://docs.tweepy.org/en/v3.5.0/api.html#API.statuses_lookup
    batch_indices = range(0, len(id_list), batch_size)
    batches = [id_list[i:i + batch_size] for i in batch_indices]

    def staggered_lookup(id_batch):
        tweets = api.statuses_lookup(id_batch, tweet_mode='extended')
        sleep(6)  # don't hit API rate limit
        return extract_data(t._json for t in tweets)

    tweet_batches = [staggered_lookup(batch) for batch in batches]
    return reduce(lambda d1, d2: d1.update(d2) or d1, tweet_batches) if len(tweet_batches) is not 0 else dict()


def extract_data(tweet_list):  # dictionary of id: metadata key-value pairs
    return dict((tw["id"], {attr: tw[attr] for attr in METADATA_LIST}) for tw in tweet_list)


def retrieve(outfile, tweet_ids):
    tweets = dict()
    # grab any tweets that were already stored
    if path.exists(outfile):
        with open(outfile) as o:
            tweets = json.load(o)
        print("found", len(tweets), "existing tweets")
        fresh_tweets = [tw for tw in tweet_ids if tw not in tweets.keys()]
    else:
        fresh_tweets = tweet_ids

    print("found", len(fresh_tweets), "new tweets")
    new_tweets = collect(fresh_tweets)
    tweets.update(new_tweets)

    # write out
    with open(outfile, "w") as o:
        json.dump(tweets, o)

    print("done.")
    return new_tweets


if __name__ == "__main__":
    # testing
    from os import system

    my_tweets = ["1081402741778456577", "1081400969710223360", "1081401383599915008", "1081395566351912960",
                 "1083611420581945344", "1082492292777365505", "1083110893720948745", "1083610813859090432",
                 "1083569408092590082", "1081401317854191616", "1083853757581012994", "1081400586354995200"]
    print(*retrieve("tmp", my_tweets).items(), sep="\n")
    system("rm tmp")
