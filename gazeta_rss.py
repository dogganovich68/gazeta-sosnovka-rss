#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
import re
import os

SITE_URL = "https://gazetasosnovka.ru/"
OUTPUT_FILE = "gazeta_sosnovka_rss.xml"
MAX_NEWS_ITEMS = 20

def get_news_links():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    response = requests.get(SITE_URL, headers=headers, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    links = set()
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '/news/' in href:
            full_url = SITE_URL.rstrip('/') + href if href.startswith('/') else href
            links.add(full_url)
            
    return list(links)

def parse_news_article(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = next((item for item in data if item.get('@type') == 'NewsArticle'), None)
                
                if data and data.get('@type') == 'NewsArticle':
                    title = re.sub(r'\s+', ' ', data.get('headline', 'Без заголовка')).strip()
                    date_str = data.get('datePublished', '')
                    description = data.get('description', '')
                    image = data.get('image', [''])[0] if isinstance(data.get('image'), list) else data.get('image', '')
                    
                    try:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                    except Exception:
                        pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

                    return {'title': title, 'link': url, 'description': description, 'pubDate': pub_date, 'image': image}
            except json.JSONDecodeError:
                continue
    except requests.RequestException:
        pass
    return None

def generate_rss(news_items):
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    
    ET.SubElement(channel, 'title').text = 'Сосновское слово — Новости'
    ET.SubElement(channel, 'link').text = SITE_URL
    ET.SubElement(channel, 'description').text = 'Последние новости Сосновского муниципального округа'
    ET.SubElement(channel, 'language').text = 'ru'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

    for item in news_items:
        if not item: continue
        xml_item = ET.SubElement(channel, 'item')
        ET.SubElement(xml_item, 'title').text = item['title']
        ET.SubElement(xml_item, 'link').text = item['link']
        ET.SubElement(xml_item, 'description').text = item['description']
        ET.SubElement(xml_item, 'pubDate').text = item['pubDate']
        ET.SubElement(xml_item, 'guid', isPermaLink='true').text = item['link']
        if item['image']:
            ET.SubElement(xml_item, 'enclosure', url=item['image'], type='image/jpeg')

    xml_string = ET.tostring(rss, encoding='utf-8')
    return minidom.parseString(xml_string).toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

def main():
    print("Получение списка новостей...")
    links = get_news_links()[:MAX_NEWS_ITEMS]
    news_items = []
    
    for url in links:
        article = parse_news_article(url)
        if article:
            news_items.append(article)
            
    news_items.sort(key=lambda x: x['pubDate'], reverse=True)
    
    print("Генерация RSS...")
    rss_xml = generate_rss(news_items)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_xml)
    print(f"Готово! Обработано новостей: {len(news_items)}")

if __name__ == '__main__':
    main()
