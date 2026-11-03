# أمثلة حقيقية | Real examples

كل مثال هنا منسوخ من تشغيل فعلي للأداة، الأمر ثم الناتج كما طلع بالضبط.

Every example below was copied from a real run: the command, then its exact output.

## 1. normalize: توحيد الحروف | normalize letters

Removes tashkeel, unifies alef (default), and with the flags turns ى into ي and ة into ه.

```text
$ python arabic_text.py normalize --ya --ta-marbuta "إِلَى الْمَدْرَسَةِ الْأُولَى"
الي المدرسه الاولي
```

## 2. tashkeel: حذف التشكيل | remove tashkeel

Removes harakat, shadda, sukun, the small alef and Quranic marks. The alef wasla ٱ stays (`normalize` turns it into ا).

```text
$ python arabic_text.py tashkeel "مَدْرَسَتِي جَمِيلَةٌ وَمُعَلِّمِي رَائِعٌ"
مدرستي جميلة ومعلمي رائع
```

## 3. digits-latin: الأرقام العربية إلى 0-9 | Arabic digits to 0-9

The Arabic thousands separator ٬ becomes `,` and the decimal separator ٫ becomes `.`.

```text
$ python arabic_text.py digits-latin "السعر ١٬٢٥٠٫٧٥ ريال"
السعر 1,250.75 ريال
```

## 4. digits-arabic: من 0-9 إلى الأرقام العربية | 0-9 to Arabic digits

```text
$ python arabic_text.py digits-arabic "الصف 2 - الفصل 1 - عام 2026"
الصف ٢ - الفصل ١ - عام ٢٠٢٦
```

## 5. slug: رابط نظيف | URL slug

Arabic stays Arabic, Latin is lowercased, Arabic digits become 0-9, words are joined with `-`.

```text
$ python arabic_text.py slug "دليل Python للمبتدئين ٢٠٢٦"
دليل-python-للمبتدئين-2026
```

## 6. count: عدد الكلمات | word count

```text
$ python arabic_text.py count "السلام عليكم ورحمة الله وبركاته"
5
```

## 7. ratio: نسبة الحروف العربية | share of Arabic letters

14 of the 20 letters are Arabic (spaces do not count).

```text
$ python arabic_text.py ratio "أحب البرمجة بلغة Python"
0.70
```

## 8. reading-time: وقت القراءة من stdin | reading time from stdin

Passing `-` reads the text from standard input. 400 words at 180 words per minute is 3 minutes (rounded up). Run in bash or cmd; see the README note for PowerShell.

```text
$ python -X utf8 -c "print('كلمة ' * 400)" | python arabic_text.py reading-time -
3
```
