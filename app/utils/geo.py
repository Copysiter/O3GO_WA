import phonenumbers


def get_geo_by_number(number: str) -> str:
    """
    Определяет ISO-код страны (например: 'RU', 'US', 'DE') по номеру телефона.
    Если определить не удалось — возвращает пустую строку.
    """
    try:
        parsed = phonenumbers.parse(number, None)
        return phonenumbers.region_code_for_number(parsed) or ""
    except Exception:
        return ""
