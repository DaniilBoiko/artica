import asyncio
from bs4 import BeautifulSoup
import requests
import stem
import socks
import aiohttp


async def download(url):
    response = await aiohttp.get(url)
    soup = await BeautifulSoup(response.content, 'html.parser')
    return soup

futures = [download('https://link.springer.com/search/page/'+str(i)+'?facet-content-type="Journal') for i in range(1, 
                                                                                                                  11)]

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait(futures))
