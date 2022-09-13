import asyncio
# import json
import random
import traceback

import datetime

from aiohttp.client_exceptions import ServerDisconnectedError  # , ClientResponseError, \
                                      # ClientOSError
from aiohttp import ClientSession, ClientTimeout
# from bs4 import BeautifulSoup
# from aiohttp.web import HTTPNotFound

# from ProjectTypes.item import Item
from ProjectTypes.error_counter import ErrorCounter, ErrorCounterOverflowWeb, ErrorCounterOverflowParse
# from app_logger import get_logger


def zipf(texts, divs=None):
    if divs:
        return [pair for pair in zip(texts, divs) if 'ERROR' not in pair]
    else:
        return [t for t in texts if t != 'ERROR']


class Fetcher:
    def __init__(self, proxylist, blacklist_urls, blacklist_substr, item_database):

        self.error_counter_web = ErrorCounter(20, 50, 'Web')
        self.error_counter_parse = ErrorCounter(20, 50, 'Parse')
        self.exceptions_to_ignore = (ServerDisconnectedError, asyncio.exceptions.TimeoutError)

        self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)\
                                    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'}
        self._session_parameters = {'raise_for_status': True,  # resp code > 400 ->  aiohttp.ClientResponseError
                                    'timeout': ClientTimeout(total=15)}

        self.item_database = item_database
        self.urls = []
        self.proxylist = proxylist
        self.blacklist_urls = blacklist_urls
        self.blacklist_substr = blacklist_substr
        self.logger = None
        self.prev_datetime = datetime.datetime.now()  # TEST


    def item_parser(self, raw_item):
        pass

    def get_raw_items(self, urls):
        pass

    async def _async_multirequest(self, urls):
        tasks = list()
        # a = [0] # TEST

        async with ClientSession(headers=self._headers, **self._session_parameters) as session:
            for url in urls:
                task = asyncio.create_task(self.__async_request(session, url))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            # print(a[0], self.error_counter_parse.short_ctr, self.error_counter_web.short_ctr)  # TEST
            # print(datetime.datetime.now() - self.prev_datetime)  # TEST
            # self.prev_datetime = datetime.datetime.now()  # TEST
            return responses

    async def __async_request(self, session, url):
        try:
            async with session.get(url, proxy=random.choice(self.proxylist)) as response:
                text = await response.text()
                # a[0] = a[0] + 1 # TEST
                self.error_counter_web.no_error()
                return text
        except Exception as exc:
            self.error_counter_web.error_occurred()
            self.logger.warning(
                'Caught error {}\n'.format(str(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            )
            self.error_counter_web.raise_()
            return 'ERROR'

    def check_sizes(self, item):
        return self.item_database[item.key].sizes != item.sizes

    def check_is_item_new(self, item):
        if item:
            if item.key not in self.item_database or \
                    self.item_database[item.key].status != item.status or \
                    self.check_sizes(item):
                self.item_database[item.key] = item
                return True
        return False

    def _fetch(self):
        new_items = list()
        raw_items = self.get_raw_items(self.urls)
        for raw_item in raw_items:
            item = self.item_parser(raw_item)
            if self.check_is_item_new(item):
                new_items.append(item)

        # if new_items:
        #     with open('test.txt', 'a') as f:
        #         f.write(str(texts))
        #         f.write('\n')
        return tuple(new_items)

    def fetch_unlimited_except(self):
        try:
            result = self._fetch()
            self.error_counter_parse.no_error()
            return result
        except ErrorCounterOverflowWeb:
            raise
        except Exception as exc:
            if self.error_counter_parse.error_occurred():
                self.logger.warning(
                    'Caught error {}\n'.format(str(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                )
            self.error_counter_parse.raise_()

    def check_name_in_blacklist(self, name):
        name_lower = name.lower()
        for s in self.blacklist_substr:
            if s in name_lower:
                return True
        return False

    # def fetch_hard_except(self):
    #     try:
    #         result = self._fetch()
    #         self.error_counter.no_error()
    #         return result
    #
    #     except self.exceptions_to_ignore as ig:
    #         ctr = self.error_counter.error_occurred()
    #         self.logger.warning('Caught error [{}]\nErrors in last calls: {}/{}  {}/{}\n'. \
    #                             format(ig, ctr[0], self.error_counter.short_limit,
    #                                    ctr[1], self.error_counter.long_limit))
    #         if ctr[0] == self.error_counter.short_limit:
    #             raise ErrorCounterOverflow
    #
    #     except ClientResponseError as cre:
    #         if cre.status in self.response_codes_to_ignore:
    #             ctr = self.error_counter.error_occurred()
    #             self.logger.warning('Caught error [{}]\nErrors in last calls: {}/{}  {}/{}\n'. \
    #                                 format(cre, ctr[0], self.error_counter.short_limit,
    #                                        ctr[1], self.error_counter.long_limit))
    #             if ctr[0] == self.error_counter.short_limit:
    #                 raise ErrorCounterOverflow
    #         else:
    #             self.logger.error('Unexpected error [{}]\n'.format(cre))
    #             raise
    #
    #     except ClientOSError as coe:
    #         if coe.errno in self.oserror_codes_to_ignore:
    #             ctr = self.error_counter.error_occurred()
    #             self.logger.warning('Caught error [{}]\nErrors in last calls: {}/{}  {}/{}\n'. \
    #                                 format(coe, ctr[0], self.error_counter.short_limit,
    #                                        ctr[1], self.error_counter.long_limit))
    #             if ctr[0] == self.error_counter.short_limit:
    #                 raise ErrorCounterOverflow
    #         else:
    #             self.logger.error('Unexpected error [{}]\n'.format(coe))
    #             raise
    #
    #     except Exception as e:
    #         self.logger.error('Unexpected error [{}]\n'.format(e))
    #         raise
