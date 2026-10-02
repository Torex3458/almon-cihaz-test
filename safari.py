"""Gerçek macOS Safari'yi (safaridriver / WebDriver) sürer.

Her adres x her ekran boyu için: ekran görüntüsü + ölçüm (sayfa yüksekliği,
yatay taşma, sayfa hataları, yüklenemeyen kaynaklar).

Not: Safari WebDriver konsol günlüğünü vermez. Hatalar, sayfa açıldıktan hemen
sonra kurulan window.onerror / unhandledrejection / console.error yakalayıcısıyla
toplanır; ilk yükleme sırasında olan hata bu yolla görünmez. Yüklenemeyen
kaynaklar performance kayıtlarından (responseStatus >= 400) okunur.
"""
import json
import os
import re
import sys
import time

from selenium import webdriver

CIKTI = os.environ.get("CIKTI", "cikti")
BOYLAR = [(1440, 900), (1920, 1080)]
BEKLE = int(os.environ.get("BEKLE", "10"))

YAKALAYICI = r"""
if (!window.__almonHata) {
  window.__almonHata = [];
  window.addEventListener('error', function (e) {
    window.__almonHata.push('error: ' + (e.message || (e.target && (e.target.src || e.target.href)) || 'bilinmeyen'));
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    window.__almonHata.push('unhandledrejection: ' + String(e.reason));
  });
  var ce = console.error;
  console.error = function () {
    try { window.__almonHata.push('console.error: ' + Array.prototype.map.call(arguments, String).join(' ')); } catch (x) {}
    return ce.apply(console, arguments);
  };
}
return true;
"""

OLCUM = r"""
var d = document.documentElement, b = document.body;
var kaynak = [];
try {
  performance.getEntriesByType('resource').forEach(function (r) {
    if (typeof r.responseStatus === 'number' && r.responseStatus >= 400) kaynak.push(r.responseStatus + ' ' + r.name);
  });
} catch (x) {}
var genis = [];
try {
  var w = d.clientWidth;
  document.querySelectorAll('body *').forEach(function (el) {
    var r = el.getBoundingClientRect();
    if (r.right > w + 1 && r.width > 0 && genis.length < 10) {
      genis.push((el.tagName.toLowerCase()) + (el.id ? '#' + el.id : '') + ' sag=' + Math.round(r.right));
    }
  });
} catch (x) {}
return {
  baslik: document.title,
  adres: location.href,
  readyState: document.readyState,
  ic_genislik: window.innerWidth,
  ic_yukseklik: window.innerHeight,
  ekran: screen.width + 'x' + screen.height,
  dpr: window.devicePixelRatio,
  sayfa_yuksekligi: Math.max(d.scrollHeight, b ? b.scrollHeight : 0),
  sayfa_genisligi: Math.max(d.scrollWidth, b ? b.scrollWidth : 0),
  gorunen_genislik: d.clientWidth,
  yatay_tasma: Math.max(d.scrollWidth, b ? b.scrollWidth : 0) > d.clientWidth + 1,
  sag_tasan_ogeler: genis,
  hatalar: window.__almonHata || [],
  yuklenemeyen_kaynaklar: kaynak,
  kullanici_ajani: navigator.userAgent
};
"""


def ad_yap(adres):
    yol = re.sub(r"^https?://", "", adres).strip("/")
    return re.sub(r"[^A-Za-z0-9]+", "_", yol) or "kok"


def main():
    adresler = [a for a in " ".join(sys.argv[1:]).replace(",", " ").split() if a]
    os.makedirs(CIKTI, exist_ok=True)
    ozet = []
    surucu = webdriver.Safari()
    try:
        for g, y in BOYLAR:
            surucu.set_window_rect(x=0, y=0, width=g, height=y)
            for adres in adresler:
                kayit = {"cihaz": "mac-safari", "istenen_pencere": f"{g}x{y}", "istenen_adres": adres}
                try:
                    surucu.get("about:blank")
                    surucu.get(adres)
                    surucu.execute_script(YAKALAYICI)
                    bas = time.time()
                    while time.time() - bas < 30:
                        if surucu.execute_script("return document.readyState") == "complete":
                            break
                        time.sleep(0.5)
                    time.sleep(BEKLE)
                    pr = surucu.get_window_rect()
                    kayit["gercek_pencere"] = f"{pr['width']}x{pr['height']}"
                    kayit.update(surucu.execute_script(OLCUM))
                    dosya = f"mac-safari_{g}x{y}_{ad_yap(adres)}.png"
                    surucu.save_screenshot(os.path.join(CIKTI, dosya))
                    kayit["goruntu"] = dosya
                except Exception as e:  # bir adres düşerse ötekiler sürsün
                    kayit["hata"] = f"{type(e).__name__}: {e}"
                print(json.dumps(kayit, ensure_ascii=False))
                ozet.append(kayit)
    finally:
        surucu.quit()
    with open(os.path.join(CIKTI, "ozet-mac-safari.json"), "w", encoding="utf-8") as f:
        json.dump(ozet, f, ensure_ascii=False, indent=2)
    if any("hata" in k for k in ozet):
        sys.exit(1)


if __name__ == "__main__":
    main()
