import feedparser
import re


class FeedHandler(object):

    @staticmethod
    def parse_feed(url, entries=4, modified=None):
        """
        Parses the given url, returns a list containing all available entries
        """
        if 1 <= entries <= 10:
            feeds = feedparser.parse(url, modified=modified).entries[:entries]
            if url == 'http://feeds.feedburner.com/evangelhoddia/dia':
                for f in feeds:
                    f['published'] = f['id'][:10] + ' ' + '06:00:00'
                    f['link'] = f['link'] + f['id'][:10]
                    f['daily_liturgy'] = f['summary']
                feeds.reverse()
                return feeds
            else:
                feed = feeds[:entries]
                feed.reverse()
                return feed
        else:
            feed = feedparser.parse(url, modified=modified).entries[:4]

        feed.reverse()
        return feed

    @staticmethod
    def format_url_string(string):
        """
        Formats a given url as string so it matches http(s)://adress.domain.
        This should be called before parsing the url, to make sure it is parsable
        """

        url_pattern = re.compile(r"(http(s?)):\/\/.*")
        if not url_pattern.match(string):
            string = "http://" + string

        return string

    @staticmethod
    def is_parsable(url):
        """
        Checks wether the given url provides a news feed. Return True if news are available, else False
        """

        url_pattern = re.compile(r"((http(s?))):\/\/.*")
        if not url_pattern.match(url):
            return False

        feed = feedparser.parse(url)

        # Check if result is empty
        if not feed.entries:
            return False
        # Check if entries provide updated attribute
        for post in feed.entries:
            if hasattr(post, "published") or hasattr(post, 'summary'):
                return True
        return True
