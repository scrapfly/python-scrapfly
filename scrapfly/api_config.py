class BaseApiConfig:
    def _bool_to_http(self, _bool: bool) -> str:
        return 'true' if _bool is True else 'false'
