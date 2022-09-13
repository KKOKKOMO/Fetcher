import asyncio
import datetime
import json
import random
import traceback

from aiohttp.client_exceptions import ServerDisconnectedError, ClientResponseError
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup

from ProjectTypes.item import Item
from ProjectTypes.error_counter import ErrorCounter, ErrorCounterOverflowWeb, ErrorCounterOverflowParse
from app_logger import get_logger
from fetcher_interface import Fetcher, zipf


class BeliefFetcher(Fetcher):
    def __init__(self, proxylist, blacklist_urls, blacklist_substr, item_database):

        super().__init__(proxylist, blacklist_urls, blacklist_substr, item_database)
        self.logger = get_logger('Belief Fetcher')
        self.urls = [
            'https://store.beliefmoscow.com/collection/nike',
            'https://beliefmoscow.com/collection/nike-sb',
            'https://store.beliefmoscow.com/collection/jordan'
        ]
        self._session_parameters = {'raise_for_status': True,  # resp code > 400 ->  aiohttp.ClientResponseError
                                    'timeout': ClientTimeout(total=5)}

    async def __SPECIAL_multirequest(self, urls):
        tasks = list()
        # a = [0]  # TEST
        async with ClientSession(headers=self._headers, **self._session_parameters) as session:
            for url in urls:
                task = asyncio.create_task(self.__SPECIAL_request(session, url))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            # print(a)
            return list(filter(None, responses))

    async def __SPECIAL_request(self, session, url):
        try:
            proxy = random.choice(self.proxylist)
            async with session.get(url, proxy=proxy) as response:
                pid = BeautifulSoup(await response.text(), 'html5lib'). \
                    findChild('meta', attrs={'name': 'product-id'}).get('content')
                json_url = 'https://beliefmoscow.com/products_by_id/{}.json'.format(pid)
                async with session.get(json_url, proxy=proxy) as json_response:
                    # a[0] = a[0] + 1  # TEST
                    return await json_response.text()

        except Exception as exc:
            self.logger.warning(
                'Caught error {}\n'.format(str(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            )
            return 'ERROR'

    def _text_to_urls_divs(self, text):
        urls, divs = [], []
        product_elms = BeautifulSoup(text, 'html5lib').findChildren('div')
        for elm in product_elms:
            if elm.get('class') == ['lg-grid-3', 'sm-grid-6', 'mc-grid-6', 'padded-inner-sides']:
                url = 'https://store.beliefmoscow.com' + elm.findChild('div', attrs={
                    'class': 'product_preview-preview'}).findChild('a').get('href')
                if url not in self.blacklist_urls:
                    urls.append(url)
                    divs.append(elm.findChild('div'))
        return urls, divs

    def get_item_urls_divs(self, urls):
        product_urls = []
        product_divs = []
        texts = asyncio.run(self._async_multirequest(urls))
        texts = zipf(texts)
        for text in texts:
            urls, divs = self._text_to_urls_divs(text)
            product_urls += urls
            product_divs += divs
        return product_urls, product_divs

    def get_raw_items(self, urls):
        item_urls, item_divs = self.get_item_urls_divs(urls)
        item_texts = asyncio.run(self.__SPECIAL_multirequest(item_urls))
        return zipf(item_texts, item_divs)

    def item_parser(self, raw_item):
        product_from_api = json.loads(raw_item[0])['products'][0]
        product_html = raw_item[1]
        img = product_from_api['first_image']['url']
        link = 'https://beliefmoscow.com' + product_from_api['url']
        name = product_html.findChild('div', attrs={'class': 'product_preview-title'}).findChild('a').get('title')
        if self.check_name_in_blacklist(name):
            return None
        price = product_html.findChild('div', attrs={'class': ['product_preview-prices', 'prices']}).findChildren('span')[-1].text
        sizes_buff = [{'var': variant['id'], 'text': variant['title'], 'quantity': variant['quantity']} for variant in
                      product_from_api['variants'] if variant['available']]
        sizes_str, status = str(), str()
        sizes = list()
        if sizes_buff:
            for size in sizes_buff:
                sizes_str += '{} | {}\n'.format(size['text'], size['quantity'])
            status = 'IN STOCK'
            sizes.append(sizes_str)
        else:
            status = 'OUT OF STOCK'
        item = Item(name=name, link=link, sizes=sizes, price=price, status=status, img=img)
        return item


if __name__ == '__main__':
    pass
