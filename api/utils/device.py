def parse_device(user_agent):
    if not user_agent:
        return "Unknown"

    ua = user_agent.lower()

    if "postman" in ua:
        client = "Postman"
    elif "chrome" in ua and "edg" not in ua:
        client = "Chrome"
    elif "firefox" in ua:
        client = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        client = "Safari"
    elif "edg" in ua:
        client = "Edge"
    else:
        client = "Unknown"

    if "mac os" in ua or "macintosh" in ua:
        platform = "macOS"
    elif "windows" in ua:
        platform = "Windows"
    elif "android" in ua:
        platform = "Android"
    elif "iphone" in ua or "ipad" in ua:
        platform = "iOS"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = "Desktop"

    return f"{client} / {platform}"
