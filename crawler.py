# pylint: disable=missing-module-docstring, missing-function-docstring
import json
import os
import re
import time
from urllib.parse import urljoin

import dotenv
import requests
from lxml import html

dotenv.load_dotenv()

CACHE_DURATION_SECONDS = 60 * 60 * int(os.getenv("CACHE_DURATION_HOURS", "24"))

DOCS_FILE_PATH = "docs.txt"
DOCS_CACHE_PATH = ".docs.cache.json"


def get_html(url):
    page = requests.get(url, timeout=30)
    return html.fromstring(page.content)


def get_doc_urls():
    lines = []
    with open(DOCS_FILE_PATH, "r", encoding="utf-8") as file:
        for line in file:
            line = line.replace("\n", "")
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

        if os.path.exists(DOCS_CACHE_PATH):
            with open(DOCS_CACHE_PATH, "r", encoding="utf-8") as file:
                cache = json.load(file)
        else:
            cache = {}

        if (
            doc_url in cache
            and cache[doc_url]["updated_at"] > time.time() - CACHE_DURATION_SECONDS
        ):
            continue

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

        toc_url = urljoin(base_url, toc_rel)

        print(f"  TOC: {toc_url}")

        toc_json = requests.get(toc_url, timeout=30).json()

        title = first_or_default(doc_html.xpath("//title/text()"))

        todo_filename = f"{doc_url.replace(
            'https://learn.microsoft.com/en-us/', '').replace('/', '-').rstrip('-')}.todo"

        blacklised_urls = [
            "/java/",
        ]

        lines = []
        for item in toc_json["items"]:
            for line in get_item_lines(base_url, item, 1):
                if any(url in line for url in blacklised_urls):
                    continue
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, f"{title}:")

        file_path = os.path.join(
            "todos",
            doc_url.replace("https://learn.microsoft.com/en-us/", ""),
            todo_filename,
        )

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path):
            # filter lines that are not already in the file
            with open(file_path, "r", encoding="utf-8") as file:
                existing_lines = [
                    re.sub(
                        r" (@done.*|@cancelled.*)",
                        "",
                        line.replace("\n", "").replace(
                            "✔ ", "☐ ").replace("✔ ", "✘ "),
                    )
                    for line in file
                ]
            lines = [line for line in lines if line not in existing_lines]

            if len(lines) > 0:
                lines.insert(0, "\n---\n")

        if len(lines) > 0:
            if os.path.exists(file_path):
                new_lines_urls = [
                    re.search(r"(?P<url>https?://[^\s]+)", line).group("url")
                    for line in lines
                    if re.search(r"(?P<url>https?://[^\s]+)", line)
                ]

                with open(file_path, "r+", encoding="utf-8") as file:
                    file_lines = file.readlines()

                    file.seek(0)

                    for line in file_lines:
                        for new_line_url in new_lines_urls:
                            if new_line_url in line and line.strip().startswith("☐"):
                                line = f'{line.replace(
                                    "☐", "✘").rstrip()} @cancelled\n'
                                break

                        file.write(line)

            with open(file_path, "a", encoding="utf-8") as file:
                for line in lines:
                    # print(line)
                    file.write(line + "\n")
                file.write("\n")

        cache[doc_url] = {"updated_at": time.time()}

        with open(DOCS_CACHE_PATH, "w", encoding="utf-8") as file:
            json.dump(cache, file, indent=2)


def get_item_lines(base_url, item, level=0):
    has_href = "href" in item
    has_children = "children" in item

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
        # it smells bad, but it works
        line = line \
            .replace("sql-server/sql-server", "sql-server") \
            .replace("sql/sql-server", "sql")
        try:
            href_html = get_html(urljoin(base_url, item["href"]))
            # <meta name="updated_at" content="2024-08-02 11:27 AM" />
            updated_at = first_or_default(
                href_html.xpath('//meta[@name="updated_at"]/@content')
            )
            if updated_at is not None:
                line += f" ({updated_at})"
        # pylint: disable=broad-except
        except Exception as e:
            print(e)

    if has_children:
        line += postfix

    yield line

    if "children" in item:
        for child in item["children"]:
            yield from get_item_lines(base_url, child, level + 1)


if __name__ == "__main__":
    main()
