# TwitterScraper

## Example:

Here I'll run the script two times in a row on myself
```bash
$ ./scrape.py -u thematthewwolff --since 2019-01-01
scrape completed. found 12 tweets
found 12 new tweets
done.

$ ./scrape.py -u thematthewwolff --since 2019-01-01
scrape completed. found 12 tweets
found 12 existing tweets
found 0 new tweets
done.
```

## Description

Twitter's API limits you to querying a user's most recent 3200 tweets. This is a pain in the ass. However, we can circumvent this limit using Selenium and doing some webscraping.  

We will query, month by month, a user's entire time on twitter. We'll collect the IDs of all their tweets—this is done within `scrape.py`. From there, we'll use the `tweepy` API to query the metadata associated with each tweet—this is done in `metadata.py`. You can adjust what metadata is collected in the same file by changing the variable `METADATA_LIST`. Personally, I was just building Markov models so I only cared about the `full_text` and if if was a retweet or not, but I've also included a list of all tweet attributes so that you can adjust it.

## Requirements (loosely)

* python3 (3.6.5)
* Modules (installed via pip3):
  * selenium (3.141.0)
  * tweepy (3.7.0)
  * requests (2.18.4)
  * beautifulsoup4 (4.6.0)
* Chrome webdriver (you can use other kinds. Personally, `brew install chromedriver`)
* [Twitter API developer credentials](https://dev.twitter.com)

## Using the Scraper

* run `python3 scrape.py` and add the arguments you need
  * `-u` followed by the username [required]
  * `--since` followed by a date string e.g (2017-01-01). Defaults to whenever the user created their twitter
  * `--until` followed by a date string e.g (2018-01-01). Defaults to the current day 
* a browser window will pop up and begin scraping month by month
* when the browser window closes, metadata collections begins
* when it finishes collection, it will dump all the data to a `.json` file that corresponds to the user
  * Don't worry about time overlaps: if you run two overlapping time frames, it will only retrieve the unique tweets!

## Troubleshooting

* do you get a driver error when you try and run the script?
  * open `scrape.py` and change the driver to use Chrome() or Firefox()
    * if neither work, google the error (you probably need to install a new driver)
* does it seem like it's not collecting tweets for days that have tweets?
  * open `scrape.py` and change the delay variable to 2 or 3

## Twitter API credentials

* sign up for a developer account here https://dev.twitter.com/
* get your key here: https://apps.twitter.com/
* once you have your key, open the file `api_key.example.py` and fill in your info
  * once you're done, remove `example` from the file name

