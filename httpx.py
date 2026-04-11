class Client:
    def __init__(self, timeout=10.0):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        raise RuntimeError("httpx stub: network call not available")
