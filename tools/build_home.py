"""Ana sayfayı on bir dilde üretir.

`index.html` İngilizce aslı ve aynı zamanda şablon: tasarım orada yaşıyor,
burada yalnızca sözler değişiyor. Ayrı bir şablon dosyası tutmadık çünkü iki
kopya tutmak, ikisinin ayrışması demek — tasarımda bir şey değiştirdiğimizde
biri güncellenip öteki unutuluyor.

Çeviriler elle yazıldı, makineyle değil: sayfanın tamamı beş cümle ve o beş
cümle ürünün ne olduğunu anlatıyor. `[[reference-catalogue-copy]]`daki gelinlik
metinleriyle aynı ağızdan konuşuyorlar.

    python3 tools/build_home.py            # ne yapacağını söyler
    python3 tools/build_home.py --apply
"""
import argparse, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import consent
import langhint

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://bridestudio.app"

# Adres yolundaki kod. İngilizce kökte, yani yolu yok.
LANGS = {"en": "", "tr": "tr", "de": "de", "es": "es", "fr": "fr", "it": "it",
         "pt-BR": "pt", "ja": "ja", "ko": "ko", "zh-Hans": "zh", "hi": "hi",
         "pl": "pl", "cs": "cs", "uk": "uk", "ru": "ru"}

LANG_NAMES = {"en": "English", "tr": "Türkçe", "de": "Deutsch", "es": "Español",
              "fr": "Français", "it": "Italiano", "pt-BR": "Português",
              "ja": "日本語", "ko": "한국어", "zh-Hans": "简体中文", "hi": "हिन्दी",
              "pl": "Polski", "cs": "Čeština", "uk": "Українська", "ru": "Русский"}

# İngilizce asıl → on dildeki karşılığı.
#
# Anahtar olarak İngilizce cümlenin kendisi kullanılıyor: sayfada ne yazıyorsa
# burada da o yazıyor, yani bir cümle değiştiğinde eşleşme bozuluyor ve betik
# bunu söylüyor. Kısa kodlar (`hero_title` gibi) sessizce eskiyor.
COPY = {
"Bride Studio — See Yourself in the Gown Before You Try It On": {
 "tr":"Bride Studio — Gelinliği Denemeden Kendini İçinde Gör",
 "de":"Bride Studio — Sieh dich im Kleid, bevor du es anprobierst",
 "es":"Bride Studio — Mírate con el vestido antes de probártelo",
 "fr":"Bride Studio — Voyez-vous dans la robe avant de l'essayer",
 "it":"Bride Studio — Guardati nell'abito prima di provarlo",
 "pt-BR":"Bride Studio — Veja-se no vestido antes de experimentar",
 "ja":"Bride Studio — 試着する前に、ドレス姿の自分を見る",
 "ko":"Bride Studio — 입어보기 전에 드레스 입은 나를 보세요",
 "zh-Hans":"Bride Studio — 试穿之前，先看见穿上婚纱的自己",
 "hi":"Bride Studio — पहनने से पहले खुद को गाउन में देखें",
 "pl":"Bride Studio — Zobacz siebie w sukni, zanim ją przymierzysz","cs":"Bride Studio — Uvidíte se v šatech dřív, než je zkusíte","uk":"Bride Studio — Побачте себе в сукні ще до примірки","ru":"Bride Studio — Увидьте себя в платье до примерки"},

"Upload one photo and see yourself wearing the wedding dress — your face, your skin tone, your figure. Over 300 gowns to try on from your sofa.": {
 "tr":"Tek bir fotoğraf yükle, gelinliği üzerinde gör — kendi yüzün, kendi teninin rengi, kendi bedenin. Koltuğundan denenecek 300'den fazla gelinlik.",
 "de":"Lade ein Foto hoch und sieh dich im Brautkleid — dein Gesicht, dein Hautton, deine Figur. Über 300 Kleider, vom Sofa aus anprobiert.",
 "es":"Sube una foto y mírate con el vestido de novia — tu cara, tu tono de piel, tu figura. Más de 300 vestidos para probarte desde el sofá.",
 "fr":"Envoyez une photo et voyez-vous en robe de mariée — votre visage, votre teint, votre silhouette. Plus de 300 robes à essayer depuis votre canapé.",
 "it":"Carica una foto e guardati nell'abito da sposa — il tuo viso, il tuo incarnato, la tua figura. Oltre 300 abiti da provare dal divano.",
 "pt-BR":"Envie uma foto e veja-se no vestido de noiva — seu rosto, seu tom de pele, seu corpo. Mais de 300 vestidos para experimentar do sofá.",
 "ja":"写真を1枚アップロードするだけで、ウェディングドレス姿の自分が見られます。あなたの顔、あなたの肌、あなたの体で。300着以上をソファから試着。",
 "ko":"사진 한 장이면 웨딩드레스를 입은 내 모습을 볼 수 있습니다. 내 얼굴, 내 피부톤, 내 체형 그대로. 300벌 넘는 드레스를 소파에서.",
 "zh-Hans":"上传一张照片，看见穿上婚纱的自己——你的脸、你的肤色、你的身形。300 多款婚纱，在沙发上试穿。",
 "hi":"एक फ़ोटो अपलोड करें और खुद को वेडिंग ड्रेस में देखें — आपका चेहरा, आपकी रंगत, आपकी काया। सोफ़े से ही 300 से ज़्यादा गाउन आज़माएँ।",
 "pl":"Wgraj jedno zdjęcie i zobacz siebie w sukni ślubnej — swoją twarz, swój odcień skóry, swoją sylwetkę. Ponad 300 sukni do przymierzenia z kanapy.","cs":"Nahrajte jednu fotku a uvidíte se ve svatebních šatech — svou tvář, svůj odstín pleti, svou postavu. Přes 300 šatů na vyzkoušení z gauče.","uk":"Завантажте одне фото й побачте себе у весільній сукні — своє обличчя, свій відтінок шкіри, свою фігуру. Понад 300 суконь, які можна приміряти з дивана.","ru":"Загрузите одно фото и увидьте себя в свадебном платье — своё лицо, свой оттенок кожи, свою фигуру. Больше 300 платьев, которые можно примерить с дивана."},

"Wedding dress try-on": {
 "tr":"Gelinlik provası","de":"Brautkleid anprobieren","es":"Prueba de vestido de novia",
 "fr":"Essayage de robe de mariée","it":"Prova dell'abito da sposa","pt-BR":"Prova de vestido de noiva",
 "ja":"ウェディングドレス試着","ko":"웨딩드레스 착용","zh-Hans":"婚纱试穿","hi":"वेडिंग ड्रेस ट्राय-ऑन",
 "pl":"Przymiarka sukni ślubnej","cs":"Zkouška svatebních šatů","uk":"Примірка весільної сукні","ru":"Примерка свадебного платья"},

"See yourself in the gown.": {
 "tr":"Kendini gelinlikte gör.","de":"Sieh dich im Kleid.","es":"Mírate con el vestido.",
 "fr":"Voyez-vous dans la robe.","it":"Guardati nell'abito.","pt-BR":"Veja-se no vestido.",
 "ja":"ドレス姿の自分を見る。","ko":"드레스 입은 나를 보세요.","zh-Hans":"看见穿上婚纱的自己。",
 "hi":"खुद को गाउन में देखें।",
 "pl":"Zobacz siebie w sukni.","cs":"Uvidíte se v šatech.","uk":"Побачте себе в сукні.","ru":"Увидьте себя в платье."},

"Upload one photo. Bride Studio shows you wearing the dress — your face,\n        your skin tone, your figure. Not a model in a catalogue. You.": {
 "tr":"Tek bir fotoğraf yükle. Bride Studio o gelinliği senin üzerinde gösteriyor — kendi yüzün, kendi tenin, kendi bedeninle. Katalogdaki manken değil. Sen.",
 "de":"Lade ein Foto hoch. Bride Studio zeigt dich im Kleid — dein Gesicht, dein Hautton, deine Figur. Kein Model aus dem Katalog. Du.",
 "es":"Sube una foto. Bride Studio te muestra con el vestido — tu cara, tu tono de piel, tu figura. No una modelo del catálogo. Tú.",
 "fr":"Envoyez une photo. Bride Studio vous montre dans la robe — votre visage, votre teint, votre silhouette. Pas un mannequin de catalogue. Vous.",
 "it":"Carica una foto. Bride Studio ti mostra nell'abito — il tuo viso, il tuo incarnato, la tua figura. Non una modella del catalogo. Tu.",
 "pt-BR":"Envie uma foto. O Bride Studio mostra você no vestido — seu rosto, seu tom de pele, seu corpo. Não uma modelo do catálogo. Você.",
 "ja":"写真を1枚アップロード。Bride Studio があなたをドレス姿で見せます。あなたの顔、あなたの肌、あなたの体で。カタログのモデルではなく、あなた。",
 "ko":"사진 한 장을 올리면 Bride Studio가 드레스를 입은 당신을 보여줍니다. 내 얼굴, 내 피부톤, 내 체형 그대로. 카탈로그 모델이 아니라 당신.",
 "zh-Hans":"上传一张照片，Bride Studio 让你看见自己穿上婚纱——你的脸、你的肤色、你的身形。不是目录里的模特，是你。",
 "hi":"एक फ़ोटो अपलोड करें। Bride Studio आपको उस ड्रेस में दिखाता है — आपका चेहरा, आपकी रंगत, आपकी काया। कैटलॉग की मॉडल नहीं। आप।",
 "pl":"Wgraj jedno zdjęcie. Bride Studio pokaże Ci tę suknię na Tobie — Twoja twarz, Twój odcień skóry, Twoja sylwetka. Nie modelka z katalogu. Ty.","cs":"Nahrajte jednu fotku. Bride Studio vám ty šaty ukáže na vás — vaše tvář, váš odstín pleti, vaše postava. Ne modelka z katalogu. Vy.","uk":"Завантажте одне фото. Bride Studio покаже цю сукню на вас — ваше обличчя, ваш відтінок шкіри, ваша фігура. Не модель із каталогу. Ви.","ru":"Загрузите одно фото. Bride Studio покажет это платье на вас — ваше лицо, ваш оттенок кожи, ваша фигура. Не модель из каталога. Вы."},

"Download on the App Store": {
 "tr":"App Store'dan indir","de":"Im App Store laden","es":"Descargar en App Store",
 "fr":"Télécharger sur l'App Store","it":"Scarica su App Store","pt-BR":"Baixar na App Store",
 "ja":"App Store でダウンロード","ko":"App Store에서 받기","zh-Hans":"在 App Store 下载",
 "hi":"App Store से डाउनलोड करें",
 "pl":"Pobierz w App Store","cs":"Stáhnout v App Store","uk":"Завантажити в App Store","ru":"Загрузить в App Store"},

"How it works": {"tr":"Nasıl çalışır","de":"So funktioniert es","es":"Cómo funciona","fr":"Comment ça marche",
 "it":"Come funziona","pt-BR":"Como funciona","ja":"使い方","ko":"이용 방법","zh-Hans":"如何使用","hi":"यह कैसे काम करता है",
 "pl":"Jak to działa","cs":"Jak to funguje","uk":"Як це працює","ru":"Как это работает"},
"Gowns": {"tr":"Gelinlikler","de":"Kleider","es":"Vestidos","fr":"Robes","it":"Abiti","pt-BR":"Vestidos",
 "ja":"ドレス","ko":"드레스","zh-Hans":"婚纱","hi":"गाउन",
 "pl":"Suknie","cs":"Šaty","uk":"Сукні","ru":"Платья"},
"Get the app": {"tr":"Uygulamayı al","de":"App holen","es":"Obtener la app","fr":"Obtenir l'app",
 "it":"Scarica l'app","pt-BR":"Baixar o app","ja":"アプリを入手","ko":"앱 받기","zh-Hans":"获取应用","hi":"ऐप लें",
 "pl":"Pobierz aplikację","cs":"Stáhnout aplikaci","uk":"Завантажити застосунок","ru":"Скачать приложение"},
"Scroll": {"tr":"Kaydır","de":"Scrollen","es":"Desliza","fr":"Défiler","it":"Scorri","pt-BR":"Role",
 "ja":"スクロール","ko":"스크롤","zh-Hans":"向下滚动","hi":"स्क्रॉल",
 "pl":"Przewiń","cs":"Posunout","uk":"Гортайте","ru":"Листайте"},

"Choose a photo.": {"tr":"Bir fotoğraf seç.","de":"Wähle ein Foto.","es":"Elige una foto.","fr":"Choisissez une photo.",
 "it":"Scegli una foto.","pt-BR":"Escolha uma foto.","ja":"写真を選ぶ。","ko":"사진을 고르세요.","zh-Hans":"选一张照片。","hi":"एक फ़ोटो चुनें।",
 "pl":"Wybierz zdjęcie.","cs":"Vyberte fotku.","uk":"Оберіть фото.","ru":"Выберите фото."},
"Pick a gown.": {"tr":"Bir gelinlik seç.","de":"Wähle ein Kleid.","es":"Elige un vestido.","fr":"Choisissez une robe.",
 "it":"Scegli un abito.","pt-BR":"Escolha um vestido.","ja":"ドレスを選ぶ。","ko":"드레스를 고르세요.","zh-Hans":"选一件婚纱。","hi":"एक गाउन चुनें।",
 "pl":"Wybierz suknię.","cs":"Vyberte šaty.","uk":"Оберіть сукню.","ru":"Выберите платье."},
"See yourself in it.": {"tr":"Üzerinde gör.","de":"Sieh dich darin.","es":"Mírate con él.","fr":"Voyez-vous dedans.",
 "it":"Guardati con addosso.","pt-BR":"Veja-se nele.","ja":"その姿を見る。","ko":"그 모습을 보세요.","zh-Hans":"看见自己穿上它。","hi":"खुद को उसमें देखें।",
 "pl":"Zobacz ją na sobie.","cs":"Uvidíte je na sobě.","uk":"Побачте її на собі.","ru":"Увидьте его на себе."},

"One picture of yourself facing the camera. The app looks at it before\n           it starts and tells you if something is going to get in the way.": {
 "tr":"Kameraya bakan tek bir fotoğraf. Uygulama başlamadan önce ona bakıyor, sonucu bozacak bir şey varsa söylüyor.",
 "de":"Ein Bild von dir, in die Kamera blickend. Die App sieht es sich vorher an und sagt dir, wenn etwas im Weg ist.",
 "es":"Una foto tuya mirando a la cámara. La app la revisa antes de empezar y te avisa si algo va a estorbar.",
 "fr":"Une photo de vous face à l'objectif. L'app la regarde avant de commencer et vous dit si quelque chose va gêner.",
 "it":"Una tua foto rivolta verso l'obiettivo. L'app la guarda prima di iniziare e ti dice se qualcosa darà problemi.",
 "pt-BR":"Uma foto sua olhando para a câmera. O app confere antes de começar e avisa se algo vai atrapalhar.",
 "ja":"カメラを向いた写真を1枚。アプリは始める前にそれを確認し、うまくいかない原因があれば教えます。",
 "ko":"카메라를 바라본 사진 한 장. 앱이 시작 전에 확인하고, 결과를 방해할 요소가 있으면 알려줍니다.",
 "zh-Hans":"一张正对镜头的照片。开始之前，应用会先看一眼，若有影响结果的地方会告诉你。",
 "hi":"कैमरे की ओर देखती हुई आपकी एक तस्वीर। ऐप शुरू करने से पहले उसे देखता है और बताता है कि कुछ आड़े आएगा या नहीं।",
 "pl":"Jedno zdjęcie twarzą do obiektywu. Aplikacja patrzy na nie przed startem i mówi, jeśli coś zepsuje wynik.","cs":"Jedna fotka tváří k objektivu. Aplikace se na ni podívá ještě před startem a řekne, jestli něco výsledek pokazí.","uk":"Одне фото обличчям до камери. Застосунок дивиться на нього ще до старту й каже, якщо щось зіпсує результат.","ru":"Одно фото лицом к камере. Приложение смотрит на него до начала и говорит, если что-то испортит результат."},

"Filter by the silhouette you already have in mind — A-line, ballgown,\n           mermaid, sheath — or keep going until something stops you.": {
 "tr":"Aklındaki siluete göre süz — A kesim, prenses, balık, dar kesim — ya da bir şey seni durdurana kadar bakmaya devam et.",
 "de":"Filtere nach der Silhouette, die dir vorschwebt — A-Linie, Prinzess, Meerjungfrau, gerade — oder blättere, bis dich etwas festhält.",
 "es":"Filtra por la silueta que ya tienes en mente — corte A, princesa, sirena, recto — o sigue mirando hasta que algo te detenga.",
 "fr":"Filtrez par la silhouette que vous avez en tête — trapèze, princesse, sirène, droite — ou continuez jusqu'à ce qu'une robe vous arrête.",
 "it":"Filtra per la silhouette che hai già in mente — A, principessa, sirena, dritto — o continua finché qualcosa non ti ferma.",
 "pt-BR":"Filtre pela silhueta que já tem em mente — corte A, princesa, sereia, reto — ou continue até algo te parar.",
 "ja":"思い描いているシルエットで絞り込みます。Aライン、プリンセス、マーメイド、ストレート。あるいは目が留まるまで見続けても。",
 "ko":"이미 마음에 둔 실루엣으로 걸러 보세요. A라인, 볼가운, 머메이드, 시스. 아니면 눈이 멈출 때까지 계속 보세요.",
 "zh-Hans":"按心中想好的廓形筛选——A 字、蓬裙、鱼尾、直筒——或者一直看下去，直到有一件让你停住。",
 "hi":"जो सिल्हूट पहले से मन में है उससे छाँटें — ए-लाइन, बॉलगाउन, मरमेड, शीथ — या तब तक देखते रहें जब तक कोई रोक न ले।",
 "pl":"Filtruj po fasonie, który masz już w głowie — krój A, balowa, syrena, prosta — albo przewijaj, aż coś Cię zatrzyma.","cs":"Filtrujte podle střihu, který už máte v hlavě — áčkový, plesové, mořská panna, pouzdrové — nebo posouvejte, dokud vás něco nezastaví.","uk":"Фільтруйте за силуетом, який уже маєте на думці — А-силует, бальна, русалка, пряма — або гортайте, доки щось вас не спинить.","ru":"Фильтруйте по силуэту, который уже держите в голове — А-силуэт, бальное, русалка, прямое — или листайте, пока что-то вас не остановит."},

"A full-length view and a close portrait, ready to save, to put side by\n           side, and to send to whoever you are taking with you.": {
 "tr":"Tam boy bir kare ve yakın bir portre; kaydetmeye, yan yana koymaya ve yanında götüreceğin kişiye göndermeye hazır.",
 "de":"Eine Ganzkörperaufnahme und ein nahes Porträt — zum Speichern, Nebeneinanderlegen und Schicken an die, die mitkommt.",
 "es":"Una foto de cuerpo entero y un retrato cercano, listos para guardar, comparar y enviar a quien te acompañe.",
 "fr":"Une vue en pied et un portrait rapproché, prêts à enregistrer, à comparer et à envoyer à celle qui vous accompagne.",
 "it":"Un'inquadratura a figura intera e un ritratto ravvicinato, pronti da salvare, confrontare e mandare a chi verrà con te.",
 "pt-BR":"Uma foto de corpo inteiro e um retrato de perto, prontos para salvar, comparar e mandar para quem for com você.",
 "ja":"全身の1枚と、寄りのポートレート。保存して、並べて見比べて、一緒に行く人に送れます。",
 "ko":"전신 컷과 클로즈업 한 장. 저장하고, 나란히 두고 비교하고, 함께 갈 사람에게 보낼 수 있습니다.",
 "zh-Hans":"一张全身，一张近景。可以保存、并排比较，也可以发给陪你去的人。",
 "hi":"एक पूरी लंबाई का शॉट और एक क़रीबी पोर्ट्रेट — सहेजने, साथ-साथ रखकर देखने और जिसे साथ ले जा रही हैं उसे भेजने के लिए तैयार।",
 "pl":"Całą sylwetkę i bliski portret — gotowe, żeby zapisać, zestawić obok siebie i wysłać tej osobie, którą zabierasz ze sobą.","cs":"Celá postava a detail zblízka — připravené uložit, položit vedle sebe a poslat té, kterou si berete s sebou.","uk":"Повний зріст і близький портрет — готові зберегти, покласти поруч і надіслати тій, кого берете з собою.","ru":"Полный рост и крупный портрет — готовые сохранить, положить рядом и отправить той, кого берёте с собой."},

"The collection": {"tr":"Koleksiyon","de":"Die Kollektion","es":"La colección","fr":"La collection",
 "it":"La collezione","pt-BR":"A coleção","ja":"コレクション","ko":"컬렉션","zh-Hans":"系列","hi":"कलेक्शन",
 "pl":"Kolekcja","cs":"Kolekce","uk":"Колекція","ru":"Коллекция"},
"Over 300 gowns,<br>and every one described.": {
 "tr":"300'den fazla gelinlik,<br>ve her biri anlatılmış.",
 "de":"Über 300 Kleider,<br>und jedes beschrieben.",
 "es":"Más de 300 vestidos,<br>y cada uno descrito.",
 "fr":"Plus de 300 robes,<br>et chacune décrite.",
 "it":"Oltre 300 abiti,<br>e ognuno descritto.",
 "pt-BR":"Mais de 300 vestidos,<br>e cada um descrito.",
 "ja":"300着以上、<br>そのすべてに説明を。",
 "ko":"300벌이 넘는 드레스,<br>하나하나 설명과 함께.",
 "zh-Hans":"300 多款婚纱，<br>每一件都有说明。",
 "hi":"300 से ज़्यादा गाउन,<br>और हर एक का ब्योरा।",
 "pl":"Ponad 300 sukni,<br>każda opisana.","cs":"Přes 300 šatů,<br>a každé popsané.","uk":"Понад 300 суконь,<br>і кожна описана.","ru":"Больше 300 платьев,<br>и каждое описано."},
"Browse all gowns": {"tr":"Gelinliklerin tamamı","de":"Alle Kleider ansehen","es":"Ver todos los vestidos",
 "fr":"Voir toutes les robes","it":"Vedi tutti gli abiti","pt-BR":"Ver todos os vestidos",
 "ja":"すべてのドレスを見る","ko":"드레스 전체 보기","zh-Hans":"浏览全部婚纱","hi":"सभी गाउन देखें",
 "pl":"Zobacz wszystkie suknie","cs":"Zobrazit všechny šaty","uk":"Переглянути всі сукні","ru":"Смотреть все платья"},

"gowns to try": {"tr":"denenecek gelinlik","de":"Kleider zum Anprobieren","es":"vestidos para probar",
 "fr":"robes à essayer","it":"abiti da provare","pt-BR":"vestidos para provar","ja":"試着できるドレス",
 "ko":"입어볼 드레스","zh-Hans":"可试穿婚纱","hi":"आज़माने के लिए गाउन",
 "pl":"sukni do przymierzenia","cs":"šatů k vyzkoušení","uk":"суконь для примірки","ru":"платьев для примерки"},
"languages": {"tr":"dil","de":"Sprachen","es":"idiomas","fr":"langues","it":"lingue","pt-BR":"idiomas",
 "ja":"言語","ko":"개 언어","zh-Hans":"种语言","hi":"भाषाएँ",
 "pl":"języków","cs":"jazyků","uk":"мов","ru":"языков"},
"to your first look": {"tr":"ilk karene kadar","de":"bis zum ersten Blick","es":"hasta tu primera imagen",
 "fr":"jusqu'à votre premier aperçu","it":"al primo sguardo","pt-BR":"até sua primeira imagem",
 "ja":"最初の一枚まで","ko":"첫 결과까지","zh-Hans":"看到第一张","hi":"पहली झलक तक",
 "pl":"do pierwszego kadru","cs":"k prvnímu snímku","uk":"до першого кадру","ru":"до первого кадра"},

"An appointment gives you an hour and five dresses. This gives you an evening\n       and as many as you like.": {
 "tr":"Bir randevuda bir saatin ve beş gelinliğin oluyor. Burada bir akşamın var, gelinlik de istediğin kadar.",
 "de":"Ein Termin gibt dir eine Stunde und fünf Kleider. Das hier gibt dir einen Abend und so viele du willst.",
 "es":"Una cita te da una hora y cinco vestidos. Esto te da una tarde entera y todos los que quieras.",
 "fr":"Un rendez-vous vous donne une heure et cinq robes. Ceci vous donne une soirée et autant que vous voulez.",
 "it":"Un appuntamento ti dà un'ora e cinque abiti. Questo ti dà una serata e quanti ne vuoi.",
 "pt-BR":"Um horário te dá uma hora e cinco vestidos. Isto te dá uma noite e quantos você quiser.",
 "ja":"予約で得られるのは1時間と5着。ここで得られるのは一晩と、好きなだけの数。",
 "ko":"예약으로 주어지는 건 한 시간과 다섯 벌. 여기서 주어지는 건 하룻저녁과 원하는 만큼.",
 "zh-Hans":"一次预约给你一小时、五件。这里给你一整晚，想看多少都行。",
 "hi":"एक अपॉइंटमेंट आपको एक घंटा और पाँच ड्रेस देता है। यह आपको पूरी शाम देता है, और जितने चाहें उतने।",
 "pl":"W salonie masz godzinę i pięć sukien. Tutaj masz wieczór i tyle sukni, ile chcesz.","cs":"V salonu máte hodinu a pětery šaty. Tady máte večer a tolik šatů, kolik chcete.","uk":"У салоні у вас година й п'ять суконь. Тут — вечір і стільки суконь, скільки схочете.","ru":"В салоне у вас час и пять платьев. Здесь — вечер и столько платьев, сколько захотите."},
"So the hour you do get is spent on the three you already know are right.": {
 "tr":"Böylece elindeki o bir saat, zaten doğru olduğunu bildiğin üçüne gidiyor.",
 "de":"So geht die eine Stunde, die du hast, an die drei, von denen du längst weißt.",
 "es":"Así, la hora que sí tienes se va en los tres que ya sabes que son.",
 "fr":"Ainsi l'heure dont vous disposez passe sur les trois dont vous êtes déjà sûre.",
 "it":"Così l'ora che hai la spendi sui tre che sai già essere quelli giusti.",
 "pt-BR":"Assim, a hora que você tem é gasta nos três que você já sabe que são.",
 "ja":"だから実際の1時間は、もう分かっている3着に使えます。",
 "ko":"그래서 실제로 주어진 한 시간은, 이미 맞다고 아는 세 벌에 쓰입니다.",
 "zh-Hans":"于是那一小时，就花在你早已知道合适的那三件上。",
 "hi":"तो जो एक घंटा मिलता है, वह उन तीन पर जाता है जिन्हें आप पहले से जानती हैं।",
 "pl":"Dzięki temu ta jedna godzina idzie na te trzy, o których już wiesz.","cs":"Ta jedna hodina pak padne na ty troje, o kterých už víte.","uk":"І та година йде на ті три, про які ви вже знаєте.","ru":"И этот час уходит на те три, о которых вы уже знаете."},

"Try your first gown tonight.": {
 "tr":"İlk gelinliğini bu akşam dene.","de":"Probier dein erstes Kleid heute Abend.",
 "es":"Pruébate tu primer vestido esta noche.","fr":"Essayez votre première robe ce soir.",
 "it":"Prova il tuo primo abito stasera.","pt-BR":"Experimente seu primeiro vestido hoje à noite.",
 "ja":"最初の一着を、今夜。","ko":"첫 드레스를 오늘 밤에.","zh-Hans":"今晚就试第一件。","hi":"आज रात अपना पहला गाउन आज़माएँ।",
 "pl":"Przymierz pierwszą suknię dziś wieczorem.","cs":"Zkuste první šaty ještě dnes večer.","uk":"Приміряйте першу сукню сьогодні ввечері.","ru":"Примерьте первое платье сегодня вечером."},
"One photo is all it takes. Nothing to fill in, nothing to sign up for.": {
 "tr":"Tek bir fotoğraf yetiyor. Doldurulacak form yok, üye olunacak bir şey yok.",
 "de":"Ein Foto genügt. Nichts auszufüllen, nichts anzumelden.",
 "es":"Basta con una foto. Nada que rellenar, nada que registrar.",
 "fr":"Une photo suffit. Rien à remplir, rien à créer.",
 "it":"Basta una foto. Niente moduli, niente registrazione.",
 "pt-BR":"Basta uma foto. Nada para preencher, nada para cadastrar.",
 "ja":"必要なのは写真1枚だけ。記入も登録もありません。",
 "ko":"사진 한 장이면 됩니다. 작성할 것도, 가입할 것도 없습니다.",
 "zh-Hans":"只需要一张照片。不用填表，也不用注册。",
 "hi":"बस एक फ़ोटो चाहिए। न कुछ भरना है, न साइन अप करना है।",
 "pl":"Wystarczy jedno zdjęcie. Żadnych formularzy, żadnej rejestracji.","cs":"Stačí jedna fotka. Nic nevyplňovat, nikam se neregistrovat.","uk":"Достатньо одного фото. Нічого не заповнювати, ніде не реєструватися.","ru":"Достаточно одного фото. Ничего не заполнять, нигде не регистрироваться."},

"Privacy": {"tr":"Gizlilik","de":"Datenschutz","es":"Privacidad","fr":"Confidentialité","it":"Privacy",
 "pt-BR":"Privacidade","ja":"プライバシー","ko":"개인정보","zh-Hans":"隐私","hi":"गोपनीयता",
 "pl":"Prywatność","cs":"Soukromí","uk":"Приватність","ru":"Конфиденциальность"},
"Terms": {"tr":"Koşullar","de":"AGB","es":"Términos","fr":"Conditions","it":"Termini","pt-BR":"Termos",
 "ja":"利用規約","ko":"이용약관","zh-Hans":"条款","hi":"शर्तें",
 "pl":"Regulamin","cs":"Podmínky","uk":"Умови","ru":"Условия"},
"Support": {"tr":"Destek","de":"Support","es":"Soporte","fr":"Assistance","it":"Assistenza","pt-BR":"Suporte",
 "ja":"サポート","ko":"고객지원","zh-Hans":"支持","hi":"सहायता",
 "pl":"Pomoc","cs":"Podpora","uk":"Підтримка","ru":"Поддержка"},
"Results are AI visualisations, not photographs of a real fitting.": {
 "tr":"Sonuçlar yapay zekâ görselleştirmesidir, gerçek bir provanın fotoğrafı değildir.",
 "de":"Ergebnisse sind KI-Visualisierungen, keine Fotos einer echten Anprobe.",
 "es":"Los resultados son visualizaciones de IA, no fotos de una prueba real.",
 "fr":"Les résultats sont des visualisations IA, pas des photos d'un essayage réel.",
 "it":"I risultati sono visualizzazioni IA, non foto di una prova reale.",
 "pt-BR":"Os resultados são visualizações de IA, não fotos de uma prova real.",
 "ja":"結果はAIによる視覚化であり、実際の試着の写真ではありません。",
 "ko":"결과는 AI 시각화이며, 실제 피팅을 찍은 사진이 아닙니다.",
 "zh-Hans":"结果为 AI 生成的效果图，并非真实试穿的照片。",
 "hi":"परिणाम AI विज़ुअलाइज़ेशन हैं, किसी असली फ़िटिंग की तस्वीरें नहीं।",
 "pl":"Wyniki to wizualizacje AI, nie zdjęcia z prawdziwej przymiarki.","cs":"Výsledky jsou vizualizace AI, ne fotografie skutečné zkoušky.","uk":"Результати — це візуалізації ШІ, а не фото справжньої примірки.","ru":"Результаты — это визуализации ИИ, а не фотографии настоящей примерки."},

"Her photo": {"tr":"Fotoğrafı","de":"Ihr Foto","es":"Su foto","fr":"Sa photo","it":"La sua foto",
 "pt-BR":"A foto dela","ja":"彼女の写真","ko":"그녀의 사진","zh-Hans":"她的照片","hi":"उसकी फ़ोटो",
 "pl":"Jej zdjęcie","cs":"Její fotka","uk":"Її фото","ru":"Её фото"},
"Her photo + the gown": {"tr":"Fotoğrafı + gelinlik","de":"Ihr Foto + das Kleid","es":"Su foto + el vestido",
 "fr":"Sa photo + la robe","it":"La sua foto + l'abito","pt-BR":"A foto dela + o vestido",
 "ja":"彼女の写真＋ドレス","ko":"그녀의 사진 + 드레스","zh-Hans":"她的照片 + 婚纱","hi":"उसकी फ़ोटो + गाउन",
 "pl":"Jej zdjęcie + suknia","cs":"Její fotka + šaty","uk":"Її фото + сукня","ru":"Её фото + платье"},
"Her, wearing it": {"tr":"Üzerinde","de":"Sie, darin","es":"Ella, con él","fr":"Elle, dedans",
 "it":"Lei, con addosso","pt-BR":"Ela, vestindo","ja":"それを着た彼女","ko":"그것을 입은 그녀","zh-Hans":"她，穿上它","hi":"वह, उसे पहने",
 "pl":"Na niej","cs":"Na ní","uk":"На ній","ru":"На ней"},
}


def build(lang, src):
    """Bir dilin ana sayfası."""
    out = src
    # Uzundan kısaya: "Her photo" ile "Her photo + the gown" aynı listede ve
    # kısası önce çalışırsa uzununun başını yiyip onu bulunamaz hâle getiriyor.
    for en in sorted(COPY, key=len, reverse=True):
        if lang == "en":
            continue
        # Başlık ayrıca kelimelere bölünerek yazılıyor, bu yüzden düz hâli
        # sayfada geçmiyor; aranmaması gereken tek metin o.
        if en == "See yourself in the gown.":
            continue
        if en not in out:
            print(f"  ! bulunamadı: {en[:44]}…")
            continue
        out = out.replace(en, COPY[en][lang])

    code = LANGS[lang]
    base = f"{SITE}/{code + '/' if code else ''}"

    # Başlıktaki kelimeler tek tek yükseliyor, yani çeviri de kelimelere
    # bölünmeli. Çince ve Japoncada boşluk yok — tek parça kalıyorlar ve
    # animasyon bütün satıra uygulanıyor.
    headline = COPY["See yourself in the gown."].get(lang, "See yourself in the gown.") if lang != "en" else "See yourself in the gown."
    words = "".join(f'<span class="word"><span>{w}</span></span> ' for w in headline.split())
    out = re.sub(r"<h1>.*?</h1>", f"<h1>{words.strip()}</h1>", out, count=1, flags=re.S)

    # Kök göreli bağlantılar dilin köküne bakmalı.
    out = out.replace('href="/gowns/"', f'href="{base}gowns/"')
    out = out.replace('href="/"', f'href="{base}"')
    out = out.replace('<html lang="en">', f'<html lang="{lang}">')
    out = out.replace(f'<link rel="canonical" href="{SITE}/">',
                      f'<link rel="canonical" href="{base}">')

    # hreflang: on bir sürüm birbirinin kopyası sayılmasın.
    alts = "\n".join(
        f'<link rel="alternate" hreflang="{l}" href="{SITE}/{LANGS[l] + "/" if LANGS[l] else ""}">'
        for l in LANGS) + f'\n<link rel="alternate" hreflang="x-default" href="{SITE}/">'
    out = out.replace("</head>", alts + "\n</head>", 1)

    # Dil seçici.
    items = "".join(
        f'<a href="{SITE}/{LANGS[l] + "/" if LANGS[l] else ""}"{" class=on" if l == lang else ""}>{LANG_NAMES[l]}</a>'
        for l in LANGS)
    picker = (f'<details class="lang"><summary>{LANG_NAMES[lang]}</summary>'
              f'<div class="lang-menu">{items}</div></details>')
    out = out.replace("</nav>", picker + "</nav>", 1)
    return out


LANG_CSS = """
/* Dil menüsü.
   Renkler `header nav a`dan daha özgül yazılmak zorunda: üst çubuktaki
   bağlantılar koyu perdenin üstünde beyaz ve menü onların içinde yaşıyor —
   ilk hâlinde beyaz zemine beyaz yazı düştü ve menü okunmaz oldu. */
header nav .lang{position:relative;font-size:13px;margin-left:22px}
header nav .lang summary{list-style:none;cursor:pointer;color:inherit;opacity:.85;
  padding:5px 12px;border:1px solid currentColor;border-radius:999px}
header nav .lang summary::-webkit-details-marker{display:none}
header nav .lang summary::after{content:" ▾";opacity:.6}
header nav .lang-menu{position:absolute;right:0;top:calc(100% + 9px);z-index:80;
  background:#fff;border:1px solid var(--hair);border-radius:14px;padding:8px;min-width:180px;
  box-shadow:0 20px 44px rgba(0,0,0,.24);display:grid;gap:2px}
header nav .lang-menu a{display:block;margin:0;padding:9px 12px;border-radius:9px;
  font-size:14px;color:var(--ink);opacity:1}
header nav .lang-menu a:hover{background:var(--cream);color:var(--ink)}
header nav .lang-menu a.on{color:var(--gold)}
"""


def swap_consent(page, lang):
    """Bandı ve dil şeridini sayfanın diline çevirir.

    `index.html` hem İngilizce sayfa hem şablon, yani betik kendi çıktısının
    üstüne yazıyor — dil menüsünde de olan şey. İkisi de önce **tamamen**
    sökülüyor, sonra bir tane konuyor. Sökme sınırını bir adım fazla
    ilerletmek, bir keresinde bandı silmek yerine sayfanın tamamını ikinci kez
    yazdırmıştı; o yüzden kesme tek bir tembel eşleşme.
    """
    page = re.sub(r"<div id=bs-consent\b.*?</script>", "", page, flags=re.S)
    page = re.sub(r"<div id=bs-lang\b.*?</script>", "", page, flags=re.S)
    page = page.replace("<body>", "<body>" + langhint.strip(lang), 1)
    return page.replace("</body>", consent.banner(lang) + "\n</body>", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src = (ROOT / "index.html").read_text()

    # Şablon her seferinde temizleniyor.
    #
    # `index.html` hem İngilizce sayfa hem şablon, yani betik çıktıyı kendi
    # girdisinin üstüne yazıyor. İkinci çalıştırmada bu, bir önceki turda
    # eklenen dil seçicinin üstüne bir tane daha koydu — ekranda iki menü
    # belirdi — ve CSS'i "zaten var" sanıp güncellemedi, yani düzeltme hiç
    # ulaşmadı. Önce eskisi sökülüyor, sonra yenisi konuyor.
    src = re.sub(r'<details class="lang">.*?</details>', "", src, flags=re.S)
    src = re.sub(r"\n/\* Dil menüsü\..*?\.lang-menu a\.on\{[^}]*\}\n", "\n", src, flags=re.S)
    src = src.replace("</style>", LANG_CSS + "</style>", 1)

    print(f"{len(COPY)} metin, {len(LANGS)} dil")
    if not a.apply:
        print("kuru çalışma — yazmak için --apply")
        return

    for lang, code in LANGS.items():
        page = swap_consent(build(lang, src), lang)
        if code:
            d = ROOT / code
            d.mkdir(exist_ok=True)
            (d / "index.html").write_text(page)
        else:
            (ROOT / "index.html").write_text(page)
        print(f"  {lang} → /{code + '/' if code else ''}")


if __name__ == "__main__":
    main()
