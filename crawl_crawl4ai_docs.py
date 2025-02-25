import os
import sys
import psutil
import asyncio
import requests
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
import argparse

__location__ = os.path.dirname(os.path.abspath(__file__))
__output__ = os.path.join(__location__, "output")

# Create output directory if it doesn't exist
os.makedirs(__output__, exist_ok=True)

# Append parent directory to system path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from typing import List, Dict
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class DocsFramework:
    def __init__(self, name: str, sitemap_url: str, base_url: str):
        self.name = name
        self.sitemap_url = sitemap_url
        self.base_url = base_url

FRAMEWORKS = {
    'crawl4ai': DocsFramework(
        'crawl4ai',
        'https://crawl4ai.com/mkdocs/sitemap.xml',
        'https://crawl4ai.com'
    ),
    'pydantic': DocsFramework(
        'pydantic',
        'https://ai.pydantic.dev/sitemap.xml',
        'https://ai.pydantic.dev'
    ),
    'agno': DocsFramework(
        'agno',
        'https://docs.agno.com/sitemap.xml',
        'https://docs.agno.com'
    )
}

def save_crawl_result(framework: str, url: str, result, output_dir: str):
    """
    Saves the crawling result in files organized by framework.
    
    Args:
        framework: Framework name
        url: URL of the crawled page
        result: Crawling result
        output_dir: Base directory to save the results
    """
    # Create filename based on URL
    filename = url.replace('https://', '').replace('http://', '').replace('/', '_')
    if filename.endswith('_'):
        filename = filename[:-1]
    
    # Create directory for framework/date
    date_dir = os.path.join(output_dir, framework, datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(date_dir, exist_ok=True)
    
    # Save Markdown content
    if hasattr(result, 'markdown_v2') and result.markdown_v2:
        md_path = os.path.join(date_dir, f"{filename}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(result.markdown_v2.raw_markdown)
    
    # Save metadata
    meta_path = os.path.join(date_dir, f"{filename}_meta.json")
    metadata = {
        'framework': framework,
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'success': result.success if hasattr(result, 'success') else False,
        'error': str(result) if isinstance(result, Exception) else None
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def save_crawl_report(framework: str, stats: Dict, output_dir: str):
    """
    Saves a general report of the crawling process by framework.
    """
    report_path = os.path.join(output_dir, framework, datetime.now().strftime('%Y-%m-%d'), 'crawl_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

def get_framework_urls(framework: DocsFramework) -> List[str]:
    """
    Fetches URLs from the sitemap of a specific framework.
    
    Args:
        framework: DocsFramework object with framework information

    Returns:
        List[str]: List of URLs found
    """
    try:
        response = requests.get(framework.sitemap_url)
        response.raise_for_status()
        
        # Parse the XML
        root = ElementTree.fromstring(response.content)
        
        # Extract all URLs from the sitemap
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [loc.text for loc in root.findall('.//ns:loc', namespace)]
        
        print(f"Found {len(urls)} URLs for {framework.name}")
        return urls
    except Exception as e:
        print(f"Error fetching sitemap for {framework.name}: {e}")
        return []

async def crawl_parallel(framework: str, urls: List[str], max_concurrent: int = 3):
    print(f"\n=== Parallel Crawling for {framework} with Browser Reuse + Memory Check ===")

    # Track peak memory usage
    peak_memory = 0
    process = psutil.Process(os.getpid())

    def log_memory(prefix: str = ""):
        nonlocal peak_memory
        current_mem = process.memory_info().rss
        if current_mem > peak_memory:
            peak_memory = current_mem
        print(f"{prefix} Current Memory: {current_mem // (1024 * 1024)} MB, Peak: {peak_memory // (1024 * 1024)} MB")

    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    
    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        exclude_external_links=True,
        exclude_social_media_links=True,
        word_count_threshold=10,
        wait_until="domcontentloaded",
        page_timeout=60000
    )

    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.start()

    try:
        success_count = 0
        fail_count = 0
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i : i + max_concurrent]
            tasks = []

            for j, url in enumerate(batch):
                session_id = f"{framework}_session_{i + j}"
                task = crawler.arun(url=url, config=crawl_config, session_id=session_id)
                tasks.append(task)

            log_memory(prefix=f"Before batch {i//max_concurrent + 1}: ")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            log_memory(prefix=f"After batch {i//max_concurrent + 1}: ")

            for url, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"Error crawling {url}: {result}")
                    fail_count += 1
                else:
                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1
                
                save_crawl_result(framework, url, result, __output__)

        stats = {
            'framework': framework,
            'timestamp': datetime.now().isoformat(),
            'total_urls': len(urls),
            'success_count': success_count,
            'fail_count': fail_count,
            'peak_memory_mb': peak_memory // (1024 * 1024)
        }
        save_crawl_report(framework, stats, __output__)

        print(f"\nSummary for {framework}:")
        print(f"  - Successfully crawled: {success_count}")
        print(f"  - Failed: {fail_count}")
        print(f"\nResults saved in: {os.path.join(__output__, framework)}")

    finally:
        print("\nClosing crawler...")
        await crawler.close()
        log_memory(prefix="Final: ")
        print(f"\nPeak memory usage (MB): {peak_memory // (1024 * 1024)}")

async def main():
    parser = argparse.ArgumentParser(description='Crawl documentation for specific frameworks')
    parser.add_argument('--framework', choices=FRAMEWORKS.keys(), default='crawl4ai',
                      help='Framework to crawl (default: crawl4ai)')
    args = parser.parse_args()

    framework = FRAMEWORKS[args.framework]
    urls = get_framework_urls(framework)
    
    if urls:
        print(f"Found {len(urls)} URLs to crawl for {framework.name}")
        await crawl_parallel(framework.name, urls, max_concurrent=10)
    else:
        print(f"No URLs found to crawl for {framework.name}")

if __name__ == "__main__":
    asyncio.run(main())