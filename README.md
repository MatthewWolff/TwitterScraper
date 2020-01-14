# TwitterScraper

## Description

Twitter's API limits you to querying a user's most recent 3200 tweets. This is a pain in the ass. However, we can circumvent this limit using Selenium and doing some webscraping.  

We can query a user's entire time on twitter, finding the IDs for each of their tweets. From there, we can use the `tweepy` API to query the complete metadata associated with each tweet. You can adjust which metadata are collected by changing the variable `METADATA_LIST` at the top of `scrape.py`. Personally, I was just collecting text to train a model, so I only cared about the `full_text` field in addition to whether the tweet was a retweet.  

I've included a list of all available tweet attributes at the top of `scrape.py` so that you can adjust things as you wish.

## Requirements (or rather, what I used)

* python3 (3.7.3)
* Modules (via `pip`):
  * selenium (3.141.0)
  * tweepy (3.8.0)
  * requests (2.21.0)
  * beautifulsoup4 (4.7.1)
* [Chrome webdriver](https://chromedriver.chromium.org/downloads) (you can use other kinds. Personally, `brew install chromedriver`)
* [Twitter API developer credentials](https://dev.twitter.com)

## Example:

I'll run the script two times on one of my advisors. By default, the scraper will start whenever the user created their twitter. I've chosen to look at a 1 year window, scraping at two week intervals. I then go from the beginning of 2019 until the present day, at 1 week intervals. The scraped tweets are stored in a JSON file that bears the Twitter user's handle.
```bash
$ ./scrape.py --help
usage: python3 scrape.py [options]

scrape.py - Twitter Scraping Tool

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Scrape this user\'s Tweets
  --since SINCE         Get Tweets after this date (Example: 2010-01-01).
  --until UNTIL         Get Tweets before this date (Example: 2018-12-07).
  --by BY               Scrape this many days at a time
  --delay DELAY         Time given to load a page before scraping it (seconds)


$ ./scrape.py -u phillipcompeau --by 14 --since 2018-01-01 --until 2019-01-01 
[ scraping user @phillipcompeau... ]
[ 1156 existing tweets in phillipcompeau.json ]
[ searching for tweets... ]
[ found 254 new tweets ]
[ retrieving new tweets (estimated time: 18 seconds)... ]
- batch 1 of 3
- batch 2 of 3
- batch 3 of 3
[ finished scraping ]
[ stored tweets in phillipcompeau.json ]

$ ./scrape.py -u phillipcompeau --since 2019-01-01 --by 7
[ scraping user @phillipcompeau... ]
[ 1410 existing tweets in phillipcompeau.json ]
[ searching for tweets... ]
[ found 541 new tweets ]
[ retrieving new tweets (estimated time: 36 seconds)... ]
- batch 1 of 6
- batch 2 of 6
- batch 3 of 6
- batch 4 of 6
- batch 5 of 6
- batch 6 of 6
[ finished scraping ]
[ stored tweets in phillipcompeau.json ]
```

## Using the Scraper

* run `python3 scrape.py` and add the arguments you desire. Try `./scrape.py --help` for all options.
  * `-u` followed by the username [required]
  * `--since` followed by a date string, e.g., (2017-01-01). Defaults to whenever the user created their twitter
  * `--until` followed by a date string, e.g., (2018-01-01). Defaults to the current day 
  * `--by` followed by the number of days to scrape at once (default: 7)
    * If someone tweets dozens of times a day, it might be better to use a lower number
  * `--delay` followed by an integer. This will be the number of seconds to wait on each page load before reading the page
    * if your internet is slow, put this higher (default: 3 seconds)
* a browser window will pop up and begin scraping 
* when the browser window closes, metadata collection begins for all new tweets
* when collection finishes, it will dump all the data to a `.json` file that corresponds to the twitter handle
  * don't worry about running two scrapes that have a time overlap; it will only retrieve new tweets!

## Troubleshooting

* do you get a driver error when you try and execute the script?
  * make sure your browser is up to date and that you have a driver version that matches your browser version 
  * you can also open `scrape.py` and change the driver to use Chrome() or Firefox()
* does the scraper seem like it's missing tweets that you know should be there?
  * try increasing the `--delay` parameter, it likely isn't waiting long enough for everything to load

## Twitter API credentials

* sign up for a developer account here https://dev.twitter.com/
* get your key here: https://apps.twitter.com/
* once you have your key, open the file `api_key.example.py` and fill in your info
  * once you're done, remove `example` from the file name

