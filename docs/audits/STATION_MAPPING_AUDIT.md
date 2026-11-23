# FINAL STATION MAPPING AUDIT (mapping_tambahan.xlsx)

Generated at: 2026-10-07T14:17:56.883851

## 0. DEBUG INFO MAPPING TAMBAHAN
- Ref_df loaded. Columns: ['source_key', 'source_nopos', 'source_name', 'source_name_variants', 'source_latitude', 'source_longitude', 'source_province', 'source_regency', 'available_in', 'file_count', 'source_files', 'name_strict', 'name_core', 'name_compact', 'mapping_status', 'mapping_method', 'station_id', 'station_name_master', 'station_name_reference', 'in_cews_master', 'usable_for_cews', 'distance_km', 'mapping_note', 'candidate_1', 'candidate_1_in_master', 'candidate_1_distance_km', 'candidate_1_name_similarity', 'candidate_2', 'candidate_2_in_master', 'candidate_2_distance_km', 'candidate_2_name_similarity', 'candidate_3', 'candidate_3_in_master', 'candidate_3_distance_km', 'candidate_3_name_similarity']
- Unique usable_for_cews values: [True]
- Ref_df size after usable filter: 52
- Ref_df size after station_id notna: 52
- Ref_df size after master_ids filter: 52
- Record 0: nopos='219C', key='NOPOS::219C::NAME::batu 18 kijang kijang', name='Batu 18 Kijang Kijang', id='21010601A'
- Record 1: nopos='228C', key='NOPOS::228C::NAME::ekang anculai teluk sebong', name='Ekang Anculai Teluk Sebong', id='21011001A'
- Record 2: nopos='228T', key='NOPOS::228T::NAME::poyotomo sri bintan', name='Poyotomo Sri Bintan', id='21011002A'
- Record 3: nopos='218C', key='NOPOS::218C::NAME::toapaya', name='Toapaya', id='21011201A'
- Record 4: nopos='250O', key='NOPOS::250O::NAME::teluk sasa sri kuala lobam', name='Teluk Sasa Sri Kuala Lobam', id='21011501A'
- Record 5: nopos='236X', key='NOPOS::236X::NAME::bunguran barat sedanau kp balau', name='Bunguran Barat Sedanau Kp Balau', id='21030501A'
- Record 6: nopos='227P', key='NOPOS::227P::NAME::bunguran selatan cemaga padang meliso', name='Bunguran Selatan Cemaga Padang Meliso', id='21031801A'
- Record 7: nopos='250I', key='NOPOS::250I::NAME::dompak tg siambang', name='Dompak Tg Siambang', id='21720401A'
- Record 8: nopos='228H', key='NOPOS::228H::NAME::kec subi melia', name='Kec Subi Melia', id='21030901A'
- Record 9: nopos='228F', key='NOPOS::228F::NAME::kec pulau tiga sabang mawang', name='Kec Pulau Tiga Sabang Mawang', id='21031101A'
- Attempting to match: sid_norm='00096091A', sname='STASIUN METEOROLOGI RHF TANJUNGPINANG'. Match found? YES

## 19. RINGKASAN MAPPING
- TOTAL MASTER STATION           : 57
- MASTER WITH SPI ANALYSIS       : 52
- MASTER WITH SPI FORECAST       : 52
- MASTER WITHOUT SPI             : 5
- EXACT MASTER MATCH             : 39
- MATCHED VIA mapping_tambahan   : 7
- RESOLVED AMBIGUOUS BY NAME/COORDINATE : 3

Breakdown reference:
  - MATCHED_REFERENCE: 7

- UNRESOLVED SOURCE              : 1
- EXCLUDED OUTSIDE MASTER        : 1
- AMBIGUOUS REMAINING            : 0
- CROSS-YEAR CONFLICT            : 0

## 20. STATION MASTER YANG BELUM MEMILIKI SPI
station_id|station_name|has_spi_analysis|has_spi_forecast|has_hth|has_ch|mapping_search_result
21710501B|ARG Pulau Setokok|False|False|True|True|TRUE_SPI_NOT_AVAILABLE
21020402B|ARG Tanjung Balai Karimun|False|False|True|True|TRUE_SPI_NOT_AVAILABLE
21040101B|ARG Singkep|False|False|True|True|TRUE_SPI_NOT_AVAILABLE
21010802B|ARG Tembeling|False|False|True|True|TRUE_SPI_NOT_AVAILABLE
21010603B|ARG Bintan Timur|False|False|True|True|TRUE_SPI_NOT_AVAILABLE


## 21. MAPPING YANG BERHASIL DISELAMATKAN (VIA mapping_tambahan.xlsx)
source_nopos|source_station_id|source_station_name|source_year|station_id_master|station_name_master|mapping_status_reference|mapping_method|distance_km|mapping_note
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2021|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2021|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2021|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2021|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2021|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2021|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2021|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2021|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2021|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2021|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2021|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2021|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2022|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2022|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2022|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2022|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2022|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2022|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2022|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2022|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2022|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2022|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2022|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2022|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2023|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2023|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2023|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2023|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2023|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2023|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2023|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2023|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2023|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2023|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2023|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2023|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2024|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2024|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2024|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2024|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2024|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2024|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2024|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2024|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2024|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2024|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2024|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2024|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2025|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2025|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2025|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2025|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
210310802a|210310802a|Selemut Cemaga|2025|21031802A|Selemut|MATCHED_REFERENCE|REFERENCE_EXACT_NAME_AND_COORD|0.4411357961246035|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2025|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2025|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096091a|00096091a|Stasiun Meteorologi RHF Tanjungpinang|2025|21720201A|Stamet Raja Haji Fisabilillah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0009372733251952894|Nama referensi dan koordinat konsisten
00096089a|00096089a|Stasiun Meteorologi Raja Haji Abdullah|2025|21020302A|Stamet Raja Haji Abdullah|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
00096179a|00096179a|Stasiun Meteorologi Dabo Singkep|2025|21040101A|Stamet Dabo Singkep|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.2739951720489993|Nama referensi dan koordinat konsisten
00096147a|00096147a|Stasiun Meteorologi Ranai Natuna|2025|21030701A|Stamet Ranai Natuna|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten
210310802a|210310802a|Selemut Cemaga|2025|21031802A|Selemut|MATCHED_REFERENCE|REFERENCE_EXACT_NAME_AND_COORD|0.4411357961246035|Nama referensi dan koordinat konsisten
00096087a|00096087a|Stasiun Meteorologi Hang Nadim Batam|2025|21710401A|Stamet Hang Nadim Batam|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.6634646579539218|Nama referensi dan koordinat konsisten
00096145a|00096145a|Stasiun Meteorologi Tarempa|2025|21050101A|Stamet Tarempa|MATCHED_REFERENCE|REFERENCE_CORE_NAME_AND_COORD|0.0|Nama referensi dan koordinat konsisten


