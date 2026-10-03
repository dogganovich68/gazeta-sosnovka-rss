#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
import re

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

def extract_full_content(url):
    """Извлекает полный текст новости со страницы."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        full_text_parts = []
        
        # Стратегия 1: Ищем по специфичным классам
        possible_selectors = [
            {'class_': 'item__content'},
            {'class_': 'content'},
            {'class_': 'post-content'},
            {'class_': 'news-content'},
            {'class_': 'entry-content'},
            {'class_': 'article-content'},
            {'class_': 'article-body'},
            {'name': 'article'},
        ]
        
        content_block = None
        for selector in possible_selectors:
            content_block = soup.find(**selector)
            if content_block:
                break
        
        if content_block:
            # Берём все параграфы и заголовки внутри блока
            for elem in content_block.find_all(['p', 'h2', 'h3', 'h4', 'blockquote']):
                text = elem.get_text(strip=True)
                if text and len(text) > 10:
                    if elem.name in ['h2', 'h3', 'h4']:
                        full_text_parts.append(f"<h3>{text}</h3>")
                    elif elem.name == 'blockquote':
                        full_text_parts.append(f"<blockquote>{text}</blockquote>")
                    else:
                        full_text_parts.append(f"<p>{text}</p>")
        
        # Стратегия 2: Если не нашли блок, берём все параграфы со страницы
        if not full_text_parts:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    # Исключаем футер, хедер, навигацию
                    parent_classes = ' '.join(p.parent.get('class', [])) if p.parent else ''
                    if not any(x in parent_classes.lower() for x in ['footer', 'header', 'nav', 'menu', 'sidebar']):
                        full_text_parts.append(f"<p>{text}</p>")
        
        return '\n'.join(full_text_parts)
        
    except Exception as e:
        print(f"Ошибка при извлечении контента из {url}: {e}")
        return ""

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
                    short_description = data.get('description', '')
                    image = data.get('image', [''])[0] if isinstance(data.get('image'), list) else data.get('image', '')
                    
                    # Извлекаем полный контент
                    full_content = extract_full_content(url)
                    
                    # Если полный контент не найден, используем краткое описание
                    if not full_content:
                        full_content = f"<p>{short_description}</p>"
                    
                    try:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                    except Exception:
                        pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

                    return {
                        'title': title, 
                        'link': url, 
                        'short_description': short_description,
                        'full_content': full_content,
                        'pubDate': pub_date, 
                        'image': image
                    }
            except json.JSONDecodeError:
                continue
    except requests.RequestException:
        pass
    return None

def generate_rss(news_items):
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    
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
        
        # ВАЖНО: В description кладём полный текст — многие ридеры показывают именно его
        ET.SubElement(xml_item, 'description').text = item['full_content']
        
        # Также добавляем content:encoded для ридеров, которые его поддерживают
        content_elem = ET.SubElement(xml_item, '{http://purl.org/rss/1.0/modules/content/}encoded')
        content_elem.text = item['full_content']
        
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
        print(f"Обработка: {url}")
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
