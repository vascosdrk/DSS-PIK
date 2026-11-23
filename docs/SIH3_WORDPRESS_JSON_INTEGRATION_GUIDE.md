# Panduan Integrasi JSON Peringatan Dini Iklim DSS-PIK ke Portal SIH3 Provinsi Kepulauan Riau (WordPress)
**Sistem Sumber:** Decision Support System Peringatan Iklim Kepulauan Riau (DSS-PIK)  
**Institusi Penerbit:** BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Versi Skema:** `1.0.0` (`docs/schemas/sih3_regional_warning.schema.json`)  

---

## 1. Gambaran Umum Arsitektur Integrasi

Portal **SIH3 Provinsi Kepulauan Riau** (berbasis WordPress) dapat menampilkan informasi peringatan dini iklim per Kabupaten/Kota secara otomatis atau semi-otomatis menggunakan kontrak **JSON Terstandarisasi DSS-PIK**.

Terdapat dua metode konsumsi data yang didukung penuh oleh DSS-PIK:

1. **Konsumsi Otomatis via Endpoint Publik Read-Only (Direkomendasikan)**  
   WordPress mengambil data terbaru yang telah berstatus `PUBLISHED` melalui HTTP GET:
   ```text
   GET http://<host-dss-pik>:8000/api/v1/publications/sih3/latest.json
   ```
   - **Keamanan**: Endpoint ini bersifat *read-only*, diizinkan melalui CORS (`Access-Control-Allow-Origin: *`), dan **hanya** mengembalikan dokumen yang telah melalui persetujuan (`APPROVED` $\rightarrow$ `PUBLISHED`). Dokumen berstatus `DRAFT` atau `REVIEW` tidak akan pernah terekspos.
2. **Unggah File JSON Manual oleh Admin SIH3**  
   Petugas BMKG mengekspor file `.json` yang telah tervalidasi dari jendela modal **Generator Peta Resmi & Ekspor JSON SIH3 (`OfficialMapModal`)** melalui tombol `Generate JSON SIH3` $\rightarrow$ `Unduh File JSON`, lalu mengunggahnya ke media/widget WordPress SIH3. Penetapan status peringatan dini per wilayah (PDKM, PDCHT, atau AMAN) dilakukan langsung secara independen dalam satu daftar 7 Kabupaten/Kota terpadu. Sistem DSS-PIK tidak melakukan publikasi otomatis sepihak ke WordPress; JSON berfungsi murni sebagai artefak pertukaran data resmi.

---

## 2. Pemetaan Wilayah Administratif & Kunci Poligon Peta SIH3

Setiap objek wilayah pada array `regions` memiliki 7 elemen tetap yang mewakili seluruh Kabupaten/Kota di Provinsi Kepulauan Riau. Untuk memastikan kompatibilitas penuh dengan GeoJSON / Geodatabase BMKG (`PDCHT_Kab_202501_das1.gdb`) maupun kode BPS/Kemendagri, setiap wilayah menyediakan tiga pengenal kanonis:

| Nama Wilayah (`region_name`) | Kode Kemendagri (`region_code`) | Kode BPS Compact (`bps_code_compact`) | Kunci Poligon GDB (`sih3_polygon_key` / `WADMKK`) |
| :--- | :---: | :---: | :--- |
| Kabupaten Bintan | `21.01` | `2101` | `BINTAN` |
| Kabupaten Karimun | `21.02` | `2102` | `KARIMUN` |
| Kabupaten Natuna | `21.03` | `2103` | `NATUNA` |
| Kabupaten Lingga | `21.04` | `2104` | `LINGGA` |
| Kabupaten Kepulauan Anambas | `21.05` | `2105` | `KEPULAUAN ANAMBAS` |
| Kota Batam | `21.71` | `2171` | `KOTA BATAM` |
| Kota Tanjungpinang | `21.72` | `2172` | `KOTA TANJUNGPINANG` |

---

## 3. Aturan Pewarnaan & Penanganan Multi-Bahaya (PDKM & PDCHT)

DSS-PIK mengevaluasi **Peringatan Dini Kekeringan Meteorologis (`PDKM`)** dan **Peringatan Dini Curah Hujan Tinggi (`PDCHT`)** secara terpisah. Satu Kabupaten/Kota dapat memiliki:
- Tidak ada peringatan aktif (`warnings: []`, status `AMAN` atau `INSUFFICIENT_DATA`),
- Satu peringatan aktif (`PDKM` saja atau `PDCHT` saja),
- Dua peringatan aktif secara simultan (`PDKM` dan `PDCHT` pada pos pengamatan berbeda di kabupaten yang sama).

### Standar Kode Warna BMKG
| Level / Status | Kode Hex | Arti Operasional |
| :--- | :---: | :--- |
| `AMAN` | `#33FF00` | Tidak ada peringatan dini aktif (data mencukupi $\ge 50\%$) |
| `WASPADA` | `#FFFF00` | Peringatan Dini Level Waspada |
| `SIAGA` | `#E69138` | Peringatan Dini Level Siaga |
| `AWAS` | `#FF0000` | Peringatan Dini Level Awas |
| `INSUFFICIENT_DATA` | `#94A3B8` | Data pengamatan belum mencukupi ($< 50\%$ pos valid) — **Jangan ditampilkan sebagai Hijau/Aman** |

---

## 4. Contoh Implementasi Shortcode PHP WordPress (`functions.php` atau Plugin Kustom SIH3)

Tambahkan cuplikan berikut pada plugin kustom atau `functions.php` tema WordPress SIH3 untuk menampilkan tabel dan kartu peringatan dini iklim Kepulauan Riau:

```php
<?php
/**
 * Shortcode: [sih3_peringatan_iklim_kepri]
 * Mengambil dan menampilkan JSON Peringatan Dini Wilayah dari DSS-PIK BMKG Tanjungpinang
 */
function sih3_render_peringatan_iklim_kepri($atts) {
    $atts = shortcode_atts(array(
        'endpoint' => 'http://127.0.0.1:8000/api/v1/publications/sih3/latest.json',
        'cache_ttl' => 300, // Cache 5 menit via WordPress Transient
    ), $atts, 'sih3_peringatan_iklim_kepri');

    $cache_key = 'sih3_dss_pik_latest_json';
    $data = get_transient($cache_key);

    if (false === $data) {
        $response = wp_remote_get($atts['endpoint'], array('timeout' => 10));
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return '<div class="sih3-warning-empty">Belum ada publikasi peringatan dini iklim aktif untuk periode ini.</div>';
        }
        $body = wp_remote_retrieve_body($response);
        $decoded = json_decode($body, true);
        if (!is_array($decoded) || empty($decoded['regions'])) {
            return '<div class="sih3-warning-empty">Format data publikasi peringatan dini tidak valid.</div>';
        }
        $data = $decoded;
        set_transient($cache_key, $data, intval($atts['cache_ttl']));
    }

    $pub = $data['publication'];
    $src = $data['source'];
    ob_start();
    ?>
    <div class="sih3-dss-pik-widget" style="font-family: sans-serif; border: 1px solid #cbd5e1; border-radius: 12px; padding: 16px; background: #ffffff;">
        <div style="margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
            <h3 style="margin: 0; font-size: 18px; color: #0f172a;">
                Peringatan Dini Iklim Ekstrem Provinsi Kepulauan Riau — <?php echo esc_html($src['evaluation_period']); ?>
            </h3>
            <p style="margin: 4px 0 0; font-size: 12px; color: #475569;">
                Sumber: <?php echo esc_html($src['institution']); ?> |
                Berlaku: <strong><?php echo esc_html($pub['valid_from']); ?></strong> s/d <strong><?php echo esc_html($pub['valid_until']); ?></strong> |
                ID Publikasi: <code><?php echo esc_html($pub['publication_id']); ?> (Rev #<?php echo intval($pub['revision']); ?>)</code>
            </p>
        </div>

        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
                <tr style="background: #f1f5f9; text-align: left;">
                    <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">Kabupaten / Kota</th>
                    <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">PDKM (Kekeringan)</th>
                    <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">PDCHT (Curah Hujan Tinggi)</th>
                    <th style="padding: 8px; border-bottom: 1px solid #cbd5e1;">Keterangan / Narasi</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($data['regions'] as $reg) :
                    $pdkm = $reg['hazard_assessments']['PDKM'];
                    $pdcht = $reg['hazard_assessments']['PDCHT'];
                ?>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-weight: 600;"><?php echo esc_html($reg['region_name']); ?></td>
                    <td style="padding: 8px;">
                        <span style="padding: 2px 8px; border-radius: 4px; font-weight: 700;">
                            <?php echo esc_html($pdkm['final_level']); ?>
                        </span>
                    </td>
                    <td style="padding: 8px;">
                        <span style="padding: 2px 8px; border-radius: 4px; font-weight: 700;">
                            <?php echo esc_html($pdcht['final_level']); ?>
                        </span>
                    </td>
                    <td style="padding: 8px; font-size: 12px; color: #334155;">
                        <?php
                        if (!empty($reg['warnings'])) {
                            foreach ($reg['warnings'] as $w) {
                                echo '<div><strong>[' . esc_html($w['hazard_code']) . ' - ' . esc_html($w['final_level']) . ']</strong> ' . esc_html($w['narrative']) . '</div>';
                            }
                        } else {
                            echo esc_html($pdkm['narrative']);
                        }
                        ?>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('sih3_peringatan_iklim_kepri', 'sih3_render_peringatan_iklim_kepri');
```

---

## 5. Contoh Pencocokan Poligon Peta Leaflet di WordPress SIH3

Ketika mewarnai layer GeoJSON Kabupaten/Kota di WordPress, gunakan pencocokan berbasis `sih3_polygon_key` (cocok dengan atribut `WADMKK` / `KABUPATEN` pada GDB BMKG) atau `region_code`:

```javascript
function matchRegionFromDssPik(featureProperties, dssPikRegions) {
  const wadmkk = (featureProperties.WADMKK || featureProperties.KABUPATEN || '').trim().toUpperCase();
  const kdpkab = (featureProperties.KDPKAB || featureProperties.region_code || '').trim();
  return dssPikRegions.find(
    (r) => r.sih3_polygon_key === wadmkk || r.region_code === kdpkab || r.bps_code_compact === kdpkab
  );
}
```

