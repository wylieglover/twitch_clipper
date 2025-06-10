import re
import unicodedata

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for cross-platform compatibility *and* FFmpeg-safe paths."""
    if not filename:
        return "unnamed"

    # 1) Normalize Unicode (decomposes accents, etc.)
    filename = unicodedata.normalize("NFKD", filename)

    # 2) Remove emojis and other problematic Unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended-A
        "]+",
        flags=re.UNICODE
    )
    filename = emoji_pattern.sub("", filename)

    # 3) Replace any “truly invalid” file-system characters with underscore
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        filename = filename.replace(ch, "_")

    # 4) Replace spaces and other punctuation that FFmpeg’s subtitles= might choke on
    #    You can add more to this list if you run into other errors.
    for ch in (" ", "'", "!", "(", ")", "[", "]", "{", "}", "&", ";", ","):
        filename = filename.replace(ch, "_")

    # 5) Remove any remaining non-ASCII (just in case)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # 6) Collapse multiple underscores into one (optional, but keeps things tidy)
    filename = re.sub(r"_+", "_", filename)

    # 7) Strip leading/trailing dots or underscores
    filename = filename.strip(" ._")

    # 8) If it’s now empty, fall back to “unnamed”
    if not filename:
        filename = "unnamed"

    # 9) Truncate to a safe length (e.g. 100 characters)
    return filename[:100]