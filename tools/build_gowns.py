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
import hashlib, json, subprocess, argparse, pathlib, re, shutil, sys, unicodedata, urllib.request
import concurrent.futures as cf

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import consent
import langhint

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow gerekiyor: pip install pillow")

PROJECT = "bridestudio-181c6"
BUCKET = "bridestudio-181c6.firebasestorage.app"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
SITE = "https://bridestudio.app"

# GA4 ölçüm kimliği. Firebase projesinin kendi web akışı, yani uygulama ve site
# aynı mülkte görünüyor — "kaç kişi siteye geldi" ile "kaç kişi indirdi" iki
# ayrı panelde durmuyor. Pin bağlantıları `utm_source=pinterest` taşıyor, o
# yüzden trafiğin kaynağı ve hangi gelinlikten geldiği burada okunabiliyor.
GA = "G-CGJLBG4684"
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

# Denklemin altındaki üç kelime. Cümle değil etiket: kareler zaten anlatıyor,
# yazı yalnızca hangisinin ne olduğunu söylüyor.
# Hangi gelinliğin vitrin karesini hangi model ürettiği.
#
# Firestore'daki üretim kayıtlarından bir kez çıkarıldı ve dosyaya yazıldı:
# her kuruluşta yeniden sorgulamak bin dokuz yüz sayfa için gereksiz, ve
# eşleşme yalnızca yeni gelinlik geldiğinde değişiyor.
# Yenilemek için: tools/map_models.py
MODEL_BY_DRESS = json.loads((pathlib.Path(__file__).parent / "dress_model.json").read_text())

EQUATION = {
    "en": ("Her photo", "This gown", "On her"),
    "tr": ("Fotoğrafı", "Bu gelinlik", "Üzerinde"),
    "de": ("Ihr Foto", "Dieses Kleid", "An ihr"),
    "es": ("Su foto", "Este vestido", "En ella"),
    "fr": ("Sa photo", "Cette robe", "Sur elle"),
    "it": ("La sua foto", "Questo abito", "Su di lei"),
    "pt-BR": ("A foto dela", "Este vestido", "Nela"),
    "ja": ("彼女の写真", "このドレス", "着た姿"),
    "ko": ("그녀의 사진", "이 드레스", "입은 모습"),
    "zh-Hans": ("她的照片", "这件婚纱", "穿上后"),
    "hi": ("उनकी फ़ोटो", "यह ड्रेस", "उन पर"),
}

# Dönüşümün altındaki satır.
#
# Eskiden burada yalnızca "On her" yazıyordu — resmi etiketleyen ölü bir kelime.
# Telefonda Pinterest'in kendi tarayıcısından bakınca öksüz duruyordu ve
# sayfanın rakiplerden ayrıldığı yeri hiç söylemiyordu: gelinliği kadının kendi
# boyunda, kilosunda ve teninde göstermesi. Etiket cümleye çevrildi.
#
# Yeri katlanma çizgisinin üstünde kalmalı: Pinterest'in tarayıcısında altta
# "Save" çubuğu ekranın bir kısmını yiyor, aşağıdaki hiçbir şey görülmüyor.
PROMISE = {
    "en": "Try this gown with your own face, height, size and skin tone.",
    "tr": "Bu gelinliği kendi yüzün, boyun, kilon ve ten renginle dene.",
    "de": "Probiere dieses Kleid mit deinem Gesicht, deiner Größe, deiner Figur und deinem Hautton.",
    "es": "Prueba este vestido con tu propio rostro, tu altura, tu talla y tu tono de piel.",
    "fr": "Essaie cette robe avec ton visage, ta taille, ta silhouette et ton teint.",
    "it": "Prova questo abito con il tuo viso, la tua altezza, la tua taglia e il tuo incarnato.",
    "pt-BR": "Experimente este vestido com seu rosto, sua altura, seu manequim e seu tom de pele.",
    "ja": "このドレスを、あなたの顔・身長・体型・肌の色で試してみて。",
    "ko": "이 드레스를 당신의 얼굴, 키, 체형, 피부톤으로 입어보세요.",
    "zh-Hans": "用你的脸庞、身高、身形和肤色试穿这件婚纱。",
    "hi": "इस ड्रेस को अपने चेहरे, कद, नाप और रंगत के साथ आज़माएँ।",
}

# Dilin kendi adı, İngilizcesi değil: menüde "Türkçe" arayan biri "Turkish"
# yazısını taramıyor.
LANG_NAMES = {
    "en": "English", "tr": "Türkçe", "de": "Deutsch", "es": "Español",
    "fr": "Français", "it": "Italiano", "pt-BR": "Português", "ja": "日本語",
    "ko": "한국어", "zh-Hans": "简体中文", "hi": "हिन्दी",
}

APPSTORE = "https://apps.apple.com/app/id6741838118"

# Stil dosyasının sürümü.
#
# Adres sabit olduğu için tarayıcı bir kez indirdiğini bir daha sormuyor:
# sayfa yeni gelirken stil eskide kalıyor ve düzen bozuk görünüyor. Kategori
# şeridi tam bu yüzden düz metin olarak çıktı — HTML yeniydi, CSS önbellekten
# geliyordu. Damga içerikten türüyor, yani stil değişmedikçe adres de
# değişmiyor ve önbellek boşuna bozulmuyor.
def css_stamp():
    return hashlib.sha1(CSS.encode()).hexdigest()[:8]


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
                # Terzi kalıbındaki hâli — `.tf` bölümünün sol karesi.
                "raw": sv(media.get("rawSource")),
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
    """Her gelinliğin iki karesini siteye indirir.

    Storage'a doğrudan bağlanmıyoruz: sayfalar statik ve depoda duran bir
    dosyaya bakmaları gerekiyor, yoksa hem imza süresi dolan adresler hem de
    her ziyarette Storage faturası çıkardı.

    İki kare, çünkü sayfanın anlattığı şey bir olay: `gowns/` vitrin karesi,
    `forms/` gelinliğin terzi kalıbındaki hâli. `.tf` bölümü ikisini üst üste
    koyup aralarından perde geçiriyor.

    **Ham kare uzun süre indirilmiyordu.** `forms/` bir kez elle doldurulmuş,
    betik ise yalnızca vitrini indiriyordu; dosyası olmayan gelinlikte bölüm
    `return ""` ile sessizce düşüyor. 2026-08-30'da katalog 175'ten 296'ya
    çıkınca 121 sayfa o bölüm olmadan basıldı ve eksiklik ancak göze
    çarptığı için fark edildi.
    """
    gowns = ROOT / "assets" / "gowns"
    forms = ROOT / "assets" / "forms"
    if apply:
        gowns.mkdir(parents=True, exist_ok=True)
        forms.mkdir(parents=True, exist_ok=True)

    # Hangi karenin indirildiği yazılıyor.
    #
    # Dosyanın **varlığına** bakmak yetmiyor: sitedeki ad sabit
    # (`gowns/D0417.jpg`) ama kaynağı değişiyor. Vitrin yenilendiğinde
    # `promote_results` yeni bir damgayla yazıyor —
    # `models/model_20260830095851.webp` — ve eski ada bakan bir kontrol
    # "dosya duruyor" deyip geçiyordu. 2026-08-30'da beğenilmeyen on dört
    # vitrin yeniden üretildi ve sitede hepsi eski kareyi göstermeye devam
    # etti; kusur ancak gözle fark edildi.
    stamp = ROOT / "assets" / "sources.json"
    seen = json.loads(stamp.read_text()) if stamp.exists() else {}
    now = {}

    def fetch(src, dst, box, tag, key):
        if not src:
            return
        now[key] = src
        if seen.get(key) == src and dst.exists() and dst.stat().st_size > 0:
            return
        if not apply:
            return
        tmp = f"/tmp/_{tag}_{dst.stem}"
        subprocess.run(["gcloud", "storage", "cp", f"gs://{BUCKET}/{src}", tmp],
                       capture_output=True)
        if not pathlib.Path(tmp).exists():
            return
        im = Image.open(tmp).convert("RGB")
        im.thumbnail((box, box), Image.LANCZOS)
        im.save(dst, quality=84, optimize=True)

    def one(d):
        fetch(d["image"], gowns / f"{d['id']}.jpg", 1000, "g", f"g:{d['id']}")
        # Kalıp karesi sayfada 360 px genişliğinde duruyor; vitrin karesi
        # kadar büyük inmesine gerek yok.
        fetch(d.get("raw"), forms / f"{d['id']}.jpg", 720, "f", f"f:{d['id']}")

    with cf.ThreadPoolExecutor(12) as ex:
        list(ex.map(one, dresses))

    stale = [k for k, v in now.items() if seen.get(k) != v]
    if stale:
        print(f"kaynağı değişmiş {len(stale)} kare"
              + ("" if apply else " (yazmak için --apply)"))
    if apply:
        stamp.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")


def head(lang, title, desc, canonical, alternates, image):
    """Her sayfanın başı.

    `hreflang` olmadan on bir dil birbirinin kopyası sayılıyor ve Google
    aralarından birini seçip diğerlerini indeksten düşürüyor — asıl kayıp
    orada olurdu.

    Favicon etiketleri burada duruyor çünkü daha önce durmuyorlardı: yayındaki
    sayfalara elle eklenmişlerdi ve bu betiğin her koşusu bin altı yüz sayfadan
    hepsini birden siliyordu. Üretilen bir dosyaya elle dokunmak, bir sonraki
    üretime kadar süren bir düzeltmedir.
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
<link rel="icon" href="/assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/gowns.css?v={css_stamp()}">
{consent.head_scripts(GA)}
</head>
<body>{langhint.strip(lang)}"""


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def lang_picker(current, url_for):
    """Aynı sayfanın öteki dilleri.

    `hreflang` etiketleri arama motoruna hangi dilin kime gösterileceğini
    söylüyor ama insana bir şey söylemiyor: siteye giren biri kendi diline
    geçemiyordu. Bağlantılar aynı gelinliğin öteki dildeki adresine gidiyor,
    ana sayfaya değil — dil değiştirmek okuduğun şeyi kaybetmek olmamalı.

    `<details>` ile: açılır menü için JavaScript gerekmiyor, ve betik
    çalışmasa da menü çalışıyor.
    """
    items = "".join(
        f'<a href="{url_for(l)}"{" class=on" if l == current else ""}>{LANG_NAMES[l]}</a>'
        for l in LANGS)
    return (f'<details class=lang><summary>{LANG_NAMES[current]}</summary>'
            f'<div class=lang-menu>{items}</div></details>')


# Dönüşümü başlatan betik.
#
# f-string'in dışında duruyor: JavaScript süslü parantez dolu ve gövdeye
# doğrudan yazıldığında biçimlendiriciyi bozuyor. Sabit olarak durup tek bir
# yer tutucuyla giriyor.
REVEAL_JS = """<script>
/* Gösteri, bölüm ekrana girdiğinde başlıyor.

   Sayfa açılır açılmaz başlatmak, telefonda çoğu zaman kadın daha bakmadan
   bitmesi demek — kaçırılan bir animasyon, hiç olmayanla aynı. Bir kez
   oynuyor: tekrarlayan bir hareket bir süre sonra göze çarpmayı bırakıyor. */
(function(){
  var tf = document.querySelector('.tf');
  if (!tf) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) { tf.classList.add('on'); return; }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (!e.isIntersecting) return;
      tf.classList.add('on');
      io.disconnect();
    });
  }, {threshold: 0.45});
  io.observe(tf);
})();
</script>"""


def equation_block(d, lang, img):
    """Gelinlik terzi kalıbında duruyor; bir perde geçiyor; kadının üstünde.

    Pinterest'ten gelen kadın ana sayfayı hiç görmüyor, doğrudan buraya
    düşüyor. Sayfa bitmiş bir vitrin karesiyle açılıyordu — tam da kadının az
    önce kaydırıp geldiği şeyle, yani yeni hiçbir şey söylemeden.

    Anlatılacak şey bir nesne değil bir olay: bu gelinlik giyilebilir. O yüzden
    iki kare üst üste duruyor ve aralarından bir bant geçiyor. Perde, prova
    kabininin kendi hareketi; jenerik bir çapraz geçiş değil.

    Yüz köşede, küçük: kimin üstünde olduğunu söylüyor ve o kare bu vitrin
    karesini gerçekten üreten profilin fotoğrafı. Temsilî görsel yok.

    Ham karesi olmayan gelinlikte bölüm hiç çıkmıyor.
    """
    form = ROOT / "assets" / "forms" / f"{d['id']}.jpg"
    if not form.exists():
        return ""
    eq = EQUATION.get(lang, EQUATION["en"])
    model = MODEL_BY_DRESS.get(d["id"], "M1")
    return f"""<section class="tf" aria-label="{esc(eq[1])} → {esc(eq[2])}">
    <div class="tf-stage">
      <img class="tf-form" src="/assets/forms/{d['id']}.jpg" alt="{esc(eq[1])}"
        width="360" height="360">
      <img class="tf-worn" src="{img}" alt="{esc(eq[2])}" width="1000" height="1000">
      <span class="tf-veil" aria-hidden="true"></span>
    </div>
    <!-- Yüz ve ok — mağaza görselindeki düzenin aynısı.
         Kareye binen yuvarlak bir madalyon ve ondan yüze uzanan kavisli beyaz
         bir ok. Kutunun **dışında** duruyor: sol kenara taşıyor, içeride
         olsaydı `overflow:hidden` onu keserdi — o kırpma perdenin çalışması
         için gerekli. -->
    <div class="tf-tag" aria-hidden="true">
      <figure><img src="/assets/models/{model}.jpg" alt="" width="360" height="360"></figure>
      <img class="tf-arrow" src="/assets/img/arrow.png" alt="" width="145" height="263">
    </div>
    <p class="tf-cap"><span data-a>{esc(eq[1])}</span><span data-b>{esc(PROMISE.get(lang, PROMISE["en"]))}</span></p>
</section>"""


def gown_page(d, lang, path_map):
    code = LANGS[lang]
    ui = UI[lang]
    title = d["title"].get(lang) or d["title"].get("en", d["id"])
    desc = d["desc"].get(lang) or d["desc"].get("en", "")
    canonical = f"{SITE}/{code + '/' if code else ''}gowns/{path_map[lang]}/"
    alternates = [(l if l not in ("pt-BR", "zh-Hans") else l,
                   f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/{path_map[l]}/")
                  for l in LANGS]
    img = f"/assets/gowns/{d['id']}.jpg"
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
    equation = equation_block(d, lang, img)
    return f"""{head(lang, esc(title) + " — Bride Studio", esc(desc), canonical, alternates, img)}
<script type="application/ld+json">{ld}</script>
<header><a class=mark href="{home}">Bride Studio</a>
<nav><a class=back href="{SITE}/{code + '/' if code else ''}gowns/">{esc(ui[0])}</a>
{lang_picker(lang, lambda l: f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/{path_map[l]}/")}</nav></header>
<main>
  {equation}
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
{REVEAL_JS}{consent.banner(lang)}
</body></html>"""


# Katalog sözlüğü — kategori adlarının on bir dildeki karşılığı burada.
VOCAB = json.loads(pathlib.Path(
    "/Users/ibrahimgunes/Desktop/PROJECTS/bride-studio-firebase/tools/catalogue/vocab.json"
).read_text(encoding="utf-8"))

# Kaç gelinlikten azına sayfa açılmıyor.
#
# Üç gelinlikli bir sayfa hem kadına az şey gösteriyor hem aramada zayıf
# duruyor. Brocade (3) ve Organza (10) bu yüzden dışarıda.
CATEGORY_MIN = 15

# Sıfat önce mi sonra mı.
#
# "Mermaid Wedding Dresses" ve "Balık Kesim Gelinlikler" sıfatı öne alıyor;
# Latin dillerinde ise isim önce geliyor — "vestidos de novia sirena". Yanlış
# sıra hem okunmuyor hem aranmıyor.
ADJ_AFTER = {"es", "fr", "it", "pt-BR"}


def _ascii(text):
    """Adres için ASCII'ye indirger.

    `unicodedata` aksanların çoğunu ayırıyor ama Türkçe `ı` ve Almanca `ß`
    onun tablosunda yok — "balık kesim" düz normalizasyonda "bal-k-kesim"
    oluyordu, harfin yerinde tire kalıyor. O yüzden önce elle eşleniyor.
    """
    fix = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g",
                         "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
                         "ç": "c", "Ç": "c", "ß": "ss", "å": "a", "ø": "o"})
    t = unicodedata.normalize("NFKD", text.translate(fix))
    return "".join(c for c in t if not unicodedata.combining(c))


def cat_slug(field, value, lang):
    """Kategori adresi.

    Gelinlik adresleriyle çakışmıyor: onlar `d0467-` diye kimlikle başlıyor,
    kategoriler harfle.

    Latin olmayan yazılarda İngilizce karşılığa düşülüyor. Eşik iki harf:
    Japoncada "Aライン" düz süzmeden geçince geriye yalnızca "a" kalıyor ve
    tek harflik bir adres ne okunuyor ne aranıyor.
    """
    word = VOCAB[field][value].get(lang) or VOCAB[field][value]["en"]
    s = re.sub(r"[^a-z0-9]+", "-", _ascii(word).lower()).strip("-")[:40].rstrip("-")
    if len(s) > 2:
        return s
    return re.sub(r"[^a-z0-9]+", "-", _ascii(VOCAB[field][value]["en"]).lower()).strip("-")[:40].rstrip("-")


def categories(dresses):
    """Sayfası açılacak kategoriler: (alan, değer, gelinlikler).

    Aramanın gittiği yer tekil ürün değil kategori: kimse "Romantic Organza
    Ballgown Mini with an off-the-shoulder neckline" yazmıyor, "short wedding
    dress" yazıyor. Katalog zaten etiketli, o etiketlerden sayfa çıkıyor.
    """
    out = []
    for field in ("silhouette", "style", "fabric", "length"):
        seen = {}
        for d in dresses:
            v = d["meta"].get(field)
            if v:
                seen.setdefault(v, []).append(d)
        for value, group in seen.items():
            # Uzunlukta yalnızca kısa olan anlamlı: katalogun neredeyse
            # tamamı yere kadar, "floor" sayfası kataloğun kopyası olurdu.
            if field == "length" and value != "Mini":
                continue
            if len(group) < CATEGORY_MIN or value not in VOCAB.get(field, {}):
                continue
            out.append((field, value, group))
    return out


def cat_title(field, value, lang):
    """Sayfa başlığı, o dilin sırasına göre."""
    word = VOCAB[field][value].get(lang) or VOCAB[field][value]["en"]
    noun = UI[lang][0]
    if lang in ADJ_AFTER:
        return f"{noun} {word}"
    return f"{word.title()} {noun.lower()}" if lang in ("en",) else f"{word.title()} {noun}"


def category_page(field, value, group, lang, paths, all_cats):
    code = LANGS[lang]
    ui = UI[lang]
    title = cat_title(field, value, lang)
    sl = {l: cat_slug(field, value, l) for l in LANGS}
    canonical = f"{SITE}/{code + '/' if code else ''}gowns/{sl[lang]}/"
    alternates = [(l, f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/{sl[l]}/") for l in LANGS]

    cards = []
    for d in group:
        t = d["title"].get(lang) or d["title"].get("en", d["id"])
        cards.append(
            f'<a class=card href="{SITE}/{code + "/" if code else ""}gowns/{paths[d["id"]][lang]}/">'
            f'<img src="/assets/gowns/{d["id"]}.jpg" alt="{esc(t)}" loading="lazy" width="1000" height="1000">'
            f'<h2>{esc(t)}</h2></a>')

    # Kardeş kategoriler — Google'ın sayfaları bulmasının yolu ve kadının
    # aradığını bulamadığında gideceği yer.
    sib = []
    for f2, v2, g2 in all_cats:
        if (f2, v2) == (field, value):
            continue
        s2 = cat_slug(f2, v2, lang)
        sib.append(f'<a href="{SITE}/{code + "/" if code else ""}gowns/{s2}/">'
                   f'{esc(cat_title(f2, v2, lang))}</a>')

    desc = f"{len(group)} · {title}"
    return f"""{head(lang, esc(title) + " — Bride Studio", esc(desc), canonical, alternates, f"/assets/gowns/{group[0]['id']}.jpg")}
<header><a class=mark href="{SITE}/{code + '/' if code else ''}">Bride Studio</a>
<nav>{lang_picker(lang, lambda l: f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/{sl[l]}/")}</nav></header>
<main class=grid-wrap>
  <h1 class=page-title>{esc(title)}</h1>
  <p class=cat-count>{len(group)}</p>
  <div class=grid>{''.join(cards)}</div>
  <nav class=cat-nav>{''.join(sib)}</nav>
  <p><a href="{SITE}/{code + '/' if code else ''}gowns/">{esc(ui[7])}</a></p>
</main>
<footer><a class=badge href="{APPSTORE}"><img src="/assets/appstore-badge.svg" alt="Download on the App Store" height="46"></a></footer>
{consent.banner(lang)}
</body></html>"""


def index_page(dresses, lang, paths, cats=()):
    code = LANGS[lang]
    ui = UI[lang]
    canonical = f"{SITE}/{code + '/' if code else ''}gowns/"
    alternates = [(l, f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/") for l in LANGS]
    cards = []
    for d in dresses:
        t = d["title"].get(lang) or d["title"].get("en", d["id"])
        cards.append(
            f'<a class=card href="{SITE}/{code + "/" if code else ""}gowns/{paths[d["id"]][lang]}/">'
            f'<img src="/assets/gowns/{d["id"]}.jpg" alt="{esc(t)}" loading="lazy" width="1000" height="1000">'
            f'<h2>{esc(t)}</h2></a>')
    # Kategori bağlantıları galerinin başında.
    #
    # Sitemap onları listeliyor ama Google bir sayfayı yalnızca listede
    # gördüğü için değerli saymıyor; ona giden bir bağlantı da olmalı. Bu
    # aynı zamanda kadının aradığı kesimi bulmasının yolu.
    catlinks = []
    for f2, v2, g2 in cats:
        s2 = cat_slug(f2, v2, lang)
        catlinks.append(f'<a href="{SITE}/{code + "/" if code else ""}gowns/{s2}/">'
                        f'{esc(cat_title(f2, v2, lang))}</a>')

    return f"""{head(lang, esc(ui[0]) + " — Bride Studio", esc(ui[0]), canonical, alternates, f"/assets/gowns/{dresses[0]['id']}.jpg")}
<header><a class=mark href="{SITE}/{code + '/' if code else ''}">Bride Studio</a>
<nav>{lang_picker(lang, lambda l: f"{SITE}/{LANGS[l] + '/' if LANGS[l] else ''}gowns/")}</nav></header>
<main class=grid-wrap>
  <h1 class=page-title>{esc(ui[0])}</h1>
  <nav class=cat-nav>{''.join(catlinks)}</nav>
  <div class=grid>{''.join(cards)}</div>
</main>
<footer><a class=badge href="{APPSTORE}"><img src="/assets/appstore-badge.svg" alt="Download on the App Store" height="46"></a>
<span class=social><a href="https://www.instagram.com/bridestudioapp" rel="me">Instagram</a>
<a href="https://www.tiktok.com/@bridestudioapp" rel="me">TikTok</a>
<a href="https://tr.pinterest.com/bridestudioai/" rel="me">Pinterest</a></span></footer>
{consent.banner(lang)}
</body></html>"""


CSS = """.cat-nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 30px}
.cat-nav a{font-size:13px;padding:7px 14px;border:1px solid var(--hair);
  border-radius:20px;color:var(--taupe);text-decoration:none;background:#fff}
.cat-nav a:hover{color:var(--ink);border-color:var(--gold)}
.cat-count{color:var(--taupe);font-size:14px;margin:-14px 0 24px}
/* Gelinlik sayfaları — ana sayfayla aynı dil, ayrı dosyada.
   Bin altı yüz sayfa aynı stili taşıyacak; satır içine gömmek her sayfayı
   şişirir, ayrı dosya bir kez indirilip önbelleğe giriyor. */
/* Logonun yazısı, ana sayfadakiyle aynı.
   Gelinlik sayfaları New York serif kullanıyordu ve aynı siteye ait iki sayfa
   iki farklı marka gibi görünüyordu — Pinterest'ten gelen ziyaretçi doğrudan
   buraya düşüyor, yani gördüğü ilk logo bu. `swap`, yazı inene kadar metnin
   görünmesini sağlıyor. */
@font-face{font-family:"Million Astteroids";
  src:url(/assets/fonts/MillionAstteroids-R9njo.ttf) format("truetype");
  font-weight:400;font-display:swap}
:root{--cream:#FAF7F4;--ink:#3C3732;--taupe:#A58E7C;--gold:#BD9973;--dark:#14100E;--hair:rgba(165,142,124,.22)}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--ink);font:400 17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
h1,h2{font-family:"New York",ui-serif,Georgia,serif;font-weight:400;line-height:1.1;letter-spacing:-.015em;margin:0}
a{color:inherit;text-decoration:none}
img{display:block;max-width:100%;height:auto}
header{display:flex;justify-content:space-between;align-items:center;max-width:1180px;margin:0 auto;padding:22px 30px;border-bottom:1px solid var(--hair)}
.mark{font-family:"Million Astteroids","New York",ui-serif,Georgia,serif;font-size:30px;line-height:1;padding-top:4px}
.back{font-size:14px;color:var(--taupe)}

/* ── Dönüşüm ──────────────────────────────────────────────────────────────
   Gelinlik terzi kalıbında duruyor, bir perde geçiyor, kadının üstünde
   kalıyor. Prova kabininin kendi hareketi.

   İki kare aynı kutuda üst üste; üstteki `clip-path` ile soldan açılıyor.
   Opaklıkla karıştırmak yerine kırpmak, iki fotoğrafın bir an bulanık bir
   ortalamaya dönüşmesini engelliyor — perde nettir, çapraz geçiş değildir.

   Zemin koyu: anlatılan an bir prova kabini, ve beyaz bir gelinlik ancak
   koyunun yanında beyaz görünüyor. */
/* Solda dönüşüm, sağda gelinliğin künyesi — yan yana.
   Alt alta dururken sayfa iki ekran boyu uzuyordu ve okunacak şeye ulaşmak
   için kaydırmak gerekiyordu. Yan yana, ikisi de ilk bakışta görünüyor. */
.tf{color:#fff;margin:0;position:relative;display:flex;flex-direction:column}
.tf-stage{position:relative;width:100%;flex:1;min-height:clamp(340px,46vw,620px);
  border-radius:18px;overflow:hidden;background:#241d19}
.tf-stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}

/* Kadın, perde geçtikçe açılıyor. Başlangıçta hiç görünmüyor. */
.tf-worn{clip-path:inset(0 100% 0 0)}

/* Perdenin kendisi: kenarında altın bir çizgi olan dar bir ışık bandı.
   Görünürlüğü perdeyle birlikte gelip gidiyor, yoksa duran bir çizgi kalıyor. */
.tf-veil{position:absolute;top:0;bottom:0;left:0;width:22%;opacity:0;pointer-events:none;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.10) 55%,rgba(189,153,115,.85) 99%)}

/* Yüz ve ok — mağaza görselindeki düzenin aynısı.
   Yuvarlak madalyon karenin sol kenarına biniyor, sağında kadının yüzüne
   bakan kavisli beyaz bir ok var.

   İkisi yan yana akıyor, mutlak konumlandırmayla değil: ok bir denemede
   madalyonun altına düşüp beyaz bir halka gibi durdu, çünkü yüzdelik `bottom`
   değeri kutunun kendi yüksekliğine göre hesaplanıyordu. Sıralı düzende yer
   tahmine kalmıyor. */
.tf-tag{position:absolute;left:5%;top:calc(34% - 40px);z-index:3;pointer-events:none;
  display:flex;align-items:flex-start;gap:clamp(6px,1vw,12px);
  opacity:0;transform:translate(-10px,6px) scale(.94)}
/* Madalyon büyütüldü (62-92 → 84-116, 2026-08-20). Telefonda karenin beşte
   biri kadardı ve sayfanın bütün hikâyesi o: ziyaretçi Pinterest'ten geliyor ve
   ilk gördüğü şey stok gibi duran bir gelin fotoğrafı. Onu stoktan ayıran tek
   şey madalyon ve ok; küçük kalınca hikâye anlatılmıyor, süs gibi duruyor.
   Daha büyüğü gelinlikle yarışmaya başlar, ve satılan şey gelinlik. */
.tf-tag figure{margin:0;width:clamp(84px,9vw,116px);flex:0 0 auto;
  border-radius:50%;overflow:hidden;border:4px solid #fff;
  box-shadow:0 10px 30px rgba(20,16,14,.42);line-height:0}
/* Yalnızca madalyondaki yüz. Eskiden `.tf-tag img` idi ve kutudaki her
   görseli yakalıyordu — ok da kare bir kutuya sıkıştırılıp kırpılıyordu, ve
   `.tf-arrow` sınıfı bunu geri alamıyordu çünkü sınıf+eleman seçicisi daha
   güçlü. Kapsamı daraltmak, özgüllük yarışını ortadan kaldırıyor. */
.tf-tag figure img{position:static;width:100%;aspect-ratio:1;object-fit:cover;display:block}
/* Ok sağa doğru yatırıldı: çizim dikeye yakın çıkıyor ve madalyonun hemen
   üstünü işaret ediyordu, oysa kadın sağda. Dönme ekseni sol alt köşe, yani
   ok madalyondan çıkmaya devam ediyor, yalnızca ucu sağa gidiyor. */
.tf-arrow{width:clamp(28px,3.3vw,42px);height:auto;margin-top:-64px;
  border:0;border-radius:0;box-shadow:none;
  transform:rotate(24deg);transform-origin:bottom left;
  filter:drop-shadow(0 2px 6px rgba(20,16,14,.55))}

/* İki hâl üst üste duruyor ve ızgara ikisinin de yerini ayırıyor. Eskiden
   mutlak konum ve `height:1.2em` vardı — tek kelime taşıdığı sürece sorun
   değildi, ama ikinci hâl artık bir cümle: sabit yükseklik onu kırpardı,
   mutlak konum da satır kaydırmayı bozardı. */
.tf-cap{margin:14px 0 0;display:grid}
.tf-cap span{grid-area:1/1}
.tf-cap [data-a]{font-size:11.5px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--taupe);align-self:start}
/* Düz gövde yazısıydı ve sayfanın geri kalanının yanında sönük duruyordu.
   Serif, italik ve altın: başlıkla aynı aileden, ama başlığı bastırmayacak
   incelikte. */
.tf-cap [data-b]{font-family:"New York",ui-serif,Georgia,serif;font-style:italic;
  font-size:clamp(15px,1.45vw,18px);line-height:1.45;letter-spacing:.005em;
  color:var(--gold);opacity:0}

/* Gösteri, bir kez. `.on` geldiğinde başlıyor — sayfa açılır açılmaz değil,
   bölüm ekrana girince: üstte olsa bile kadın oraya bakıyor olmayabilir. */
.tf.on .tf-worn{animation:tf-open 1.5s cubic-bezier(.62,.02,.24,1) .35s forwards}
.tf.on .tf-veil{animation:tf-sweep 1.5s cubic-bezier(.62,.02,.24,1) .35s forwards}
.tf.on .tf-tag{animation:tf-tag-in .65s cubic-bezier(.16,.86,.26,1) 1.5s forwards}
.tf.on .tf-cap [data-a]{animation:tf-out .4s ease 1.1s forwards}
.tf.on .tf-cap [data-b]{animation:tf-in .5s ease 1.35s forwards}

@keyframes tf-open{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes tf-sweep{
  0%{left:-22%;opacity:0}
  8%{opacity:1}
  92%{opacity:1}
  100%{left:100%;opacity:0}}
@keyframes tf-tag-in{to{opacity:1;transform:none}}
@keyframes tf-in{to{opacity:1}}
@keyframes tf-out{to{opacity:0}}

/* Hareketi kapatmış olana bitmiş hâli: kadın gelinliğin içinde, yüz köşede. */
@media(prefers-reduced-motion:reduce){
  .tf-worn{clip-path:none}
  .tf-tag{opacity:1;transform:none}
  .tf-veil{display:none}
  .tf-cap [data-a]{opacity:0}
  .tf-cap [data-b]{opacity:1}
}

/* İki sütun: solda dönüşüm, sağda okunacaklar.
   Büyük vitrin karesi buradan kalktı — aynı görsel hem dönüşümde hem burada
   duruyordu. */
main{max-width:1180px;margin:0 auto;padding:clamp(30px,4vw,60px) clamp(20px,4vw,30px);
  display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);
  gap:clamp(28px,4vw,60px);
  /* İki sütun aynı yerde bitiyor. Kare bir görsel sağdaki künye ve düğmeden
     kısa kalıyordu ve alt hizası tutmuyordu; kutu satırın boyunu alıp
     fotoğrafı ona göre kırpıyor. */
  align-items:stretch}
@media(max-width:900px){
  main{grid-template-columns:1fr;gap:26px}
  .tf-stage{border-radius:14px;min-height:0;aspect-ratio:4/5}
}
main figure{margin:0;border-radius:20px;overflow:hidden;background:#efe9e3}
.eyebrow{font:600 11px/1 sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--taupe);margin:0 0 14px}
/* Sağ sütun satırın boyunu dolduruyor ve düğme dibe iniyor.
   `align-items:stretch` sütunu zaten uzatıyordu ama içerik tepede kalıp
   altında boşluk bırakıyordu: soldaki alt yazı düğmenin bittiği yerin
   aşağısına sarkıyor, iki sütun aynı yerde bitmiyordu. Kullanıcı bunu bir
   kez söylemişti, kırılan yer alt yazı eklenince burasıydı. */
.info{display:flex;flex-direction:column}
.info .btn{margin-top:auto}
.info h1{font-size:clamp(28px,3.6vw,44px)}
.rule{width:46px;height:1px;background:var(--gold);opacity:.6;margin:20px 0}
.lead{color:#5f584f;margin:0 0 28px}
.spec{margin:0 0 32px;border-top:1px solid var(--hair)}
.spec .r{display:flex;justify-content:space-between;gap:20px;padding:12px 0;border-bottom:1px solid var(--hair)}
.spec dt{font:600 11px/1.6 sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--taupe);margin:0}
.spec dd{margin:0;font-family:"New York",ui-serif,Georgia,serif;font-size:17px}
.badge{display:inline-block;line-height:0}
.badge img{height:46px;width:auto}
/* Tek eylem.
   Siyah bir kapsüldü ve krem bir sayfada sert duruyordu — sayfadaki hiçbir
   şey o kadar koyu değil. Altın, markanın kendi vurgusu ve zaten künye
   çizgilerinde, yaka adında, dönüşümün çerçevesinde var; düğme onların dolu
   hâli oluyor.

   Sütunun tamamını kaplıyor: künye satırları kenardan kenara uzanıyordu,
   düğme onların altında yarım kalıyordu ve hizasız görünüyordu. Telefonda da
   parmak için doğru büyüklük. */
.btn{position:relative;display:block;width:100%;text-align:center;
  padding:20px 32px;border-radius:999px;overflow:hidden;
  background:var(--gold);color:#fff;
  font:400 19px/1 "New York",ui-serif,Georgia,serif;letter-spacing:.01em;
  box-shadow:0 10px 26px rgba(189,153,115,.32);
  transition:background .25s ease,box-shadow .25s ease,transform .25s ease}
.btn::after{content:"";position:absolute;top:0;bottom:0;left:-60%;width:45%;
  background:linear-gradient(100deg,transparent,rgba(255,255,255,.30),transparent);
  transform:skewX(-18deg);animation:btn-shine 6s ease-in-out infinite}
@keyframes btn-shine{0%{left:-60%}18%{left:130%}100%{left:130%}}
.btn:hover{background:var(--dark);box-shadow:0 12px 30px rgba(20,16,14,.28);transform:translateY(-1px)}
.btn:focus-visible{outline:2px solid var(--dark);outline-offset:3px}
@media(prefers-reduced-motion:reduce){.btn::after{display:none}.btn{transition:none}}
@media(prefers-reduced-motion:reduce){
  .btn,.btn::after{animation:none}
  .btn::after{display:none}
}
header nav{display:flex;align-items:center;gap:18px}
.lang{position:relative;font-size:13px}
.lang summary{list-style:none;cursor:pointer;color:var(--taupe);padding:6px 10px;border:1px solid var(--hair);border-radius:999px}
.lang summary::-webkit-details-marker{display:none}
.lang summary::after{content:" ▾";opacity:.6}
.lang[open] summary{color:var(--ink)}
.lang-menu{position:absolute;right:0;top:calc(100% + 8px);z-index:20;background:#fff;
  border:1px solid var(--hair);border-radius:14px;padding:8px;min-width:170px;
  box-shadow:0 18px 40px rgba(60,55,50,.14);display:grid;gap:2px}
.lang-menu a{display:block;padding:8px 12px;border-radius:9px;font-size:14px;color:var(--ink)}
.lang-menu a:hover{background:var(--cream)}
.lang-menu a.on{color:var(--gold)}
.social{display:flex;gap:18px}
.social a{font:400 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--taupe)}
.social a:hover{color:var(--gold)}
footer{max-width:1180px;margin:0 auto;padding:40px 30px 70px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;color:var(--taupe);font-size:13px}
.grid-wrap{display:block}
.page-title{font-size:clamp(30px,4vw,52px);margin-bottom:34px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.grid .card img{border-radius:14px;background:#efe9e3}
.grid .card h2{font-size:15px;margin-top:12px}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
"""


def sweep(dresses, paths, apply):
    """Katalogdan çıkmış gelinliklerin sayfalarını siler.

    Betik her koşuda sayfaları üzerine yazıyor ama silinmiş bir gelinliğin
    klasörüne dokunmuyordu. Katalogdan çıkan gelinlik sitemap'ten düşüyor,
    galeriden düşüyor — ve adresi açık kalmaya devam ediyor, Google'ın
    indeksinde de öyle. 2026-08-30'da katalogdan dört gelinlik çıktı ve
    sayfaları yerinde duruyordu.

    Karşılaştırma dil dil yapılıyor, çünkü slug başlıktan üretiliyor ve
    başlık her dilde başka: bir gelinliğin adı değişirse eski slug da bu
    yolla temizleniyor.
    """
    gone = []
    for lang, code in LANGS.items():
        base = (ROOT / code if code else ROOT) / "gowns"
        if not base.is_dir():
            continue
        keep = {paths[d["id"]][lang] for d in dresses}
        # Kategori klasörleri de korunuyor — gelinlik slug'ı değiller.
        keep |= {cat_slug(f, v, lang) for f, v, _ in categories(dresses)}
        gone += [c for c in base.iterdir() if c.is_dir() and c.name not in keep]

    live = {d["id"].lower() for d in dresses}
    for kind in ("gowns", "forms"):
        art = ROOT / "assets" / kind
        if art.is_dir():
            gone += [f for f in art.iterdir() if f.stem.lower() not in live]

    if not gone:
        return
    print(f"katalogda olmayan {len(gone)} klasör/dosya siliniyor")
    for g in sorted(gone)[:6]:
        print("  ", g.relative_to(ROOT))
    if len(gone) > 6:
        print(f"   … ve {len(gone) - 6} tane daha")
    if not apply:
        return
    for g in gone:
        shutil.rmtree(g) if g.is_dir() else g.unlink()


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
    sweep(dresses, paths, a.apply)
    if not a.apply:
        d = dresses[0]
        print("örnek adres:", f"/gowns/{paths[d['id']]['en']}/")
        print("kuru çalışma — yazmak için --apply")
        return

    cats = categories(dresses)
    print(f"kategori sayfası: {len(cats)} × {len(LANGS)} dil")
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
        (gi / "index.html").write_text(index_page(dresses, lang, paths, cats))
        urls.append(f"{SITE}/{code + '/' if code else ''}gowns/")

        for field, value, group in cats:
            cs = cat_slug(field, value, lang)
            cp = gi / cs
            cp.mkdir(parents=True, exist_ok=True)
            (cp / "index.html").write_text(
                category_page(field, value, group, lang, paths, cats))
            urls.append(f"{SITE}/{code + '/' if code else ''}gowns/{cs}/")

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
