"""The four variable fonts the page uses (all SIL OFL 1.1), fetched from github.com/google/fonts
into fonts/. git does not hold binaries, so a clean clone fetches them here (~2 MB).
usage: python -I tools/fonts.py        (run from the demo folder; skips files already present)"""
import os, urllib.request, urllib.parse

FONTS = {  # page filename -> google/fonts path
    'Inter.ttf': 'inter/Inter[opsz,wght].ttf',
    'Newsreader-VF.ttf': 'newsreader/Newsreader[opsz,wght].ttf',
    'Newsreader-Italic-VF.ttf': 'newsreader/Newsreader-Italic[opsz,wght].ttf',
    'JetBrainsMono-var.ttf': 'jetbrainsmono/JetBrainsMono[wght].ttf',
}
BASE = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the demo folder
OUT = os.path.join(HERE, 'fonts')
os.makedirs(OUT, exist_ok = True)
for name, rel in FONTS.items():
    dst = os.path.join(OUT, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 10000:
        print(name, 'already present'); continue
    url = BASE + urllib.parse.quote(rel)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=120).read()
    open(dst, 'wb').write(data)
    print(name, len(data), 'bytes')
print('fonts ready in', OUT)
