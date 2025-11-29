import sys
import os
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime

HTML_FILE = "opinion.html"
XML_FILE = "articles.xml"
MAX_ITEMS = 500

# Load HTML
if not os.path.exists(HTML_FILE):
    print("HTML not found")
    sys.exit(1)

with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

articles = []

def extract_article(container, link_selector, title_selectors, desc_selector, time_selector, img_selector):
    """Generic function to extract article data"""
    results = []
    for item in soup.select(container):
        link = item.select_one(link_selector)
        if not link:
            continue
        url = link.get("href")
        if not url:
            continue
        
        # Try multiple title selectors
        title = None
        for selector in title_selectors:
            title_tag = item.select_one(selector)
            if title_tag:
                # Remove shoulder span if present
                shoulder = title_tag.select_one("span.shoulder")
                if shoulder:
                    shoulder.decompose()
                title = title_tag.get_text(strip=True)
                break
        
        if not title:
            continue
        
        # Extract description
        desc_tag = item.select_one(desc_selector)
        desc = desc_tag.get_text(strip=True) if desc_tag else ""
        
        # Extract time
        time_tag = item.select_one(time_selector)
        pub = time_tag.get_text(strip=True) if time_tag else ""
        # Clean up time text
        if pub:
            pub = pub.replace("", "").strip()
        
        # Extract image
        img_tag = item.select_one(img_selector)
        img = img_tag.get("src", "") if img_tag else ""
        
        results.append({"url": url, "title": title, "desc": desc, "pub": pub, "img": img})
    return results

# --- 1. DCatLead (main lead) ---
articles.extend(extract_article(
    "div.DCatLead",
    "a[href*='/opinion/']",
    ["h1", "h2", "h3"],
    "p.CatDesc, p.summary3, p",
    ".publishTime, p.time",
    "img"
))

# --- 2. Catcards (category cards) ---
articles.extend(extract_article(
    "div.Catcards",
    "a[href*='/opinion/']",
    ["h3", "h2", "h1"],
    "p",
    ".publishTime, p.time",
    "img"
))

# --- 3. CatListNews (sub news) ---
articles.extend(extract_article(
    "div.CatListNews",
    "a[href*='/opinion/']",
    ["h3", "h2", "h1"],
    "p",
    ".publishTime, p.time",
    "img"
))

# --- 4. itemDiv format (new format) ---
articles.extend(extract_article(
    "div.itemDiv",
    "a.linkOverlay, a[href*='/opinion/']",
    ["h2.title3", "h3", "h2", "h1"],
    "p.summary3, p",
    "p.time, .publishTime",
    "img"
))

# --- 5. Catch-all: any link with /opinion/ in href ---
for link in soup.select("a[href*='/opinion/']"):
    url = link.get("href")
    if not url:
        continue
    
    # Try to find title in or near the link
    title = None
    # Check if link itself has text
    if link.get_text(strip=True) and not link.find("img"):
        title = link.get_text(strip=True)
    else:
        # Look for title in parent or nearby elements
        parent = link.parent
        if parent:
            for tag in ["h1", "h2", "h3", "h4"]:
                title_tag = parent.find(tag)
                if title_tag:
                    shoulder = title_tag.select_one("span.shoulder")
                    if shoulder:
                        shoulder.decompose()
                    title = title_tag.get_text(strip=True)
                    break
    
    if not title:
        continue
    
    # Find description
    desc = ""
    parent = link.parent
    if parent:
        desc_tag = parent.find("p", class_=lambda x: x and "summary" in x) or parent.find("p")
        if desc_tag:
            desc = desc_tag.get_text(strip=True)
    
    # Find time
    pub = ""
    if parent:
        time_tag = parent.find(class_=lambda x: x and ("time" in x.lower() if x else False))
        if time_tag:
            pub = time_tag.get_text(strip=True).replace("", "").strip()
    
    # Find image
    img = ""
    if parent:
        img_tag = parent.find("img")
        if img_tag:
            img = img_tag.get("src", "")
    
    articles.append({"url": url, "title": title, "desc": desc, "pub": pub, "img": img})

# --- Load or create XML ---
if os.path.exists(XML_FILE):
    try:
        tree = ET.parse(XML_FILE)
        root = tree.getroot()
    except ET.ParseError:
        root = ET.Element("rss", version="2.0")
else:
    root = ET.Element("rss", version="2.0")

# Ensure channel exists
channel = root.find("channel")
if channel is None:
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Opinion Articles"
    ET.SubElement(channel, "link").text = "https://protidinerbangladesh.com/opinion"
    ET.SubElement(channel, "description").text = "Latest opinion articles"

# Deduplicate by URL (both in new articles and existing XML)
seen_urls = set()
unique_articles = []
for art in articles:
    if art["url"] not in seen_urls:
        seen_urls.add(art["url"])
        unique_articles.append(art)

# Get existing URLs from XML
existing = set()
for item in channel.findall("item"):
    link_tag = item.find("link")
    if link_tag is not None:
        existing.add(link_tag.text.strip())

# Append new unique articles
new_count = 0
for art in unique_articles:
    if art["url"] in existing:
        continue
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = art["title"]
    ET.SubElement(item, "link").text = art["url"]
    ET.SubElement(item, "description").text = art["desc"]
    ET.SubElement(item, "pubDate").text = art["pub"] if art["pub"] else datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    if art["img"]:
        ET.SubElement(item, "enclosure", url=art["img"], type="image/jpeg")
    new_count += 1

# Trim to last MAX_ITEMS
all_items = channel.findall("item")
if len(all_items) > MAX_ITEMS:
    for old_item in all_items[:-MAX_ITEMS]:
        channel.remove(old_item)

# Save XML
tree = ET.ElementTree(root)
tree.write(XML_FILE, encoding="utf-8", xml_declaration=True)

print(f"Found {len(articles)} total articles (including duplicates)")
print(f"Unique articles: {len(unique_articles)}")
print(f"New articles added: {new_count}")
print(f"Total in XML: {len(channel.findall('item'))}")
print(f"XML saved to {XML_FILE}")