# -*- coding: utf-8 -*-
"""Arabic Text Toolkit - أدوات النص العربي.

One small file of plain Python (3.9+, nothing to install) for cleaning and
measuring Arabic text: remove tashkeel, unify letter shapes, convert digits,
count words, build URL slugs and more.

Use it as a library:

    >>> from arabic_text import normalize, slugify
    >>> normalize("أَهْلًا وَسَهْلًا")
    'اهلا وسهلا'
    >>> slugify("مرحبا بالعالم!")
    'مرحبا-بالعالم'

Or from the command line:

    python arabic_text.py normalize "أَهْلًا وَسَهْلًا"
    python arabic_text.py --help

Author:  Hassam (https://github.com/hosam382)
License: MIT
"""

import argparse
import math
import re
import sys
import unicodedata
from typing import Optional

__version__ = "1.0.0"

__all__ = [
    "remove_tashkeel",
    "remove_tatweel",
    "normalize",
    "to_latin_digits",
    "to_arabic_digits",
    "is_arabic",
    "arabic_ratio",
    "count_words",
    "slugify",
    "strip_non_arabic",
    "reading_time",
]


# ---------------------------------------------------------------------------
# Character tables
# ---------------------------------------------------------------------------
# Every character has a number called its "code point" (written U+0627 for
# the letter ا). Many tables below are simply ranges of those numbers.


def _char_range(first: int, last: int) -> str:
    """Return every character from code point `first` to `last` (inclusive).

    >>> _char_range(0x0628, 0x062A)
    'بةت'
    """
    return "".join(chr(code) for code in range(first, last + 1))


TATWEEL = "ـ"  # ـ  the stretching line in "مـــرحبا"

# Tashkeel: every mark that is written above or below a letter.
TASHKEEL = (
    _char_range(0x064B, 0x065F)  # tanween, fatha, damma, kasra, shadda, sukun ...
    + "ٰ"  # superscript alef, the small alef in "هٰذا"
    + _char_range(0x0610, 0x061A)  # small signs above letters (religious texts)
    + _char_range(0x06D6, 0x06ED)  # Quranic marks: waqf signs, small letters ...
)

LATIN_DIGITS = "0123456789"
ARABIC_DIGITS = _char_range(0x0660, 0x0669)  # ٠١٢٣٤٥٦٧٨٩  (Arabic-Indic)
PERSIAN_DIGITS = _char_range(0x06F0, 0x06F9)  # ۰۱۲۳۴۵۶۷۸۹  (Persian / Urdu)
ARABIC_DECIMAL_SEPARATOR = "٫"  # ٫  as in ٣٫١٤
ARABIC_THOUSANDS_SEPARATOR = "٬"  # ٬  as in ١٬٠٠٠

# Unicode blocks that hold Arabic-script characters.
ARABIC_BLOCKS = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)

# str.maketrans(old, new) builds a lookup table, and text.translate(table)
# swaps every character in one fast pass. A third argument lists characters
# to delete.
_DELETE_TASHKEEL = str.maketrans("", "", TASHKEEL)
_ALEF_TABLE = str.maketrans("أإآٱ", "اااا")
_YA_TABLE = str.maketrans("ى", "ي")
_TA_MARBUTA_TABLE = str.maketrans("ة", "ه")
_HAMZA_TABLE = str.maketrans("ؤئ", "وي")
_TO_LATIN_DIGITS_TABLE = str.maketrans(
    ARABIC_DIGITS + PERSIAN_DIGITS + ARABIC_DECIMAL_SEPARATOR + ARABIC_THOUSANDS_SEPARATOR,
    LATIN_DIGITS + LATIN_DIGITS + "." + ",",
)
_TO_ARABIC_DIGITS_TABLE = str.maketrans(
    LATIN_DIGITS + PERSIAN_DIGITS,
    ARABIC_DIGITS + ARABIC_DIGITS,
)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------


def remove_tashkeel(text: str) -> str:
    """Remove tashkeel (diacritics) and keep the letters.

    Removes fatha, damma, kasra, tanween, shadda, sukun, the superscript
    alef and the small Quranic marks. Nothing else is changed, so the
    alef wasla ٱ stays (use normalize() to turn it into ا).

    >>> remove_tashkeel("مُحَمَّدٌ")
    'محمد'
    >>> remove_tashkeel("هٰذَا")
    'هذا'
    >>> remove_tashkeel("بِسْمِ ٱللَّهِ")
    'بسم ٱلله'
    """
    # Step 1: some texts store أ as two characters: ا + a "combining hamza"
    # mark. NFC joins such pairs into one letter, so step 2 can never strip
    # the hamza off a letter by mistake.
    text = unicodedata.normalize("NFC", text)
    # Step 2: delete every tashkeel mark in one pass.
    return text.translate(_DELETE_TASHKEEL)


def remove_tatweel(text: str) -> str:
    """Remove tatweel (kashida), the line used to stretch words.

    >>> remove_tatweel("مـــرحـبـا")
    'مرحبا'
    """
    return text.replace(TATWEEL, "")


def normalize(
    text: str,
    *,
    alef: bool = True,
    ya: bool = False,
    ta_marbuta: bool = False,
    hamza: bool = False,
    tashkeel: bool = True,
    tatweel: bool = True,
    digits: Optional[str] = None,
) -> str:
    """Make different spellings of the same word look the same.

    Useful before searching or comparing: after normalize(), "أحمد" and
    "احمد" are equal. Each option switches one rule on or off:

    Args:
        text: The text to clean.
        alef: Unify alef shapes: أ إ آ ٱ -> ا  (on by default).
        ya: Alef maqsura to ya: ى -> ي  ("مستشفى" -> "مستشفي").
        ta_marbuta: Ta marbuta to ha: ة -> ه  ("مدرسة" -> "مدرسه").
        hamza: Drop the hamza seat: ؤ -> و and ئ -> ي  ("مسؤول" -> "مسوول").
        tashkeel: Remove tashkeel (on by default).
        tatweel: Remove tatweel (on by default).
        digits: None keeps digits as they are, "latin" gives 0-9,
            "arabic" gives ٠-٩.

    Returns:
        The normalized text. Running normalize() twice gives the same result
        as running it once.

    >>> normalize("إِسْلَام")
    'اسلام'
    >>> normalize("مستشفى المدينة", ya=True, ta_marbuta=True)
    'مستشفي المدينه'
    >>> normalize("الصفحة ١٢", digits="latin")
    'الصفحة 12'
    """
    if digits not in (None, "latin", "arabic"):
        raise ValueError('digits must be None, "latin" or "arabic"')

    text = unicodedata.normalize("NFC", text)  # join split letters (see remove_tashkeel)
    if tashkeel:
        text = remove_tashkeel(text)
    if tatweel:
        text = remove_tatweel(text)
    if alef:
        text = text.translate(_ALEF_TABLE)
    if ya:
        text = text.translate(_YA_TABLE)
    if ta_marbuta:
        text = text.translate(_TA_MARBUTA_TABLE)
    if hamza:
        text = text.translate(_HAMZA_TABLE)
    if digits == "latin":
        text = to_latin_digits(text)
    elif digits == "arabic":
        text = to_arabic_digits(text)
    return text


# ---------------------------------------------------------------------------
# Digits
# ---------------------------------------------------------------------------


def to_latin_digits(text: str) -> str:
    """Turn Arabic-Indic (٠-٩) and Persian (۰-۹) digits into 0-9.

    The Arabic decimal separator ٫ becomes "." and the Arabic thousands
    separator ٬ becomes ",".

    >>> to_latin_digits("السعر ١٬٢٥٠٫٥ ريال")
    'السعر 1,250.5 ريال'
    """
    return text.translate(_TO_LATIN_DIGITS_TABLE)


def to_arabic_digits(text: str) -> str:
    """Turn 0-9 (and Persian ۰-۹) into Arabic-Indic digits ٠-٩.

    Only digits change; punctuation such as "." is left alone.

    >>> to_arabic_digits("الصف 2 - الفصل 1")
    'الصف ٢ - الفصل ١'
    """
    return text.translate(_TO_ARABIC_DIGITS_TABLE)


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


def is_arabic(char: str) -> bool:
    """Return True if `char` is one Arabic-script letter.

    Letters used in Persian and Urdu (پ چ گ) count too. Digits,
    punctuation (، ؟), tashkeel and tatweel do not.

    >>> is_arabic("ب"), is_arabic("پ"), is_arabic("b"), is_arabic("٣")
    (True, True, False, False)
    """
    if len(char) != 1:
        raise ValueError(f"is_arabic() expects exactly one character, got {len(char)}")
    if not char.isalpha() or char == TATWEEL:
        return False
    code = ord(char)
    return any(first <= code <= last for first, last in ARABIC_BLOCKS)


def arabic_ratio(text: str) -> float:
    """Return the share of letters that are Arabic, from 0.0 to 1.0.

    Only letters are counted: spaces, digits, punctuation, tashkeel and
    tatweel are ignored. Text with no letters gives 0.0.

    >>> arabic_ratio("Python بايثون")
    0.5
    >>> arabic_ratio("مرحبا")
    1.0
    """
    letters = [char for char in remove_tatweel(text) if char.isalpha()]
    if not letters:
        return 0.0
    arabic_letters = sum(1 for char in letters if is_arabic(char))
    return arabic_letters / len(letters)


def count_words(text: str) -> int:
    """Count the words in `text`.

    A word is a piece of text between spaces that has at least one letter
    or digit, so a lone "،" or "-" is not a word, but "2026" is.

    >>> count_words("السلام عليكم ورحمة الله")
    4
    >>> count_words("مرحبا ، كيف حالك ؟")
    3
    """
    pieces = remove_tatweel(text).split()
    return sum(1 for piece in pieces if any(char.isalnum() for char in piece))


def reading_time(text: str, wpm: int = 180) -> int:
    """Estimate reading time in whole minutes, rounded up.

    Args:
        text: The text to be read.
        wpm: Reading speed in words per minute (180 is a relaxed pace
            for Arabic).

    Returns:
        At least 1 for any text that has words, and 0 for text with no
        words (such as "" or "!!!").

    >>> reading_time("كلمة " * 200)
    2
    >>> reading_time("")
    0
    """
    if wpm <= 0:
        raise ValueError("wpm must be greater than 0")
    words = count_words(text)
    return math.ceil(words / wpm)


# ---------------------------------------------------------------------------
# Converting
# ---------------------------------------------------------------------------


def _to_ascii(char: str) -> str:
    """Drop accents from a Latin character: "é" -> "e". Others give ""."""
    decomposed = unicodedata.normalize("NFKD", char)  # "é" -> "e" + accent mark
    return decomposed.encode("ascii", "ignore").decode("ascii")


def slugify(text: str) -> str:
    """Turn a title into a clean URL part, for example for a blog post link.

    Keeps Arabic letters, Latin letters and digits. It normalizes the text
    (tashkeel, tatweel, alef), turns Arabic digits into 0-9, lowercases
    Latin letters, and joins the words with "-". Punctuation, including
    Arabic ، ؛ ؟ and the quotes « », becomes a separator.

    >>> slugify("مرحبا بالعالم!")
    'مرحبا-بالعالم'
    >>> slugify("دليل Python للمبتدئين ٢٠٢٦")
    'دليل-python-للمبتدئين-2026'
    """
    text = normalize(text, digits="latin")
    pieces = []
    for char in text:
        if is_arabic(char):
            pieces.append(char)
            continue
        plain = _to_ascii(char).lower()  # "É" -> "e", "!" -> "!", "،" -> ""
        pieces.append(plain if plain.isalnum() else "-")
    slug = "".join(pieces)
    slug = re.sub(r"-+", "-", slug)  # "a---b" -> "a-b"
    return slug.strip("-")


def strip_non_arabic(text: str, keep_spaces: bool = True, keep_digits: bool = True) -> str:
    """Keep only the Arabic letters (with their tashkeel) and drop the rest.

    Args:
        text: The text to filter.
        keep_spaces: Keep one space between words. If False, all spaces
            are removed.
        keep_digits: Keep digits (0-9, ٠-٩, ۰-۹).

    Latin letters, punctuation, symbols and tatweel are removed.

    >>> strip_non_arabic("Hello مرحبا World 2026!")
    'مرحبا 2026'
    >>> strip_non_arabic("Hello مرحبا World 2026!", keep_digits=False)
    'مرحبا'
    """
    kept = []
    for char in text:
        if is_arabic(char) or char in TASHKEEL:
            kept.append(char)
        elif keep_digits and char.isdecimal():
            kept.append(char)
        elif keep_spaces and char.isspace():
            kept.append(" ")
    result = "".join(kept)
    if keep_spaces:
        result = " ".join(result.split())  # collapse runs of spaces, trim the ends
    return result


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _use_utf8_console() -> None:
    """Let print() show Arabic on Windows consoles (which may use cp1252).

    Streams that cannot be reconfigured (for example in tests) are skipped.
    stdin uses "utf-8-sig" so a byte-order mark at the start is ignored.
    """
    for stream, encoding in ((sys.stdout, "utf-8"), (sys.stderr, "utf-8"), (sys.stdin, "utf-8-sig")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding=encoding)
        except (ValueError, OSError):
            pass


def _positive_int(value: str) -> int:
    """argparse type: accept only whole numbers greater than 0."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a whole number greater than 0")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser with one sub-command per tool."""
    parser = argparse.ArgumentParser(
        prog="arabic_text.py",
        description="Arabic Text Toolkit (أدوات النص العربي): clean and measure Arabic text.",
        epilog='Pass "-" instead of the text to read it from standard input.',
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add_command(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text, description=help_text)
        sub.add_argument("text", help='the text, or "-" to read standard input')
        return sub

    norm = add_command("normalize", "normalize letters, remove tashkeel and tatweel")
    norm.add_argument("--ya", action="store_true", help="also turn ى into ي")
    norm.add_argument("--ta-marbuta", action="store_true", help="also turn ة into ه")
    norm.add_argument("--hamza", action="store_true", help="also turn ؤ into و and ئ into ي")
    norm.add_argument("--keep-alef", action="store_true", help="do not change أ إ آ ٱ")
    norm.add_argument("--keep-tashkeel", action="store_true", help="do not remove tashkeel")
    norm.add_argument("--keep-tatweel", action="store_true", help="do not remove tatweel")
    norm.add_argument("--digits", choices=["latin", "arabic"], help="convert digits too")

    add_command("tashkeel", "remove tashkeel only")
    add_command("digits-latin", "convert ٠-٩ and ۰-۹ to 0-9")
    add_command("digits-arabic", "convert 0-9 to ٠-٩")
    add_command("slug", "make a URL slug")
    add_command("count", "count words")
    add_command("ratio", "share of letters that are Arabic (0.00 to 1.00)")
    reading = add_command("reading-time", "estimated reading time in minutes")
    reading.add_argument("--wpm", type=_positive_int, default=180, help="words per minute (default: 180)")
    return parser


def _read_text(text: str) -> str:
    """Return the text argument, or read standard input when it is "-"."""
    if text == "-":
        return sys.stdin.read().rstrip("\n")
    return text


def _run_command(args: argparse.Namespace, text: str) -> str:
    """Run the chosen sub-command and return what should be printed."""
    command = args.command
    if command == "normalize":
        return normalize(
            text,
            alef=not args.keep_alef,
            ya=args.ya,
            ta_marbuta=args.ta_marbuta,
            hamza=args.hamza,
            tashkeel=not args.keep_tashkeel,
            tatweel=not args.keep_tatweel,
            digits=args.digits,
        )
    if command == "tashkeel":
        return remove_tashkeel(text)
    if command == "digits-latin":
        return to_latin_digits(text)
    if command == "digits-arabic":
        return to_arabic_digits(text)
    if command == "slug":
        return slugify(text)
    if command == "count":
        return str(count_words(text))
    if command == "ratio":
        return f"{arabic_ratio(text):.2f}"
    if command == "reading-time":
        return str(reading_time(text, wpm=args.wpm))
    raise ValueError(f"unknown command: {command}")


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the command line. Returns the exit code."""
    _use_utf8_console()
    args = build_parser().parse_args(argv)
    text = _read_text(args.text)
    print(_run_command(args, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
