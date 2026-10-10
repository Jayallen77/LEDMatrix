# Cache strategy

CacheManager provides memory and persistent JSON caching with atomic writes and writable-directory fallbacks. Retained managers enforce their own refresh windows. Weather and markets keep last-good data during failures and retry on bounded backoff. Colorado live games expire after 120 seconds. Legacy sports have separate live/recent/upcoming freshness settings.
