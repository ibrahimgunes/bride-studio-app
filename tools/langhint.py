"""Sayfanın üstündeki dil şeridi.

Pinterest'ten gelen herkes İngilizce adrese düşüyor — pinler tek dilde
paylaşılıyor. Almanya'dan gelen bir gelin sitenin Almancası olduğunu hiç
görmüyor, çünkü dil seçici menünün içinde ve kimse aramıyor.

Şerit, tarayıcı dili sayfanınkinden farklıysa çıkıyor ve o dile giden
bağlantıyı veriyor. Otomatik yönlendirme değil: Google dile göre yönlendirmeyi
önermiyor ve sitenin tamamı indekslenmek için var — 1937 sayfayı, ziyaretçiyi
iki tık erken taşımak için riske atmıyoruz. Seçim kullanıcıda kalıyor.

**Adres uydurulmuyor.** Hedef, sayfanın kendi `hreflang` etiketlerinden
okunuyor: gelinlik adresleri her dilde farklı (`d0001-minimalist-crepe-...`
karşısında `d0001-brautkleid-in-gerade-...`), yani kalıpla üretmek 404 demekti.
Etiketler zaten her sayfada duruyor.

Şerit bir kez kapatılırsa bir daha çıkmıyor; tercih `localStorage`da.
"""

# Şeridin metni, her dilin kendi dilinde — çünkü okuyacak olan o dili
# konuşuyor. `{lang}` dilin kendi adıyla doluyor.
HINT = {
    "en": "View this page in English",
    "tr": "Bu sayfayı Türkçe görüntüle",
    "de": "Diese Seite auf Deutsch ansehen",
    "es": "Ver esta página en español",
    "fr": "Voir cette page en français",
    "it": "Vedi questa pagina in italiano",
    "pt-BR": "Ver esta página em português",
    "ja": "このページを日本語で見る",
    "ko": "이 페이지를 한국어로 보기",
    "zh-Hans": "用简体中文查看此页",
    "hi": "इस पेज को हिन्दी में देखें",
}

CLOSE = {
    "en": "Dismiss", "tr": "Kapat", "de": "Schließen", "es": "Cerrar",
    "fr": "Fermer", "it": "Chiudi", "pt-BR": "Fechar", "ja": "閉じる",
    "ko": "닫기", "zh-Hans": "关闭", "hi": "बंद करें",
}

CREAM, INK, MINK, GOLD = "#FAF7F4", "#3C3732", "#A58E7C", "#BD9973"


def strip(lang):
    """`<body>`in hemen içine. Gerekmiyorsa hiç görünmüyor."""
    import json
    hints = json.dumps(HINT, ensure_ascii=False)
    closes = json.dumps(CLOSE, ensure_ascii=False)
    return f"""<div id=bs-lang hidden><a href="#"></a><button type=button aria-label="close"></button></div>
<style>
#bs-lang{{display:flex;gap:14px;align-items:center;justify-content:center;
 background:{CREAM};border-bottom:1px solid rgba(60,55,50,.12);
 padding:9px 16px;font-size:14px;color:{INK};position:relative;z-index:80}}
#bs-lang[hidden]{{display:none}}
#bs-lang a{{color:{INK};text-decoration:none;border-bottom:1px solid {GOLD};padding-bottom:1px}}
#bs-lang a:hover{{color:{GOLD}}}
#bs-lang button{{font:inherit;cursor:pointer;background:none;border:0;color:{MINK};
 padding:2px 6px;line-height:1}}
#bs-lang button:focus-visible,#bs-lang a:focus-visible{{outline:2px solid {GOLD};outline-offset:2px}}
</style>
<script>
(function(){{
  var HINT={hints},CLOSE={closes},here="{lang}";
  try{{if(localStorage.getItem('bs-lang')==='off')return;}}catch(e){{}}

  // Tarayıcının istediği diller, sırayla. Ülke değil dil bakılıyor: Almanya'da
  // yaşayan herkes Almanca okumuyor, ama telefonunu Almanca kullanan okuyor.
  var want=(navigator.languages||[navigator.language||'']).map(function(s){{
    return String(s);
  }});

  // Sayfanın kendi kardeşleri. Adresler dile göre farklı, o yüzden
  // uydurulmuyor — etiketten okunuyor.
  var alts={{}};
  Array.prototype.forEach.call(
    document.querySelectorAll('link[rel=alternate][hreflang]'),function(l){{
      alts[l.getAttribute('hreflang')]=l.getAttribute('href');
  }});

  // İlk eşleşen dil. `de-AT` da `de`ye düşüyor; `zh` basitleştirilmiş sayılıyor.
  var pick=null;
  for(var i=0;i<want.length&&!pick;i++){{
    var w=want[i],base=w.split('-')[0].toLowerCase();
    var cand=[w,base==='zh'?'zh-Hans':null,base==='pt'?'pt-BR':null,base];
    for(var j=0;j<cand.length;j++){{
      var c=cand[j];
      if(c&&alts[c]&&HINT[c]){{pick=c;break;}}
    }}
  }}
  if(!pick||pick===here)return;

  var box=document.getElementById('bs-lang'),a=box.querySelector('a'),b=box.querySelector('button');
  a.href=alts[pick];a.textContent=HINT[pick];a.setAttribute('lang',pick);
  b.textContent=CLOSE[pick]||CLOSE.en;
  b.addEventListener('click',function(){{
    try{{localStorage.setItem('bs-lang','off');}}catch(e){{}}
    box.hidden=true;
  }});
  box.hidden=false;
}})();
</script>"""
