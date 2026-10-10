# Cache management

Persistent display data is separate from authorization caches. Preserve config/spotify_auth.json, credentials.json, and token.pickle. Inspect refresh errors before clearing caches: last-good data intentionally keeps the display useful offline. CacheManager selects a writable location, commonly /var/cache/ledmatrix.
