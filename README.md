<p align="center">
  <img src="assets/ayus-header.png" alt="A.Y.U.S." width="800">
</p>

Görüntü tabanlı göreli risk haritası çıkaran ve geçilebilir alanlar üzerinden rota öneren, TUA Astro Hackathon için geliştirilmiş bir afet rota planlama prototipi.

## Hızlı başlangıç

Depoyu indirin:

```bash
git clone https://github.com/beratbesli/ayus-route-planner.git
cd ayus-route-planner
```

**Windows:** `kurulum.bat` dosyasını, ardından `baslat.bat` dosyasını çalıştırın.

**Linux:**

```bash
./kurulum.sh
./baslat.sh
```

Uygulamada görüntüyü seçip **Rota oluştur** düğmesine basın. Üretilen rota ve risk haritası seçilen çıktı klasörüne kaydedilir.

## Nasıl çalışır?

1. Görüntü gri tona çevrilir; Gaussian bulanıklaştırma ve Canny kenar çıkarımı uygulanır.
2. Görüntü, bütün pikselleri tam bir kez kapsayan bir grid'e bölünür. Hücrelerdeki kenar yoğunluğu göreli risk olarak kullanılır.
3. Eşik üzerindeki hücreler kapatılır; kalan hücrelerden risk ve engelden uzaklık ağırlıklı bir grafik oluşturulur.
4. Varsayılan olarak deterministik Dijkstra rotası, isteğe bağlı olarak sabit seed destekli ACO rotası üretilir. Ayrışan yedek rotalar ve göreli güvenlik ölçümleri de hesaplanır.

Bu işlem gerçek bir hasar sınıflandırıcısı veya coğrafi doğrulama değildir. Sonuçların anlamı kullanılan görüntünün ölçeğine, güncelliğine, görüş açısına ve kalibrasyon eşiklerine bağlıdır.

## Komut satırı

```bash
python -m ayus --input depremfoto.png --output-dir outputs
```

Kalibrasyon dosyası kullanmak için:

```bash
python kalibrasyon.py --input depremfoto.png --output-config ayus_config.json
python -m ayus --config ayus_config.json
```

## Paketleme ve test

- Windows paketi: `paketle.bat`
- Linux `.deb` ve AppImage paketi: `./paketle.sh`

```bash
python -m pytest -q
python -m ruff check .
```

CI, desteklenen Python sürümlerinde birim testlerini çalıştırır. Paketleme akışı her ilgili PR'da Linux ve Windows çıktılarının gerçekten üretildiğini doğrular; sürüm etiketi oluştuğunda her iki platformun çıktıları ve `SHA256SUMS` aynı GitHub sürümüne yüklenir.

## Güvenlik ve kullanım sınırları

- Bu depo araştırma/hackathon prototipidir; tahliye veya acil durum kararlarında tek kaynak olarak kullanılmamalıdır.
- Rota üretimi, fiziksel geçilebilirliği, yapı stabilitesini, yangın/su/gaz tehlikelerini ya da canlı saha verisini doğrulamaz.
- Operatör, giriş görüntüsünün kaynağını ve zamanını doğrulamalı; çıktıyı yetkili kurum verileri ve saha gözlemiyle karşılaştırmalıdır.
- Güvenlik açığı bildirmek için [SECURITY.md](SECURITY.md) dosyasını kullanın.

## Lisans

[MIT Lisansı](LICENSE)
