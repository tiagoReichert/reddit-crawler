#!/usr/bin/python
# coding=utf-8
# -------------------------------------------------------------
#       Telegram Reddit Crawler Bot
#
#       Autor: Tiago M Reichert
#       Data Inicio:  25/06/2017
#       Data Release: 26/06/2017
#       email: tiago@reichert.eti.br
#       Versão: v1.0a
# --------------------------------------------------------------
import configparser
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import scrapy
from scrapy.crawler import CrawlerProcess
import json
from multiprocessing import Process
import time
import threading
import Queue
import logging


def main():
    # Getting bot config parameters
    config = configparser.ConfigParser()
    config.read_file(open('/app/config.ini'))

    # Connecting to Telegram API
    updater = Updater(token=config['DEFAULT']['token'])
    dispatcher = updater.dispatcher

    # Adding handlers
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    nada_pra_fazer_handler = CommandHandler('NadaPraFazer', nada_pra_fazer, pass_args=True)
    dispatcher.add_handler(nada_pra_fazer_handler)

    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)

    # Starting
    print 'Starting Bot...'
    updater.start_polling()
    print 'Started!'


def start(bot, update):
    """
        Shows an welcome message and help info about the available commands.
    """
    me = bot.get_me()

    # Welcome message
    msg = "Hello!\n"
    msg += "I'm {0}.\n".format(me.first_name)
    msg += "What would you like to search on Reddis yet?\n\n"
    msg += "/NadaPraFazer askreddit;worldnews;cats - Searches for askreddit, worldnews and cats \n"

    bot.send_message(chat_id=update.message.chat_id, text=msg)


def nada_pra_fazer(bot, update, args):
    """
        Executes the reddit crawler when the user send the NadaPraFazer command.
    """
    if len(args) != 1:
        msg = "Wrong arguments \nUsage example:\n/NadaPraFazer askreddit;worldnews;cats"
        bot.send_message(chat_id=update.message.chat_id, text=msg)
    else:
        msg = "Searching...\nJust a moment, please."
        bot.send_message(chat_id=update.message.chat_id, text=msg)

        # Creating a new process with the crawler and stating
        p = Process(target=crawler, args=(args[0], bot, update.message.chat_id, ))
        p.start()


def unknown(bot, update):
    """
        Placeholder command when the user sends an unknown command.
    """
    msg = "Sorry, I don't know what you're asking for. \nTry typing /start"
    bot.send_message(chat_id=update.message.chat_id, text=msg)


def crawler(subreddits, bot, chat_id):
    """
        Scrapy reddit crawler.
    """

    # Scrapy spider
    class RedditSpider(scrapy.Spider):
        name = 'reddit'

        def parse(self, response):
            for thing in response.css('div.thing'):
                upvotes = int(thing.css('::attr(data-score)').extract_first())
                if upvotes > 5000:
                    # If up votes > 5000 then add subreddit to queue
                    queue.put(
                        json.dumps({
                            'subreddit': response.request.url.rsplit('/', 2)[1].encode('utf8'),
                            'title': str(thing.css('p.title a.title::text').extract_first().encode('utf8')),
                            'upvotes': upvotes,
                            'thread_link': response.urljoin(
                                thing.css('p.title a.title::attr(href)').extract_first().encode('utf8')),
                            'comment_link': thing.css('ul.buttons a.comments::attr(href)').extract_first().encode(
                                'utf8')
                        }))
            # go to next page
            response.css("div.quote")
            for href in response.css('span.next-button a::attr(href)'):
                yield response.follow(href, self.parse)

    # Create messages queue
    queue = Queue.Queue()

    # Start SendResult thread
    send_thread = SendResult(bot, chat_id, queue)
    send_thread.start()

    # Set urls to search
    urls = []
    for sr in subreddits.split(';'):
        urls.append('https://www.reddit.com/r/' + sr)

    # Configure and start spider
    # Set encoding to UTF-8 and disable logs
    process = CrawlerProcess({'FEED_EXPORT_ENCODING': 'utf-8', 'LOG_ENABLED': False})
    spider = RedditSpider
    spider.start_urls = urls
    process.crawl(spider)
    process.start()

    # Set stop variable on thread and wait until it's done
    send_thread.stop = True
    send_thread.join()


class SendResult(threading.Thread):
    """
        SendResult thread
    """

    def __init__(self, bot, chat_id, q):
        self.bot = bot
        self.chat_id = chat_id
        self.queue = q
        self.stop = False
        self.logger = logging.getLogger(__name__)
        threading.Thread.__init__(self)

    def run(self):
        while True:
            time.sleep(0.1) # Delay because otherwise sendMessage get some errors
            if not self.queue.empty():
                # Get message from queue
                r = self.queue.get()
                result = json.loads(r)
                # Format message
                text = '<b>' + str(result['title'].encode('utf-8')) + '</b>\n'
                text += '<b>Subreddit:</b> ' + str(result['subreddit'].encode('utf-8')) + '\n'
                text += '<b>Up Votes:</b> ' + str(result['upvotes']) + '\n'
                text += '<b>Thread Link:</b> \n' + str(result['thread_link'].encode('utf-8')) + '\n'
                text += '<b>Comment Link:</b> \n' + str(result['comment_link'].encode('utf-8')) + '\n'
                # Send message
                try:
                    self.bot.sendMessage(parse_mode='HTML', chat_id=self.chat_id, text=text)
                except Exception as e:
                    self.logger.debug(e)
            else:
                # If queue is empty and stop is True, end this thread
                if self.stop:
                    time.sleep(0.2)
                    try:
                        self.bot.sendMessage(parse_mode='HTML', chat_id=self.chat_id, text="All Reddit's sent")
                    except Exception as e:
                        self.logger.debug(e)
                    finally:
                        break
                # Otherwise wait 1 second and try again
                time.sleep(1)


if __name__ == '__main__':
    main()
