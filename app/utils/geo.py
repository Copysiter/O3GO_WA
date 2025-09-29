from typing import Optional

from phonenumbers.phonenumberutil import NumberParseException
import phonenumbers


def get_geo_by_number(number: Optional[str]) -> str:
    """
    Определяет ISO-код страны (например: 'RU', 'US', 'DE') по номеру телефона.
    Если определить не удалось — возвращает пустую строку.

    Примечание: если номер приходит без префикса '+' (например: '7920...'),
    для корректного определения гео временно добавляем '+' перед парсингом.
    Это изменение применяется только для вычисления гео и не меняет
    сохранённое значение номера в базе данных.
    """
    if not number:
        return ""

    try:
        num = number.strip()
        # временно добавляем '+' если его нет — только для гео-определения
        num_for_parse = num if num.startswith("+") else f"+{num}"
        parsed = phonenumbers.parse(num_for_parse, None)
        return phonenumbers.region_code_for_number(parsed) or ""
    except NumberParseException:
        return ""
