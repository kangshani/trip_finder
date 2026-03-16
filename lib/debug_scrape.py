import sys
from bs4 import BeautifulSoup
import re
from scrape_single_site import fetch_page

html = fetch_page('https://en.wikivoyage.org/wiki/Serengeti')
soup = BeautifulSoup(html, "lxml")
main = soup.find(class_="mw-parser-output") or soup.find("main") or soup.find("body")
print("Initial main text length:", len(main.get_text()))

for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "form"]):
    tag.decompose()
print("After tag decompose:", len(main.get_text()))

for element in soup.find_all(class_=re.compile(r"(sidebar|menu|nav|footer|header|ad|banner|cookie|popup|modal)", re.IGNORECASE)):
    print("Decomposing class:", element.get('class'))
    element.decompose()
print("After class decompose:", len(main.get_text()))
