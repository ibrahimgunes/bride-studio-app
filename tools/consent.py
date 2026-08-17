"""Çerez onayı bandı ve GA4'ün ona bağlanması.

İki dosya da bunu kullanıyor: `build_gowns.py` bin dokuz yüz otuz altı gelinlik
sayfasına, `build_home.py` on bir ana sayfaya. Tek yerde durmasının sebebi,
metnin iki yerde ayrı ayrı yaşamaya başlamaması.

**Sıra önemli.** `gtag` yüklenmeden önce onay "denied" olarak ilan ediliyor
(Consent Mode v2). Böylece betik sayfayla birlikte inse de kabul edilene kadar
çerez yazmıyor, ve kabul edildiği an geçmişe dönük değil ileriye doğru
çalışmaya başlıyor. Bandı gösterip gtag'i serbest bırakmak, bandı hiç
koymamakla aynı şey olurdu.

**Ret, kabul kadar kolay.** İki düğme aynı boyutta ve aynı yerde; birini
küçültmek ya da köşeye atmak GDPR'ın açıkça saymadığı ama denetimlerde
takıldığı yer. Seçim `localStorage`da duruyor, band bir daha çıkmıyor.
"""

# Onay metinleri. Her dil kendi akışıyla yazıldı; hiçbiri İngilizceden kelime
# kelime çevrilmedi. Üçlü: cümle, kabul, ret.
CONSENT = {
    "en": ("We use cookies to see how the site is used. Nothing is stored until you agree.",
           "Accept", "Decline"),
    "tr": ("Sitenin nasıl kullanıldığını görmek için çerez kullanıyoruz. Kabul etmezsen hiçbir şey saklanmıyor.",
           "Kabul et", "İstemiyorum"),
    "de": ("Wir verwenden Cookies, um zu sehen, wie die Seite genutzt wird. Ohne Ihre Zustimmung wird nichts gespeichert.",
           "Einverstanden", "Ablehnen"),
    "es": ("Usamos cookies para ver cómo se usa el sitio. No se guarda nada hasta que aceptes.",
           "Aceptar", "Rechazar"),
    "fr": ("Nous utilisons des cookies pour comprendre l'usage du site. Rien n'est enregistré sans votre accord.",
           "Accepter", "Refuser"),
    "it": ("Usiamo i cookie per capire come viene usato il sito. Nulla viene salvato senza il tuo consenso.",
           "Accetto", "Rifiuto"),
    "pt-BR": ("Usamos cookies para entender como o site é usado. Nada é guardado até você concordar.",
              "Aceitar", "Recusar"),
    "ja": ("サイトの利用状況を把握するためにCookieを使用します。同意いただくまで何も保存されません。",
           "同意する", "同意しない"),
    "ko": ("사이트 이용 방식을 파악하기 위해 쿠키를 사용합니다. 동의하기 전까지는 아무것도 저장되지 않습니다.",
           "동의", "동의하지 않음"),
    "zh-Hans": ("我们使用 Cookie 了解网站的使用情况。在您同意之前不会保存任何内容。",
                "同意", "拒绝"),
    "hi": ("साइट कैसे इस्तेमाल होती है यह देखने के लिए हम कुकीज़ का उपयोग करते हैं। आपकी सहमति तक कुछ भी सेव नहीं होता।",
           "स्वीकार करें", "अस्वीकार करें"),
}

CREAM, INK, MINK, GOLD, DARK = "#FAF7F4", "#3C3732", "#A58E7C", "#BD9973", "#14100E"


def head_scripts(ga):
    """`</head>` içine. Onay ilanı gtag'den **önce** geliyor."""
    return f"""<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
var bsOK=null;try{{bsOK=localStorage.getItem('bs-consent');}}catch(e){{}}
gtag('consent','default',{{
 'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied',
 'analytics_storage':bsOK==='yes'?'granted':'denied','wait_for_update':500}});
gtag('js',new Date());gtag('config','{ga}');
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={ga}"></script>"""


def banner(lang):
    """`</body>` öncesine. Seçim yapılmışsa hiç görünmüyor."""
    text, yes, no = CONSENT.get(lang, CONSENT["en"])
    return f"""<div id=bs-consent hidden>
  <p>{text}</p>
  <div class=bs-consent-actions>
    <button type=button data-consent=no>{no}</button>
    <button type=button data-consent=yes>{yes}</button>
  </div>
</div>
<style>
#bs-consent{{position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;
 max-width:660px;margin:0 auto;display:flex;gap:18px;align-items:center;
 flex-wrap:wrap;justify-content:space-between;
 background:{DARK};color:{CREAM};padding:18px 20px;border-radius:14px;
 box-shadow:0 10px 40px rgba(0,0,0,.28);font-size:14px;line-height:1.45}}
#bs-consent[hidden]{{display:none}}
#bs-consent p{{margin:0;flex:1 1 300px;color:{CREAM}}}
.bs-consent-actions{{display:flex;gap:10px;flex:0 0 auto}}
#bs-consent button{{font:inherit;cursor:pointer;padding:9px 18px;border-radius:999px;
 border:1px solid {MINK};background:transparent;color:{CREAM};white-space:nowrap}}
#bs-consent button[data-consent=yes]{{background:{GOLD};border-color:{GOLD};color:{DARK}}}
#bs-consent button:focus-visible{{outline:2px solid {CREAM};outline-offset:2px}}
@media (max-width:520px){{
 #bs-consent{{flex-direction:column;align-items:stretch}}
 .bs-consent-actions{{display:grid;grid-template-columns:1fr 1fr}}
 #bs-consent button{{width:100%}}
}}
</style>
<script>
(function(){{
  var box=document.getElementById('bs-consent'),saved=null;
  try{{saved=localStorage.getItem('bs-consent');}}catch(e){{}}
  if(saved===null)box.hidden=false;
  box.addEventListener('click',function(e){{
    var pick=e.target.getAttribute&&e.target.getAttribute('data-consent');
    if(!pick)return;
    try{{localStorage.setItem('bs-consent',pick);}}catch(e){{}}
    if(window.gtag)gtag('consent','update',
      {{'analytics_storage':pick==='yes'?'granted':'denied'}});
    box.hidden=true;
  }});
}})();
</script>"""
