from __future__ import annotations


class EntityTypeNormalizer:
    """
    Normalize entity types từ các nguồn khác nhau về 1 taxonomy thống nhất của app.
    VD: Presidio EMAIL_ADDRESS -> EMAIL, PHONE_NUMBER -> PHONE
    """

    _MAP = {
        # Presidio -> App
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "CREDIT_CARD": "CREDIT_CARD",
        "US_SSN": "SSN",
        "URL": "URL",
        "IP_ADDRESS": "IP",
        "DOMAIN_NAME": "DOMAIN",
        # Local (để sẵn nếu mày đổi tên)
        "CCCD": "CCCD",
        "PHONE": "PHONE",
        "EMAIL": "EMAIL",
        "TAX_ID": "TAX_ID",
        "API_SECRET": "API_SECRET",
    }

    def normalize(self, raw_type: str) -> str:
        if not raw_type:
            return raw_type
        key = str(raw_type).strip()
        return self._MAP.get(key, key)