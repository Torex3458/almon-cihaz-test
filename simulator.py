"""iOS simülatöründe (iPhone + iPad) Safari ile adresleri açar, ekran görüntüsü alır.

simctl sayfanın içini ölçemez; özet yalnız cihaz/sürüm/görüntü bilgisini verir.
Yerleşim yargısı görüntüye bakılarak verilir.
"""
import json
import os
import re
import subprocess
import sys
import time

CIKTI = os.environ.get("CIKTI", "cikti")
BEKLE = int(os.environ.get("BEKLE_SIM", "25"))


def kos(*komut, kontrol=True):
    print("+", " ".join(komut), flush=True)
    return subprocess.run(komut, check=kontrol, capture_output=True, text=True)


def ad_yap(adres):
    yol = re.sub(r"^https?://", "", adres).strip("/")
    return re.sub(r"[^A-Za-z0-9]+", "_", yol) or "kok"


def cihaz_sec():
    veri = json.loads(kos("xcrun", "simctl", "list", "devices", "available", "-j").stdout)
    adaylar = []
    for calisma, liste in veri["devices"].items():
        if "iOS" not in calisma:
            continue
        surum = calisma.split("iOS-")[-1].replace("-", ".")
        for c in liste:
            adaylar.append((surum, c["name"], c["udid"]))

    def surum_anahtar(s):
        return tuple(int(p) for p in re.findall(r"\d+", s))

    adaylar.sort(key=lambda a: surum_anahtar(a[0]), reverse=True)

    def bul(desenler):
        for desen in desenler:
            for a in adaylar:
                if re.fullmatch(desen, a[1]):
                    return a
        return None

    iphone = bul([r"iPhone 17", r"iPhone 16", r"iPhone 1\d", r"iPhone.*"])
    ipad = bul([r"iPad Air.*", r"iPad \(.*\)", r"iPad Pro.*", r"iPad.*"])
    return [("iphone", iphone), ("ipad", ipad)]


def main():
    adresler = [a for a in " ".join(sys.argv[1:]).replace(",", " ").split() if a]
    os.makedirs(CIKTI, exist_ok=True)
    ozet = []
    for tur, cihaz in cihaz_sec():
        if not cihaz:
            ozet.append({"cihaz": tur, "hata": "uygun simülatör bulunamadı"})
            continue
        surum, ad, udid = cihaz
        kayit_temel = {"cihaz": f"{tur}-safari", "model": ad, "ios": surum, "udid": udid}
        try:
            kos("xcrun", "simctl", "boot", udid, kontrol=False)
            kos("xcrun", "simctl", "bootstatus", udid, "-b")
            kos("xcrun", "simctl", "status_bar", udid, "override", "--time", "9:41",
                "--batteryState", "charged", "--batteryLevel", "100", kontrol=False)
            # Safari'nin ilk açılışı uzun sürer; boş sayfayla ısındır
            kos("xcrun", "simctl", "openurl", udid, "about:blank", kontrol=False)
            time.sleep(10)
            for adres in adresler:
                kayit = dict(kayit_temel, istenen_adres=adres)
                try:
                    kos("xcrun", "simctl", "openurl", udid, adres)
                    time.sleep(BEKLE)
                    dosya = f"{tur}-safari_{ad_yap(adres)}.png"
                    kos("xcrun", "simctl", "io", udid, "screenshot", "--type=png",
                        os.path.join(CIKTI, dosya))
                    kayit["goruntu"] = dosya
                except subprocess.CalledProcessError as e:
                    kayit["hata"] = f"{e.cmd}: {e.stderr.strip()[:300]}"
                print(json.dumps(kayit, ensure_ascii=False), flush=True)
                ozet.append(kayit)
        except subprocess.CalledProcessError as e:
            ozet.append(dict(kayit_temel, hata=f"{e.cmd}: {e.stderr.strip()[:300]}"))
        finally:
            kos("xcrun", "simctl", "shutdown", udid, kontrol=False)
    with open(os.path.join(CIKTI, "ozet-simulator.json"), "w", encoding="utf-8") as f:
        json.dump(ozet, f, ensure_ascii=False, indent=2)
    if any("hata" in k for k in ozet):
        sys.exit(1)


if __name__ == "__main__":
    main()
