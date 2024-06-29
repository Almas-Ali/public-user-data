import asyncio
import json
import os
from typing import Dict, List

import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm


async def fetch(
    url: str,
    session: ClientSession,
    headers: Dict[str, str],
    retries: int = 10,  # Except not to failed anything!
):
    for count in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                return await response.text()
        except aiohttp.client_exceptions.ServerDisconnectedError as e:
            # print(f"Server disconnected while fetching {url}. Retrying {count}...")
            pass
        except aiohttp.ClientError as e:
            # print(f"Client error {e} while fetching {url}. Retrying {count}...")
            pass
        except asyncio.TimeoutError:
            # print(f"Timeout while fetching {url}. Retrying {count}...")
            pass
        await asyncio.sleep(1)
    print(f"Failed to fetch {url} after {retries} retries.")
    return ""


async def download_image(
    url: str,
    session: ClientSession,
    id: str,
    headers: Dict[str, str],
    retries: int = 10,  # Except not to failed anything!
):
    for count in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                content = await response.read()
                with open(f"images/{id}.png", "wb") as f:
                    f.write(content)
                return
        except aiohttp.client_exceptions.ServerDisconnectedError as e:
            # print(f"Server disconnected while downloading {url}. Retrying {count}...")
            pass
        except aiohttp.ClientError as e:
            # print(f"Client error {e} while downloading {url}. Retrying {count}...")
            pass
        except asyncio.TimeoutError:
            # print(f"Timeout while downloading {url}. Retrying {count}...")
            pass
        await asyncio.sleep(1)
    print(f"Failed to download image from {url} after {retries} retries.")


async def scraper(url: str, session: ClientSession, headers: Dict[str, str]):
    """Scrape data from the given url"""
    html = await fetch(url, session, headers)
    if not html:
        return None

    data: Dict[str, str] = {}
    data["id"] = [str(i) for i in url.split("/") if i.isdigit()][0]

    soup = BeautifulSoup(html, "html.parser")
    html_card = soup.select_one('div[class="card-body"]')

    if not html_card:
        print(f"No data found in {url}")
        return None

    image = html_card.select_one('img[class="img-thumbnail"]')

    data["image"] = image.get("src", "") if image else ""
    data["name"] = html_card.select_one("b").text
    data["address_present"] = html_card.select("b")[1].next_sibling.next_sibling.strip()
    data["address_permanent"] = html_card.select("b")[
        2
    ].next_sibling.next_sibling.strip()
    data["last_education"] = html_card.select("b")[3].next_sibling.strip()
    data["job_experiences"] = html_card.select("b")[4].next_sibling.strip()
    data["experience_details"] = html_card.select("b")[5].next_sibling.strip()

    # If profile is empty
    if (
        data["image"] == "https://www.rajshahijobs.com/images/users/"
        and data["name"] == ""
    ):
        return None

    # Save image locally
    if data["image"]:
        image_local_path = f'images/{data["id"]}.png'
        await download_image(data["image"], session, data["id"], headers)
        data["local_image_path"] = image_local_path

    return data


async def main() -> None:
    """Main function to run the scraper"""

    url_format = "https://www.rajshahijobs.com/cv/{id}/"

    os.makedirs("images", exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        urls = [url_format.format(id=i) for i in range(1, 500)]
        tasks = [scraper(url, session, headers) for url in urls]

        results: List[Dict[str, str]] = []
        for task in tqdm.as_completed(tasks, desc="Scraping data"):
            result = await task
            results.append(result)

    new_results = [result for result in results if result is not None]
    count_none = len(results) - len(new_results)

    print(f"[!] Filtered {count_none} None data.")

    # Load existing data
    if os.path.exists("scraped_data.json"):
        with open("scraped_data.json", "r") as f:
            existing_data = json.load(f)
        existing_data_dict = {entry["id"]: entry for entry in existing_data}
    else:
        existing_data_dict = {}

    # Update only changed data in json file from the scraped data
    updated_data_dict = {entry["id"]: entry for entry in new_results}
    for id, entry in updated_data_dict.items():
        if id in existing_data_dict:
            existing_entry = existing_data_dict[id]
            for key, value in entry.items():
                if key == "image":
                    continue
                if existing_entry[key] != value:
                    print(
                        f"[!] Updating {id}: {key} from {existing_entry[key]} to {value}"
                    )
                    existing_entry[key] = value
        else:
            print(f"[!] Adding new entry {id}")
            existing_data_dict[id] = entry

    updated_data = list(existing_data_dict.values())

    try:
        # Sort the results by id
        updated_data = sorted(updated_data, key=lambda x: int(x["id"]))

        # Save the results to a JSON file
        with open("scraped_data.json", "w") as f:
            json.dump(updated_data, f, indent=4)

    except TypeError:
        print("[!] Warning: Not properly scraped! Try again.")


if __name__ == "__main__":
    asyncio.run(main())
