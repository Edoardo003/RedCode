---
name: "hexstrike-urldiscovery"
description: "Correct parameters, deduplication strategies, and usage patterns for HexStrike gau_discovery, waybackurls_discovery, and hakrawler_crawl MCP tools."
---

# HexStrike URL Discovery — gau_discovery, waybackurls_discovery, hakrawler_crawl — Tool Skill

Historical URL discovery and web crawling tools. Find endpoints that existed in the past (removed pages, old API versions, exposed config files) and crawl current live endpoints. These tools feed the scanning phase with URLs that might be missed by standard directory brute-force.

---

## gau_discovery — Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`) |
| `flags`   | string | no       | GAU flags                          |

Fetches known URLs from Wayback Machine, CommonCrawl, Open Threat Exchange (OTX), and URLScan.io.

### Common Usage

```
# Discover all historical URLs
gau_discovery(domain="example.com")

# Filter by specific providers
gau_discovery(domain="example.com", flags="--providers wayback,commoncrawl,otx")

# With output filtering (only paths matching pattern)
gau_discovery(domain="example.com", flags="--blacklist png,jpg,gif,css,woff,svg")
```

---

## waybackurls_discovery — Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`) |
| `flags`   | string | no       | Waybackurls flags                  |

Fetches URLs specifically from the Wayback Machine's CDX API. Narrower than GAU but sometimes finds URLs that GAU misses.

### Common Usage

```
# Discover all Wayback Machine URLs
waybackurls_discovery(domain="example.com")

# With date range filtering
waybackurls_discovery(domain="example.com", flags="-dates")
```

---

## hakrawler_crawl — Parameters

| Parameter | Type   | Required | Description                                        |
| --------- | ------ | -------- | -------------------------------------------------- |
| `url`     | string | **YES**  | Starting URL to crawl (e.g. `https://example.com`) |
| `flags`   | string | no       | Hakrawler flags (e.g. `-d 3`, `-insecure`)         |

**Note**: hakrawler takes a `url` parameter (not `domain`). It actively crawls the live site — not passive like gau/waybackurls.

### Common Usage

```
# Crawl with default depth
hakrawler_crawl(url="https://example.com")

# Deep crawl (3 levels)
hakrawler_crawl(url="https://example.com", flags="-d 3")

# Include subdomains in scope
hakrawler_crawl(url="https://example.com", flags="-d 2 -subs")

# Skip TLS verification (self-signed certs)
hakrawler_crawl(url="https://example.com", flags="-d 2 -insecure")

# With proxy
hakrawler_crawl(url="https://example.com", flags="-d 2 -proxy http://user:pass@host:port")
```

---

## Multi-Tool Strategy

Run ALL three tools for maximum URL coverage. Each finds different URLs:

1. **gau_discovery** — broadest coverage (4 sources)
2. **waybackurls_discovery** — deepest Wayback Machine coverage
3. **hakrawler_crawl** — finds current live endpoints (JS-rendered links, forms)

**Deduplicate** results across all three tools. The merged list feeds into:

- **@scanner** → URLs for parameter fuzzing, injection testing
- **@exploiter** → old/hidden endpoints that might lack security controls

## High-Value URL Patterns

After collecting URLs, look for these patterns:

| Pattern                       | Why It Matters                                  |
| ----------------------------- | ----------------------------------------------- |
| `/api/`, `/v1/`, `/v2/`       | API endpoints — test for injection, auth bypass |
| `?id=`, `?page=`, `?file=`    | Parameters — test for SQLi, LFI, SSRF           |
| `.env`, `.config`, `.bak`     | Config files — may contain credentials          |
| `/admin/`, `/dashboard/`      | Admin panels — test for default creds           |
| `/upload`, `/import`          | File upload — test for unrestricted upload      |
| Old API versions (`/api/v1/`) | Deprecated endpoints with weaker security       |
| `/debug/`, `/test/`           | Debug endpoints — often left in production      |

## Proxy Configuration

```
# gau — respects http_proxy env var
gau_discovery(domain="example.com")

# waybackurls — respects http_proxy env var
waybackurls_discovery(domain="example.com")

# hakrawler — explicit proxy flag
hakrawler_crawl(url="https://example.com", flags="-proxy http://user:pass@host:port")
```

## Retry Strategy

1. **gau timeout**: Try with fewer providers (`--providers wayback`)
2. **waybackurls 0 results**: Domain may be too new for Wayback Machine archives
3. **hakrawler timeout**: Reduce crawl depth (`-d 1`). Large sites can have thousands of pages.
4. **Rate limited**: Wait and retry. These tools query third-party APIs.
5. **Tool not available**: Use alternatives. gau and waybackurls overlap significantly.

## Output Interpretation

- **Thousands of URLs** — normal for active sites. Filter by high-value patterns first.
- **Old URLs returning 404** — page removed. Check Wayback Machine for cached content.
- **Old URLs still live** — may be forgotten, unpatched, less monitored. HIGH priority.
- **URLs with parameters** — IMMEDIATE value for injection testing.
- **Config file URLs** — attempt to access. May contain credentials, API keys, database strings.

## Evidence Capture

Save discovered URLs to `output/{target}/osint/raw/urls_*.txt`. Merge and deduplicate into a master URL list at `output/{target}/osint/raw/all_urls.txt`.
