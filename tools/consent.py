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
gtag('consent','default',{{
 'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied',
 'analytics_storage':'granted'}});
gtag('js',new Date());gtag('config','{ga}');

// App Store'a tıklama.
//
// Sayfanın tek işi kadını mağazaya götürmek ve o adım bugüne kadar hiç
// ölçülmüyordu: kaç kişinin sayfaya geldiğini biliyorduk, kaçının çıkıp
// gittiğini bilmiyorduk. Ücretli bir denemede eksik olan tam bu sayı —
// tıklama başına maliyet ancak tıklama sayılırsa hesaplanıyor.
//
// Dinleyici belgeye bağlı, düğmelere tek tek değil: sayfada mağazaya giden
// iki bağlantı var (üstteki düğme ve alttaki rozet) ve üçüncüsü eklendiğinde
// burayı kimse hatırlamayacak.
document.addEventListener('click',function(e){{
  var a=e.target.closest&&e.target.closest('a[href*="apps.apple.com"]');
  if(!a||!window.gtag)return;
  gtag('event','store_click',{{
    page_path:location.pathname,
    // Reklam hangi kaynaktan getirdiyse o etikette duruyor; tıklamayı
    // kaynağına bağlayan şey bu.
    source:new URLSearchParams(location.search).get('utm_source')||'(none)'
  }});
}},true);
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={ga}"></script>"""


def banner(lang):
    """Çerez bandı kaldırıldı — 2026-08-24.

    Önce herkese gösteriliyordu ve onay verilene kadar ölçüm kapalıydı; doksan
    günde toplanan şey 47 oturum ve 10 kişiydi, çoğu da bağlantı denemesi.
    Sonra yalnızca AB'de gösterilecek şekilde daraltıldı. Kullanıcı ikisini de
    istemedi ve karar onun: band tamamen kalkıyor, `analytics_storage` her
    ziyaretçide baştan açık.

    Bunun bedeli AB tarafında hukuki: orada analitik çerezi onaysız
    çalıştırmak ePrivacy'ye aykırı. Karar bilinerek verildi.

    Fonksiyon duruyor ki üreticide çağrıldığı yerler bozulmasın; boş dönüyor.
    """
    return ""
