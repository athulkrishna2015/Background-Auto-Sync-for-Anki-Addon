import socket


def has_internet_connection(host="8.8.8.8", port=443, timeout=3):
    """Try connecting to the Google DNS server to check internet connectivity.
    Using port 443 (HTTPS) as opposed to 53 (DNS) because TCP port 53 is often blocked
    by enterprise firewalls or public Wi-Fi networks."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return True
    except OSError:
        pass

    # Fallback to ankiweb just in case 8.8.8.8 is unreachable
    try:
        with socket.create_connection(("ankiweb.net", 443), timeout=timeout):
            pass
        return True
    except OSError:
        return False
