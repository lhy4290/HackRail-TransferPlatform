class FakeTDXClient:
    """測試用假 TDX 客戶端：依端點回傳預先設定好的資料，略過真實 HTTP 呼叫"""

    def __init__(self, responses: dict[str, object] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict | None]] = []

    async def request(self, endpoint: str, params: dict | None = None, **kwargs):
        self.calls.append((endpoint, params))
        if endpoint in self.responses:
            return self.responses[endpoint]
        for prefix, value in self.responses.items():
            if endpoint.startswith(prefix):
                return value
        return []
