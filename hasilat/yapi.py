
import openpyxl
import pandas as pd
import numpy as np

def extract_sap_data(file_path, sheet_name):
    df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    df = df_raw.copy().iloc[1:]
    df.columns = [
        "Durum", "Tayin", "Kayıt tarihi", "Tutar", "Fatura No", "Mali Yıl", "İş Alanı",
        "Belge No", "Müşteri", "Müşteri Adı", "Açıklama", "Aktarılma Durumu",
        "Muhasebe Belge No", "Oluşturan/Onaylayan"
    ]

    def extract_sicil(creator):
        if isinstance(creator, str) and '/' in creator:
            return creator.split('/')[0].strip()
        return np.nan

    df['YTP Sicil No'] = df['Oluşturan/Onaylayan'].apply(extract_sicil)

    nakit_df = df[df['Tayin'].str.upper() == 'NAKIT'].copy()
    visa_df = df[df['Tayin'].str.upper() == 'VISA'].copy()

    def get_last_amount_per_person(df_section):
        results = {}
        current_sicil = None
        last_tutar = None

        for _, row in df_section.iterrows():
            sicil = row['YTP Sicil No']
            if pd.notna(sicil):
                if current_sicil is not None and last_tutar is not None:
                    results[current_sicil] = last_tutar
                current_sicil = sicil
                last_tutar = row['Tutar']
            else:
                last_tutar = row['Tutar']

        if current_sicil is not None and last_tutar is not None:
            results[current_sicil] = last_tutar

        return pd.DataFrame(list(results.items()), columns=['YTP Sicil No', 'Tutar'])

    # Her kişiden sadece son Tutar alınır
    nakit_summary = get_last_amount_per_person(nakit_df).rename(columns={'Tutar': 'Nakit Toplam'})
    visa_summary = get_last_amount_per_person(visa_df).rename(columns={'Tutar': 'Visa Toplam'})

    # Genel toplamları ayrı topla (oluşturan boş olanlar)
    nakit_genel = nakit_df[nakit_df['YTP Sicil No'].isna()]['Tutar'].sum()
    visa_genel = visa_df[visa_df['YTP Sicil No'].isna()]['Tutar'].sum()

    # Kişisel verileri birleştir
    merged = pd.merge(nakit_summary, visa_summary, on='YTP Sicil No', how='outer')
    merged['Nakit Toplam'] = merged['Nakit Toplam'].fillna(0)
    merged['Visa Toplam'] = merged['Visa Toplam'].fillna(0)
    merged['Genel Toplam'] = merged['Nakit Toplam'] + merged['Visa Toplam']

    # Genel toplam satırı
    genel_satir = pd.DataFrame([{
        'YTP Sicil No': 'Genel Toplam',
        'Nakit Toplam': nakit_genel,
        'Visa Toplam': visa_genel,
        'Genel Toplam': nakit_genel + visa_genel
    }])

    final = pd.concat([merged, genel_satir], ignore_index=True)

    return final


# SAP verisini işle
dosya_yolu = "hasilat/Hasilat_karsilastirma_sistemi_1.xlsx"
sayfa_adi = "sistem yapılandırılmamış"

sap_verisi = extract_sap_data(dosya_yolu, sayfa_adi)
print(sap_verisi)

# Dosya adını belirle
output_file = "SAP_Yapilandirilmis.xlsx"

# Excel olarak kaydet
sap_verisi.to_excel(output_file, index=False, engine="openpyxl")

print(f"Yapılandırılmış veri '{output_file}' olarak kaydedildi.")
