# -*- coding: utf-8 -*-
"""Tests for arabic_text.py - standard library only, nothing to install.

Run from this folder:

    python -m unittest -v

The examples written inside the docstrings of arabic_text.py are checked
too (see load_tests at the bottom).
"""

import contextlib
import doctest
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

import arabic_text
from arabic_text import (
    arabic_ratio,
    count_words,
    is_arabic,
    normalize,
    reading_time,
    remove_tashkeel,
    remove_tatweel,
    slugify,
    strip_non_arabic,
    to_arabic_digits,
    to_latin_digits,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "arabic_text.py")


class RemoveTashkeelTests(unittest.TestCase):
    def test_removes_harakat_shadda_sukun_and_tanween(self):
        self.assertEqual(remove_tashkeel("مُحَمَّدٌ"), "محمد")
        self.assertEqual(remove_tashkeel("مَدْرَسَةٌ جَمِيلَةٌ"), "مدرسة جميلة")
        self.assertEqual(remove_tashkeel("كِتَابًا"), "كتابا")

    def test_removes_superscript_alef(self):
        self.assertEqual(remove_tashkeel("هٰذَا"), "هذا")

    def test_removes_quranic_marks(self):
        self.assertEqual(
            remove_tashkeel("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"),
            "بسم ٱلله ٱلرحمن ٱلرحيم",
        )
        # U+06DB is a small waqf sign, U+0610 a small sign above a letter.
        self.assertEqual(remove_tashkeel("رَيْبَ ۛ فِيهِ"), "ريب  فيه")
        self.assertEqual(remove_tashkeel("محمدؐ"), "محمد")

    def test_keeps_hamza_stored_as_separate_mark(self):
        # "ا" + combining hamza above is the same letter as "أ".
        self.assertEqual(remove_tashkeel("أَ"), "أ")

    def test_empty_and_non_arabic_text_unchanged(self):
        self.assertEqual(remove_tashkeel(""), "")
        self.assertEqual(remove_tashkeel("Hello 123, world!"), "Hello 123, world!")


class RemoveTatweelTests(unittest.TestCase):
    def test_removes_every_tatweel(self):
        self.assertEqual(remove_tatweel("مـــرحـبـا"), "مرحبا")
        self.assertEqual(remove_tatweel(""), "")


class NormalizeTests(unittest.TestCase):
    def test_default_unifies_alef_and_removes_tashkeel(self):
        self.assertEqual(normalize("أَحْمَد إِبْرَاهِيم آدَم"), "احمد ابراهيم ادم")

    def test_alef_wasla(self):
        self.assertEqual(normalize("ٱلْحَمْدُ"), "الحمد")

    def test_alef_can_be_turned_off(self):
        self.assertEqual(normalize("أحمد", alef=False), "أحمد")

    def test_ya_option(self):
        self.assertEqual(normalize("مستشفى"), "مستشفى")
        self.assertEqual(normalize("مستشفى", ya=True), "مستشفي")

    def test_ta_marbuta_option(self):
        self.assertEqual(normalize("مدرسة"), "مدرسة")
        self.assertEqual(normalize("مدرسة", ta_marbuta=True), "مدرسه")

    def test_hamza_option(self):
        self.assertEqual(normalize("مسؤول سائل", hamza=True), "مسوول سايل")

    def test_keep_tashkeel_and_tatweel(self):
        text = "مَـرْحَبًا"
        self.assertEqual(normalize(text, tashkeel=False, tatweel=False), text)
        self.assertEqual(normalize(text), "مرحبا")

    def test_digits_option(self):
        self.assertEqual(normalize("صفحة ١٢", digits="latin"), "صفحة 12")
        self.assertEqual(normalize("رقم 7", digits="arabic"), "رقم ٧")

    def test_bad_digits_value_raises(self):
        with self.assertRaises(ValueError):
            normalize("نص", digits="roman")

    def test_mixed_arabic_and_english(self):
        self.assertEqual(normalize("أتعلم Python 3.12"), "اتعلم Python 3.12")

    def test_empty_string(self):
        self.assertEqual(normalize(""), "")

    def test_is_idempotent(self):
        samples = [
            "",
            "أَهْلًا وَسَهْلًا",
            "مـــسؤولٌ في المستشفى الجامعيّة",
            "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
            "Room ١٠١ - Python ۳",
            "أٓ",
        ]
        option_sets = [
            {},
            {"ya": True, "ta_marbuta": True, "hamza": True},
            {"alef": False, "tashkeel": False, "tatweel": False},
            {"digits": "latin"},
            {"digits": "arabic"},
        ]
        for text in samples:
            for options in option_sets:
                with self.subTest(text=text, options=options):
                    once = normalize(text, **options)
                    self.assertEqual(normalize(once, **options), once)


class DigitTests(unittest.TestCase):
    def test_arabic_indic_to_latin(self):
        self.assertEqual(to_latin_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789")

    def test_persian_to_latin(self):
        self.assertEqual(to_latin_digits("۰۱۲۳۴۵۶۷۸۹"), "0123456789")

    def test_arabic_separators_to_latin(self):
        self.assertEqual(to_latin_digits("١٬٢٣٤٫٥"), "1,234.5")

    def test_latin_to_arabic(self):
        self.assertEqual(to_arabic_digits("الصف 2 - عام 2026"), "الصف ٢ - عام ٢٠٢٦")
        self.assertEqual(to_arabic_digits("۴۵"), "٤٥")

    def test_text_without_digits_unchanged(self):
        self.assertEqual(to_latin_digits("مرحبا"), "مرحبا")
        self.assertEqual(to_arabic_digits(""), "")

    def test_round_trip(self):
        text = "Room 101, year 2026"
        self.assertEqual(to_latin_digits(to_arabic_digits(text)), text)


class IsArabicTests(unittest.TestCase):
    def test_arabic_letters(self):
        for char in "ابتثجحخدذرزسشصضطظعغفقكلمنهويءأإآةىپچگ":
            with self.subTest(char=char):
                self.assertTrue(is_arabic(char))

    def test_not_arabic_letters(self):
        for char in ["a", "Z", "1", "٣", "،", "؟", " ", "ـ", "َ", "!"]:
            with self.subTest(char=char):
                self.assertFalse(is_arabic(char))

    def test_needs_exactly_one_character(self):
        with self.assertRaises(ValueError):
            is_arabic("")
        with self.assertRaises(ValueError):
            is_arabic("مرحبا")


class ArabicRatioTests(unittest.TestCase):
    def test_simple_ratios(self):
        self.assertEqual(arabic_ratio("مرحبا"), 1.0)
        self.assertEqual(arabic_ratio("Hello"), 0.0)
        self.assertEqual(arabic_ratio("Python بايثون"), 0.5)

    def test_no_letters_gives_zero(self):
        self.assertEqual(arabic_ratio(""), 0.0)
        self.assertEqual(arabic_ratio("١٢٣ 456 !!"), 0.0)

    def test_ignores_tashkeel_tatweel_digits_and_punctuation(self):
        self.assertEqual(arabic_ratio("مُـــرْحَبًا، 2026!"), 1.0)
        self.assertAlmostEqual(arabic_ratio("أحب البرمجة بلغة Python"), 14 / 20)


class CountWordsTests(unittest.TestCase):
    def test_empty_and_spaces(self):
        self.assertEqual(count_words(""), 0)
        self.assertEqual(count_words("   \n\t "), 0)

    def test_arabic_sentence(self):
        self.assertEqual(count_words("السلام عليكم ورحمة الله وبركاته"), 5)

    def test_punctuation_alone_is_not_a_word(self):
        self.assertEqual(count_words("مرحبا ، كيف حالك ؟ - «»"), 3)

    def test_tashkeel_does_not_split_words(self):
        self.assertEqual(count_words("مُحَمَّدٌ رَسُولُ ٱللَّهِ"), 3)

    def test_mixed_text_and_numbers(self):
        self.assertEqual(count_words("I love بايثون 3"), 4)


class SlugifyTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(slugify("مرحبا بالعالم!"), "مرحبا-بالعالم")

    def test_arabic_punctuation_and_quotes(self):
        self.assertEqual(slugify("«الدرس الأول»، مقدمة؛ لماذا؟"), "الدرس-الاول-مقدمة-لماذا")

    def test_mixed_and_lowercase_latin(self):
        self.assertEqual(slugify("Python للمبتدئين 101"), "python-للمبتدئين-101")

    def test_tashkeel_tatweel_and_arabic_digits(self):
        self.assertEqual(slugify("الـدَّرْسُ ٣"), "الدرس-3")

    def test_collapses_and_trims_dashes(self):
        self.assertEqual(slugify("  --مرحبا -- _ -- عالم--  "), "مرحبا-عالم")

    def test_latin_accents_are_removed(self):
        self.assertEqual(slugify("Café عربي"), "cafe-عربي")

    def test_empty_or_punctuation_only(self):
        self.assertEqual(slugify(""), "")
        self.assertEqual(slugify("!!! ، ؟ ..."), "")

    def test_is_idempotent(self):
        for text in ["مرحبا بالعالم!", "دليل Python للمبتدئين ٢٠٢٦", "«أ» - B"]:
            with self.subTest(text=text):
                once = slugify(text)
                self.assertEqual(slugify(once), once)


class StripNonArabicTests(unittest.TestCase):
    def test_default_keeps_digits_and_spaces(self):
        self.assertEqual(strip_non_arabic("Hello مرحبا World 2026!"), "مرحبا 2026")

    def test_drop_digits(self):
        self.assertEqual(strip_non_arabic("الصف ٣ Grade 3", keep_digits=False), "الصف")

    def test_drop_spaces(self):
        self.assertEqual(strip_non_arabic("مرحبا بالعالم", keep_spaces=False), "مرحبابالعالم")

    def test_keeps_tashkeel_drops_tatweel(self):
        self.assertEqual(strip_non_arabic("مُحَمَّد and عـلي"), "مُحَمَّد علي")

    def test_empty(self):
        self.assertEqual(strip_non_arabic(""), "")


class ReadingTimeTests(unittest.TestCase):
    def test_empty_text_is_zero(self):
        self.assertEqual(reading_time(""), 0)
        self.assertEqual(reading_time("!!! ،"), 0)

    def test_short_text_is_at_least_one_minute(self):
        self.assertEqual(reading_time("مرحبا"), 1)

    def test_rounds_up(self):
        self.assertEqual(reading_time("كلمة " * 180), 1)
        self.assertEqual(reading_time("كلمة " * 181), 2)
        self.assertEqual(reading_time("كلمة " * 360), 2)

    def test_custom_speed(self):
        self.assertEqual(reading_time("word " * 100, wpm=50), 2)

    def test_bad_speed_raises(self):
        with self.assertRaises(ValueError):
            reading_time("مرحبا", wpm=0)


class CommandLineTests(unittest.TestCase):
    def run_main(self, *argv):
        """Call main() and return what it printed (without the newline)."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = arabic_text.main(list(argv))
        self.assertEqual(exit_code, 0)
        return output.getvalue().rstrip("\n")

    def test_every_command(self):
        cases = [
            (["normalize", "أَهْلًا وَسَهْلًا"], "اهلا وسهلا"),
            (["tashkeel", "مُحَمَّدٌ"], "محمد"),
            (["digits-latin", "١٢٣"], "123"),
            (["digits-arabic", "123"], "١٢٣"),
            (["slug", "مرحبا بالعالم!"], "مرحبا-بالعالم"),
            (["count", "السلام عليكم ورحمة الله"], "4"),
            (["ratio", "Python بايثون"], "0.50"),
            (["reading-time", "مرحبا"], "1"),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(self.run_main(*argv), expected)

    def test_normalize_flags(self):
        result = self.run_main("normalize", "--ya", "--ta-marbuta", "--hamza", "مستشفى المدينة مسؤول")
        self.assertEqual(result, "مستشفي المدينه مسوول")
        self.assertEqual(self.run_main("normalize", "--keep-alef", "أحمد"), "أحمد")
        self.assertEqual(self.run_main("normalize", "--digits", "latin", "صفحة ٥"), "صفحة 5")

    def test_reading_time_wpm_flag(self):
        self.assertEqual(self.run_main("reading-time", "--wpm", "2", "واحد اثنان ثلاثة"), "2")

    def test_reads_stdin_when_text_is_dash(self):
        with mock.patch("sys.stdin", io.StringIO("مـرحبا بالعالم!\n")):
            self.assertEqual(self.run_main("slug", "-"), "مرحبا-بالعالم")

    def test_bad_wpm_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                arabic_text.main(["reading-time", "--wpm", "0", "نص"])

    def test_real_process_prints_utf8(self):
        # Runs the script like a user would; on Windows this checks that
        # Arabic output does not crash on a cp1252 console encoding.
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        completed = subprocess.run(
            [sys.executable, SCRIPT, "slug", "-"],
            input="مرحبا بالعالم!".encode("utf-8"),
            capture_output=True,
            env=env,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        self.assertEqual(completed.stdout.decode("utf-8").strip(), "مرحبا-بالعالم")


def load_tests(loader, tests, pattern):
    """Also run the >>> examples written in arabic_text.py's docstrings."""
    tests.addTests(doctest.DocTestSuite(arabic_text))
    return tests


if __name__ == "__main__":
    unittest.main()
