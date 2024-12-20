# pylint: disable=missing-module-docstring, missing-function-docstring
import os
import re
from urllib.parse import urljoin

import requests
from lxml import html

DOCS_FILE_PATH = "docs.txt"


def get_html(url):
    page = requests.get(url, timeout=30)
    return html.fromstring(page.content)


def get_doc_urls():
    lines = []
    with open(DOCS_FILE_PATH, "r", encoding="utf-8") as file:
        for line in file:
            lines.append(line.replace("\n", ""))
    lines = list(set(lines))
    lines.sort()

    with open(DOCS_FILE_PATH, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(line + "\n")
    return lines


def first_or_default(lst, default=None):
    return lst[0] if len(lst) > 0 else default


def main():
    for doc_url in get_doc_urls():
        print(doc_url)
        doc_html = get_html(doc_url)

        # <meta name="toc_rel" content="toc.json" />
        toc_rel = first_or_default(doc_html.xpath(
            '//meta[@name="toc_rel"]/@content'))

        # <link href="https://learn.microsoft.com/en-us/azure/event-grid/" rel="canonical">
        base_url = first_or_default(
            doc_html.xpath('//link[@rel="canonical"]/@href'))

        if toc_rel is None:
            print(f"No table of contents found for {doc_url}.")
            continue

        toc_url = f"{doc_url}{toc_rel}"

        print(f"TOC: {toc_url}")

        toc_json = requests.get(toc_url, timeout=30).json()

        # for item in toc_json['items']:
        #     for line in get_item_lines(base_url, item):
        #         print(line)

        title = first_or_default(doc_html.xpath('//title/text()'))

        todo_filename = title \
            .lower() \
            .replace(" | microsoft learn", "") \
            .replace(" documentation", "") \
            .replace(" ", "-") \
            .replace("---", "-") \
            .replace("--", "-")

        lines = []
        for item in toc_json['items']:
            for line in get_item_lines(base_url, item, 1):
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, f"{title}:")

        if os.path.exists(f"todos/{todo_filename}.todo"):
            # filter lines that are not already in the file
            with open(f"todos/{todo_filename}.todo", "r", encoding="utf-8") as file:
                existing_lines = [
                    re.sub(
                        r" (@done.*|@cancelled.*)", "",
                        line.replace("\n", "")
                            .replace("✔ ", "☐ ")
                            .replace("✔ ", "✘ "))
                    for line in file]
            lines = [line for line in lines if line not in existing_lines]

            if len(lines) > 0:
                lines.insert(0, "\n---\n")

        if len(lines) > 0:
            with open(f"todos/{todo_filename}.todo", "a", encoding="utf-8") as file:
                for line in lines:
                    print(line)
                    file.write(line + "\n")
                file.write("\n")


def get_item_lines(base_url, item, level=0):
    has_href = 'href' in item
    has_children = 'children' in item

    if has_href and not has_children:
        prefix = "☐ "
    else:
        prefix = ""

    if has_children:
        postfix = ":"
    else:
        postfix = ""

    line = f"{'    ' * level}{prefix}{item['toc_title']}"

    if has_href:
        line += f" {urljoin(base_url, item['href'])}"
        try:
            href_html = get_html(urljoin(base_url, item['href']))
            # <meta name="updated_at" content="2024-08-02 11:27 AM" />
            updated_at = first_or_default(href_html.xpath(
                '//meta[@name="updated_at"]/@content'))
            if updated_at is not None:
                line += f" ({updated_at})"
        except Exception as e:
            print(e)

    if has_children:
        line += postfix

    yield line

    if 'children' in item:
        for child in item['children']:
            yield from get_item_lines(base_url, child, level + 1)


if __name__ == "__main__":
    main()
