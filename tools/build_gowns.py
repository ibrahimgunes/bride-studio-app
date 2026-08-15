"""Katalogdaki her gelinlik için bir sayfa üretir, on bir dilde.

Sitenin varlık sebebi bu betik. Ana sayfa tek başına hiçbir aramada çıkmaz;
aramadan gelen trafiğin tamamı gelinlik sayfalarına düşecek — 151 gelinlik ×
11 dil, yani binden fazla indekslenebilir sayfa. Metinlerin hepsi zaten
Firestore'da duruyor ve on bir dile çevrilmiş durumda ([[reference-catalogue-copy]]),
yani burada çeviri değil yalnızca dizme işi var.

Sayfalar elle yazılmıyor çünkü katalog haftada bir değişiyor: gelinlik
ekleniyor, siliniyor, vitrin karesi yenileniyor. Elle yazılan bir sayfa ikinci
değişiklikte bayatlıyor. Bu betik her seferinde baştan üretiyor.

    python3 tools/build_gowns.py            # ne yapacağını söyler
    python3 tools/build_gowns.py --apply

Çıktı:
    gowns/<slug>/index.html                 İngilizce
    <dil>/gowns/<slug>/index.html           diğer on dil
    gowns/index.html, <dil>/gowns/          galeri
    assets/gowns/<id>.jpg                   vitrin karesi
    sitemap.xml
"""
import json, subprocess, argparse, pathlib, re, shutil, sys, urllib.request
import concurrent.futures as cf

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow gerekiyor: pip install pillow")

PROJECT = "bridestudio-181c6"
BUCKET = "bridestudio-181c6.firebasestorage.app"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
SITE = "https://bridestudio.app"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Firestore'daki dil kodu → adres yolundaki kod.
#
# İkisi aynı değil çünkü adreste `pt-BR` ve `zh-Hans` gereksiz uzun; arama
# motorları `pt` ve `zh` ile de doğru eşliyor. İngilizce kök dizinde, yani
# yolu yok.
LANGS = {
    "en": "",   "tr": "tr", "de": "de", "es": "es", "fr": "fr", "it": "it",
    "pt-BR": "pt", "ja": "ja", "ko": "ko", "zh-Hans": "zh", "hi": "hi",
}

# Sayfadaki sabit metinler. Gelinliğin kendi başlığı ve açıklaması zaten
# çevrilmiş geliyor; çevrilmesi gereken tek şey aradaki bağlayıcı sözler.
UI = {
    "en": ("Wedding dresses", "Try it on yourself", "Fabric", "Neckline", "Silhouette", "Length", "Detail", "See the whole collection", "Download on the App Store"),
    "tr": ("Gelinlikler", "Kendi üzerinde dene", "Kumaş", "Yaka", "Siluet", "Boy", "Detay", "Koleksiyonun tamamı", "App Store'dan indir"),
    "de": ("Brautkleider", "Probier es an dir", "Stoff", "Ausschnitt", "Silhouette", "Länge", "Detail", "Ganze Kollektion", "Im App Store laden"),
    "es": ("Vestidos de novia", "Pruébatelo", "Tejido", "Escote", "Silueta", "Largo", "Detalle", "Ver la colección", "Descargar en App Store"),
    "fr": ("Robes de mariée", "Essayez-la sur vous", "Tissu", "Encolure", "Silhouette", "Longueur", "Détail", "Voir la collection", "Télécharger sur l'App Store"),
    "it": ("Abiti da sposa", "Provalo su di te", "Tessuto", "Scollatura", "Silhouette", "Lunghezza", "Dettaglio", "Vedi la collezione", "Scarica su App Store"),
    "pt-BR": ("Vestidos de noiva", "Experimente em você", "Tecido", "Decote", "Silhueta", "Comprimento", "Detalhe", "Ver a coleção", "Baixar na App Store"),
    "ja": ("ウェディングドレス", "自分で試着する", "素材", "ネックライン", "シルエット", "丈", "ディテール", "コレクションを見る", "App Storeでダウンロード"),
    "ko": ("웨딩드레스", "직접 입어보기", "소재", "네크라인", "실루엣", "기장", "디테일", "전체 컬렉션 보기", "App Store에서 받기"),
    "zh-Hans": ("婚纱", "在自己身上试穿", "面料", "领口", "廓形", "长度", "细节", "查看全部系列", "在 App Store 下载"),
    "hi": ("वेडिंग ड्रेस", "खुद पर आज़माएँ", "कपड़ा", "नेकलाइन", "सिल्हूट", "लंबाई", "डिटेल", "पूरा कलेक्शन देखें", "App Store से डाउनलोड करें"),
}

APPSTORE = "https://apps.apple.com/app/id6741838118"


def token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def sv(node):
    """Firestore'un sarmaladığı değeri açar."""
    return (node or {}).get("stringValue", "")


def fetch_dresses(tok):
    """Katalogun tamamı, sayfalanarak.

    `pageToken` atlanırsa üç yüzden fazla belge sessizce kesiliyor — daha önce
    bir profili tam bu yüzden kaybetmiştik.
    """
    out, page = [], None
    while True:
        url = f"{BASE}/dresses?pageSize=300" + (f"&pageToken={page}" if page else "")
        d = json.load(urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {tok}"})))
        for doc in d.get("documents", []):
            f = doc["fields"]
            meta = f.get("metadata", {}).get("mapValue", {}).get("fields", {})
            title = f.get("title", {}).get("mapValue", {}).get("fields", {})
            desc = f.get("description", {}).get("mapValue", {}).get("fields", {})
            media = f.get("media", {}).get("mapValue", {}).get("fields", {})
            out.append({
                "id": doc["name"].rsplit("/", 1)[-1],
                "title": {k: sv(v) for k, v in title.items()},
                "desc": {k: sv(v) for k, v in desc.items()},
                "meta": {k: sv(v) for k, v in meta.items()},
                "image": sv(media.get("modelView")),
            })
        page = d.get("nextPageToken")
        if not page:
            break
    return sorted(out, key=lambda x: x["id"])


def slug(text, did):
    """Adres parçası: `d0233-romantic-tulle-ballgown`.

    Kimlik başta duruyor ki iki gelinliğin adı aynı olduğunda adresler
    çakışmasın — katalogda aynı başlıktan birden fazla var.
    """
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return f"{did.lower()}-{s}"[:70].rstrip("-")


def download_images(dresses, apply):
    """Vitrin karelerini siteye indirir.

    Storage'a doğrudan bağlanmıyoruz: sayfalar statik ve depoda duran bir
    dosyaya bakmaları gerekiyor, yoksa hem imza süresi dolan adresler hem de
    her ziyarette Storage faturası çıkardı.
    """
    out = ROOT / "assets" / "gowns"
    if apply:
        out.mkdir(parents=True, exist_ok=True)

    def one(d):
        dst = out / f"{d['id']}.jpg"
        if not d["image"] or (dst.exists() and dst.stat().st_size > 0):
            return
        if not apply:
            return
        tmp = f"/tmp/_g_{d['id']}"
        subprocess.run(["gcloud", "storage", "cp",
                        f"gs://{BUCKET}/{d['image']}", tmp], capture_output=True)
        if not pathlib.Path(tmp).exists():
            return
        im = Image.open(tmp).convert("RGB")
        im.thumbnail((1000, 1000), Image.LANCZOS)
        im.save(dst, quality=84, optimize=True)

    with cf.ThreadPoolExecutor(12) as ex:
        list(ex.map(one, dresses))


def head(lang, title, desc, canonical, alternates, image):
    """Her sayfanın başı.

    `hreflang` olmadan on bir dil birbirinin kopyası sayılıyor ve Google
    aralarından birini seçip diğerlerini indeksten düşürüyor — asıl kayıp
    orada olurdu.
    """
    alt = "\n".join(
        f'<link rel="alternate" hreflang="{h}" href="{u}">' for h, u in alternates
    )
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
{alt}
<link rel="alternate" hreflang="x-default" href="{SITE}/gowns/">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{image}">
<meta property="og:type" content="product">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{SITE}/assets/gowns.css">
</head>
<body>"""


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def gown_page(d, lang, path_map):
    code = LANGS[lang]
    ui = UI[lang]
    title = d["title"].get(lang) or d["title"].get("en", d["id"])
    desc = d["desc"].get(lang) or d["desc"].get("en", "")
    canonical = f"{SITE}/{code + '/' if code else ''}gowns/{path_map[lang]}/"
    alternates = [(l if l not in ("pt-BR", "zh-Hans") else l,
                   f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/{path_map[l]}/")
                  for l in LANGS]
    img = f"{SITE}/assets/gowns/{d['id']}.jpg"
    m = d["meta"]

    # Yapısal veri: arama sonucunda görselin ve adın birlikte çıkmasını
    # sağlıyor. Fiyat yok, çünkü satılan bir ürün değil.
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Product",
        "name": title, "description": desc, "image": img,
        "brand": {"@type": "Brand", "name": "Bride Studio"},
        "category": m.get("silhouette", ""),
    }, ensure_ascii=False)

    rows = [(ui[4], m.get("silhouette")), (ui[2], m.get("fabric")),
            (ui[3], m.get("neckline")), (ui[5], m.get("length")),
            (ui[6], m.get("feature"))]
    spec = "\n".join(
        f"<div class=r><dt>{esc(l)}</dt><dd>{esc(v)}</dd></div>"
        for l, v in rows if v)

    home = f"{SITE}/{code + '/' if code else ''}"
    return f"""{head(lang, esc(title) + " — Bride Studio", esc(desc), canonical, alternates, img)}
<script type="application/ld+json">{ld}</script>
<header><a class=mark href="{home}">Bride Studio</a>
<a class=back href="{SITE}/{code + '/' if code else ''}gowns/">{esc(ui[0])}</a></header>
<main>
  <figure><img src="{img}" alt="{esc(title)}" width="1000" height="1000"></figure>
  <div class=info>
    <p class=eyebrow>{esc(m.get('style',''))}</p>
    <h1>{esc(title)}</h1>
    <div class=rule></div>
    <p class=lead>{esc(desc)}</p>
    <dl class=spec>{spec}</dl>
    <a class=btn href="{APPSTORE}">{esc(ui[1])}</a>
  </div>
</main>
<footer>
  <a href="{SITE}/{code + '/' if code else ''}gowns/">{esc(ui[7])}</a>
  <span>Results are AI visualisations, not photographs of a real fitting.</span>
</footer>
</body></html>"""


def index_page(dresses, lang, paths):
    code = LANGS[lang]
    ui = UI[lang]
    canonical = f"{SITE}/{code + '/' if code else ''}gowns/"
    alternates = [(l, f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/") for l in LANGS]
    cards = []
    for d in dresses:
        t = d["title"].get(lang) or d["title"].get("en", d["id"])
        cards.append(
            f'<a class=card href="{SITE}/{code + "/" if code else ""}gowns/{paths[d["id"]][lang]}/">'
            f'<img src="{SITE}/assets/gowns/{d["id"]}.jpg" alt="{esc(t)}" loading="lazy" width="1000" height="1000">'
            f'<h2>{esc(t)}</h2></a>')
    return f"""{head(lang, esc(ui[0]) + " — Bride Studio", esc(ui[0]), canonical, alternates, f"{SITE}/assets/gowns/{dresses[0]['id']}.jpg")}
<header><a class=mark href="{SITE}/{code + '/' if code else ''}">Bride Studio</a></header>
<main class=grid-wrap>
  <h1 class=page-title>{esc(ui[0])}</h1>
  <div class=grid>{''.join(cards)}</div>
</main>
<footer><a href="{APPSTORE}">{esc(ui[8])}</a></footer>
</body></html>"""


CSS = """/* Gelinlik sayfaları — ana sayfayla aynı dil, ayrı dosyada.
   Bin altı yüz sayfa aynı stili taşıyacak; satır içine gömmek her sayfayı
   şişirir, ayrı dosya bir kez indirilip önbelleğe giriyor. */
:root{--cream:#FAF7F4;--ink:#3C3732;--taupe:#A58E7C;--gold:#BD9973;--dark:#14100E;--hair:rgba(165,142,124,.22)}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--ink);font:400 17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
h1,h2{font-family:"New York",ui-serif,Georgia,serif;font-weight:400;line-height:1.1;letter-spacing:-.015em;margin:0}
a{color:inherit;text-decoration:none}
img{display:block;max-width:100%;height:auto}
header{display:flex;justify-content:space-between;align-items:center;max-width:1180px;margin:0 auto;padding:22px 30px;border-bottom:1px solid var(--hair)}
.mark{font-family:"New York",ui-serif,Georgia,serif;font-size:20px}
.back{font-size:14px;color:var(--taupe)}
main{max-width:1180px;margin:0 auto;padding:60px 30px;display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:start}
main figure{margin:0;border-radius:20px;overflow:hidden;background:#efe9e3}
.eyebrow{font:600 11px/1 sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--taupe);margin:0 0 14px}
.info h1{font-size:clamp(28px,3.6vw,44px)}
.rule{width:46px;height:1px;background:var(--gold);opacity:.6;margin:20px 0}
.lead{color:#5f584f;margin:0 0 28px}
.spec{margin:0 0 32px;border-top:1px solid var(--hair)}
.spec .r{display:flex;justify-content:space-between;gap:20px;padding:12px 0;border-bottom:1px solid var(--hair)}
.spec dt{font:600 11px/1.6 sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--taupe);margin:0}
.spec dd{margin:0;font-family:"New York",ui-serif,Georgia,serif;font-size:17px}
.btn{display:inline-block;padding:16px 34px;border-radius:999px;background:var(--dark);color:#fff;font:500 15px/1 sans-serif}
footer{max-width:1180px;margin:0 auto;padding:40px 30px 70px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;color:var(--taupe);font-size:13px}
.grid-wrap{display:block}
.page-title{font-size:clamp(30px,4vw,52px);margin-bottom:34px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.grid .card img{border-radius:14px;background:#efe9e3}
.grid .card h2{font-size:15px;margin-top:12px}
@media(max-width:900px){main{grid-template-columns:1fr;gap:30px;padding:34px 22px}.grid{grid-template-columns:repeat(2,1fr)}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    tok = token()
    dresses = fetch_dresses(tok)
    dresses = [d for d in dresses if d["image"] and d["title"].get("en")]
    print(f"katalog: {len(dresses)} gelinlik")

    # Her gelinliğin her dildeki adresi önden hesaplanıyor: `hreflang`
    # etiketleri bütün dilleri bilmek zorunda, yani sayfa yazılırken hepsi
    # elde olmalı.
    paths = {}
    for d in dresses:
        paths[d["id"]] = {l: slug(d["title"].get(l) or d["title"]["en"], d["id"])
                          for l in LANGS}

    pages = len(dresses) * len(LANGS) + len(LANGS)
    print(f"üretilecek: {pages} sayfa ({len(LANGS)} dil)")
    if not a.apply:
        d = dresses[0]
        print("örnek adres:", f"/gowns/{paths[d['id']]['en']}/")
        print("kuru çalışma — yazmak için --apply")
        return

    download_images(dresses, True)
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "gowns.css").write_text(CSS)

    urls = []
    for lang, code in LANGS.items():
        base = ROOT / code if code else ROOT
        for d in dresses:
            p = base / "gowns" / paths[d["id"]][lang]
            p.mkdir(parents=True, exist_ok=True)
            (p / "index.html").write_text(gown_page(d, lang, paths[d["id"]]))
            urls.append(f"{SITE}/{code + '/' if code else ''}gowns/{paths[d['id']][lang]}/")
        gi = base / "gowns"
        gi.mkdir(parents=True, exist_ok=True)
        (gi / "index.html").write_text(index_page(dresses, lang, paths))
        urls.append(f"{SITE}/{code + '/' if code else ''}gowns/")

    # Sitemap olmadan Google bu sayfaların çoğunu aylarca bulamaz: hiçbirine
    # ana sayfadan doğrudan bağlantı yok.
    body = "\n".join(f"<url><loc>{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"<url><loc>{SITE}/</loc></url>\n{body}\n</urlset>\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")

    print(f"yazıldı: {len(urls)} sayfa + sitemap")


if __name__ == "__main__":
    main()
