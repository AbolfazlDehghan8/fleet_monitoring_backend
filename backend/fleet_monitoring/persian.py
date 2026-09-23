_PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
_ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'
_DIGIT_TABLE = {
    **{ord(p): str(i) for i, p in enumerate(_PERSIAN_DIGITS)},
    **{ord(a): str(i) for i, a in enumerate(_ARABIC_DIGITS)},
}
_LETTER_TABLE = {
    ord('ي'): 'ی',
    ord('ى'): 'ی',
    ord('ك'): 'ک',
}
_INVISIBLE_TABLE = {ord('\u200f'): None, ord('\u200e'): None, ord('\ufeff'): None}


def normalize_digits(value):
    return value.translate(_DIGIT_TABLE) if isinstance(value, str) else value


def normalize_persian_text(value):
    if not isinstance(value, str):
        return value
    value = value.translate(_DIGIT_TABLE).translate(_LETTER_TABLE).translate(_INVISIBLE_TABLE)
    return value.strip()


def is_valid_iran_national_code(code):
    code = normalize_digits(code)
    if not isinstance(code, str) or len(code) != 10 or not code.isdigit():
        return False
    if len(set(code)) == 1:
        return False
    total = sum(int(code[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    check = int(code[9])
    return check == remainder if remainder < 2 else check == 11 - remainder