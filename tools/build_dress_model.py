"""Her gelinliğin vitrinini hangi mankenin ürettiğini bulur.

`build_gowns.py` gelinlik sayfasının köşesine bir madalyon koyuyor: o vitrin
karesini gerçekten üreten profilin fotoğrafı. Hangi profil olduğu bugüne kadar
`dress_model.json`da **elle** tutuluyordu — 220 kayıtlık bir dosya, katalog 296
gelinliğe çıkınca 76'sı eksik kaldı, ve eksik olan `MODEL_BY_DRESS.get(id, "M1")`
ile sessizce M1'e düşüyor. Yani sayfa, karedeki kadından başka birinin yüzünü
gösteriyor.

Eşleme tahmin edilmiyor, **dosya adından** okunuyor. `promote_results.py`
vitrini üretim zamanının damgasıyla yazıyor:

    wedding_dresses/D0394/models/model_20260830094544.webp
                                       └── 2026-08-30 09:45:44

O damga, üretimi başlatan `images` kaydının kendi zamanı. Yani kareyi hangi
işin ürettiği kesin olarak biliniyor ve o işin `profileId`si madalyonun sahibi.

    python3 tools/build_dress_model.py            # ne bulduğunu söyler
    python3 tools/build_dress_model.py --apply
"""
import json, subprocess, argparse, pathlib, re, urllib.request
from datetime import datetime, timezone

PROJECT = "bridestudio-181c6"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
# Vitrinleri üreten hesap: sahibin cihazı.
OWNER = "device-0A40DB94-9B9D-471B-8EEB-443412423F6C"
OUT = pathlib.Path(__file__).parent / "dress_model.json"

# Damga ile üretim zamanı arasında kabul edilen kayma.
#
# İkisi aynı olayı gösteriyor ama aynı saniyeyi değil: damga işin bittiği,
# `createdAt` başladığı an. Bir üretim ~95 saniye sürüyor, kuyrukta beklerse
# daha uzun. Pencere geniş tutuluyor çünkü aynı gelinliğin iki üretimi arasında
# genellikle günler var — yanlış eşleşme riski, eşleşememe riskinden küçük.
WINDOW_MINUTES = 90


def token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def get(url, tok):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        url, headers={"Authorization": f"Bearer {tok}"})).read())


def sv(f):
    return (f or {}).get("stringValue", "")


def profiles(tok):
    """Profil kimliği → görünen ad (M1 / M2 / M3)."""
    out, page = {}, None
    while True:
        u = f"{BASE}/users/{OWNER}/profiles?pageSize=300" + (f"&pageToken={page}" if page else "")
        d = get(u, tok)
        for doc in d.get("documents", []):
            name = sv(doc["fields"].get("name"))
            # "M2 Studio" → "M2"; madalyon dosyaları bu adla duruyor.
            m = re.match(r"(M\d)", name)
            if m:
                out[doc["name"].rsplit("/", 1)[-1]] = m.group(1)
        page = d.get("nextPageToken")
        if not page:
            return out


def generations(tok):
    """Sahibin bütün üretimleri: (gelinlik, zaman, profil)."""
    out, page = [], None
    while True:
        body = {"structuredQuery": {
            "from": [{"collectionId": "images"}],
            "where": {"fieldFilter": {
                "field": {"fieldPath": "userId"},
                "op": "EQUAL", "value": {"stringValue": OWNER}}},
            "limit": 3000}}
        req = urllib.request.Request(
            f"{BASE}:runQuery", method="POST", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
        for row in json.loads(urllib.request.urlopen(req).read()):
            doc = row.get("document")
            if not doc:
                continue
            f = doc["fields"]
            made = (f.get("createdAt") or {}).get("timestampValue")
            if not made:
                continue
            out.append((sv(f.get("dressId")), made, sv(f.get("profileId"))))
        return out


def dresses(tok):
    """Gelinlik kimliği → vitrin karesinin yolu."""
    out, page = {}, None
    while True:
        u = f"{BASE}/dresses?pageSize=300&mask.fieldPaths=media" + (f"&pageToken={page}" if page else "")
        d = get(u, tok)
        for doc in d.get("documents", []):
            media = doc["fields"].get("media", {}).get("mapValue", {}).get("fields", {})
            out[doc["name"].rsplit("/", 1)[-1]] = sv(media.get("modelView"))
        page = d.get("nextPageToken")
        if not page:
            return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    tok = token()
    who = profiles(tok)
    gens = generations(tok)
    cat = dresses(tok)
    print(f"profil {len(who)}, üretim {len(gens)}, gelinlik {len(cat)}")

    by_dress = {}
    for did, made, pid in gens:
        by_dress.setdefault(did, []).append((made, pid))

    found, missing, guessed = {}, [], []
    for did, path in sorted(cat.items()):
        m = re.search(r"model_(\d{14})\.", path)
        if not m:
            # Damgadan önceki adlar: `model1.webp`, `model_v20.webp`. Kareyi
            # hangi işin ürettiği okunamıyor, ama gelinliğin **tek** bir
            # üretimi varsa başka aday yok — o kare ondan gelmiş olmak
            # zorunda. Birden fazlaysa dosyadaki elle kayda bırakılıyor.
            runs = {p for _, p in by_dress.get(did, []) if p in who}
            if len(runs) == 1:
                found[did] = who[runs.pop()]
                guessed.append(did)
            else:
                missing.append(did)
            continue
        stamp = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        best, gap = None, None
        for made, pid in by_dress.get(did, []):
            d = abs((datetime.fromisoformat(made.replace("Z", "+00:00")) - stamp).total_seconds())
            if gap is None or d < gap:
                best, gap = pid, d
        if best and gap <= WINDOW_MINUTES * 60 and best in who:
            found[did] = who[best]
        else:
            missing.append(did)

    import collections
    print("eşleşen:", len(found), dict(collections.Counter(found.values())),
          f"(tek üretimden çıkarılan: {len(guessed)})" if guessed else "")
    if missing:
        print(f"eşleşmeyen {len(missing)}:", missing[:10],
              "…" if len(missing) > 10 else "")

    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    changed = [d for d in found if old.get(d) and old[d] != found[d]]
    if changed:
        # Türetme kazanıyor. Doğrulandı: D0204 bugün M2 ile yeniden üretildi,
        # damga M2 diyor, elle tutulan dosya hâlâ M1 diyordu — yani dosya
        # mankeni değişen her gelinlikte bayatlıyor.
        print(f"dosyadaki kayıt düzeltiliyor, {len(changed)} gelinlik:",
              [(d, old[d], "→", found[d]) for d in changed[:8]])

    # Damgasız vitrinler — `model1.webp` gibi, sürümlü ada geçmeden önce
    # basılmış olanlar. Hangi üretimden geldikleri okunamıyor, o yüzden elle
    # tutulan kayıt tek kaynak ve korunuyor.
    kept = {d: m for d, m in old.items() if d not in found and d in cat}
    if kept:
        print(f"damgasız olduğu için dosyadan korunan: {len(kept)}")
    dropped = [d for d in old if d not in cat]
    if dropped:
        print(f"katalogda olmayan {len(dropped)} kayıt düşüyor")

    out = {**kept, **found}
    blank = [d for d in cat if d not in out]
    if blank:
        print(f"UYARI — madalyonu M1'e düşecek {len(blank)} gelinlik:", blank[:10])

    if not a.apply:
        print("kuru çalışma — yazmak için --apply")
        return
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"{OUT.name}: {len(out)} kayıt yazıldı")


if __name__ == "__main__":
    main()
