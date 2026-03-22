import logging
import os
import pwd
import stat
from typing import Optional


DEFAULT_RUNTIME_USER = "daemon"
RUNTIME_USER_ENV = "LEDMATRIX_SPOTIFY_RUNTIME_USER"
EXPECTED_CACHE_MODE = 0o600


def get_expected_runtime_user() -> str:
    return os.getenv(RUNTIME_USER_ENV, DEFAULT_RUNTIME_USER)


def _logger(logger: Optional[logging.Logger]) -> logging.Logger:
    return logger or logging.getLogger(__name__)


def _safe_geteuid() -> int:
    if hasattr(os, "geteuid"):
        return os.geteuid()
    return os.getuid()


def _resolve_user(username: str):
    try:
        return pwd.getpwnam(username)
    except KeyError:
        return None


def log_spotify_cache_diagnostics(
    cache_path: str,
    logger: Optional[logging.Logger] = None,
    expected_owner: Optional[str] = None,
) -> None:
    logger = _logger(logger)
    expected_owner = expected_owner or get_expected_runtime_user()

    logger.info(
        "Spotify auth cache expected owner=%s mode=%s path=%s",
        expected_owner,
        oct(EXPECTED_CACHE_MODE),
        cache_path,
    )

    if not os.path.exists(cache_path):
        logger.warning("Spotify auth cache does not exist at %s", cache_path)
        return

    euid = _safe_geteuid()
    stat_info = os.stat(cache_path)
    mode = stat.S_IMODE(stat_info.st_mode)
    logger.info(
        "DIAG: Cache file stat: UID=%s, GID=%s, Mode=%s",
        stat_info.st_uid,
        stat_info.st_gid,
        oct(mode),
    )
    logger.info("DIAG: Current process Effective UID: %s", euid)
    logger.info("DIAG: Current process read access: %s", os.access(cache_path, os.R_OK))

    expected_user = _resolve_user(expected_owner)
    if expected_user:
        if stat_info.st_uid != expected_user.pw_uid or mode != EXPECTED_CACHE_MODE:
            logger.warning(
                "Spotify auth cache ownership mismatch. Expected owner=%s (uid=%s) and mode=%s.",
                expected_owner,
                expected_user.pw_uid,
                oct(EXPECTED_CACHE_MODE),
            )
    else:
        logger.warning(
            "Expected Spotify runtime user '%s' does not exist on this system. "
            "Set %s if your matrix process runs as another user.",
            expected_owner,
            RUNTIME_USER_ENV,
        )

    try:
        with open(cache_path, "r", encoding="utf-8") as cache_file:
            preview = cache_file.read(120)
        logger.info("DIAG: Cache file manual read successful. Content preview length=%s", len(preview))
        if not preview.strip():
            logger.warning("DIAG: Cache file is empty or whitespace only.")
    except Exception as exc:
        logger.error("DIAG: Error during diagnostic read of cache file: %s", exc)


def ensure_spotify_cache_access(
    cache_path: str,
    logger: Optional[logging.Logger] = None,
    runtime_user: Optional[str] = None,
) -> bool:
    logger = _logger(logger)
    runtime_user = runtime_user or get_expected_runtime_user()

    if not os.path.exists(cache_path):
        logger.warning("Cannot fix Spotify auth cache permissions because %s does not exist.", cache_path)
        return False

    expected_user = _resolve_user(runtime_user)
    euid = _safe_geteuid()

    try:
        os.chmod(cache_path, EXPECTED_CACHE_MODE)
    except PermissionError:
        logger.warning(
            "Cannot set mode %s on %s without sufficient permissions. Current EUID=%s.",
            oct(EXPECTED_CACHE_MODE),
            cache_path,
            euid,
        )
    except OSError as exc:
        logger.warning("Failed to set mode on Spotify auth cache %s: %s", cache_path, exc)

    if expected_user is None:
        logger.warning(
            "Spotify runtime user '%s' was not found. Leaving auth cache owned by the current user. "
            "Set %s to the account used after matrix privilege drop if needed.",
            runtime_user,
            RUNTIME_USER_ENV,
        )
        log_spotify_cache_diagnostics(cache_path, logger=logger, expected_owner=runtime_user)
        stat_info = os.stat(cache_path)
        return stat.S_IMODE(stat_info.st_mode) == EXPECTED_CACHE_MODE

    try:
        os.chown(cache_path, expected_user.pw_uid, expected_user.pw_gid)
    except PermissionError:
        logger.warning(
            "Cannot change owner of %s to %s unless this runs as root. Current EUID=%s.",
            cache_path,
            runtime_user,
            euid,
        )
    except OSError as exc:
        logger.warning("Failed to change owner of Spotify auth cache %s: %s", cache_path, exc)

    log_spotify_cache_diagnostics(cache_path, logger=logger, expected_owner=runtime_user)
    stat_info = os.stat(cache_path)
    mode = stat.S_IMODE(stat_info.st_mode)
    return stat_info.st_uid == expected_user.pw_uid and mode == EXPECTED_CACHE_MODE
