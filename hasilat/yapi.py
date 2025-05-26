import openpyxl
import pandas as pd
import numpy as np
import os

def extract_sap_data(file_path, sheet_name):
    """
    SAP Excel dosyasından veri çıkarıp yapılandırır
    """
    try:
        # Dosya kontrolü
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel dosyası bulunamadı: {file_path}")
        
        # Excel dosyasını oku
        df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        
        if df_raw.empty:
            raise ValueError("Excel dosyası boş")
        
        # İlk satırı header olarak kullan, gerisi veri
        df = df_raw.copy().iloc[1:]
        df.columns = [
            "Durum", "Tayin", "Kayıt tarihi", "Tutar", "Fatura No", "Mali Yıl", "İş Alanı",
            "Belge No", "Müşteri", "Müşteri Adı", "Açıklama", "Aktarılma Durumu",
            "Muhasebe Belge No", "Oluşturan/Onaylayan"
        ]
        
        # Boş satırları temizle
        df = df.dropna(how='all')
        
        def extract_sicil(creator):
            """YTP Sicil No'yu çıkar"""
            if isinstance(creator, str) and '/' in creator:
                sicil = creator.split('/')[0].strip()
                # Sayısal kontrol
                if sicil.isdigit():
                    return sicil
            return np.nan
        
        # YTP Sicil No'yu çıkar
        df['YTP Sicil No'] = df['Oluşturan/Onaylayan'].apply(extract_sicil)
        
        # Tutar sütununu sayısal yap
        df['Tutar'] = pd.to_numeric(df['Tutar'], errors='coerce')
        
        # Tayin sütununu temizle ve büyük harfe çevir
        df['Tayin'] = df['Tayin'].astype(str).str.upper().str.strip()
        
        # NAKIT ve VISA verilerini filtrele
        nakit_df = df[df['Tayin'] == 'NAKIT'].copy()
        visa_df = df[df['Tayin'] == 'VISA'].copy()
        
        def get_last_amount_per_person(df_section):
            """Her kişi için son tutarı al"""
            if df_section.empty:
                return pd.DataFrame(columns=['YTP Sicil No', 'Tutar'])
            
            # Sadece YTP Sicil No'su olan kayıtları al
            df_with_sicil = df_section[df_section['YTP Sicil No'].notna()].copy()
            
            if df_with_sicil.empty:
                return pd.DataFrame(columns=['YTP Sicil No', 'Tutar'])
            
            # Index'e göre sırala (son kayıt = en büyük index)
            df_with_sicil = df_with_sicil.sort_index()
            
            # Her sicil no için son kaydı al
            last_records = df_with_sicil.groupby('YTP Sicil No').tail(1)
            
            return last_records[['YTP Sicil No', 'Tutar']].copy()
        
        # Her kişi için son tutarları al
        nakit_summary = get_last_amount_per_person(nakit_df)
        visa_summary = get_last_amount_per_person(visa_df)
        
        # Sütun adlarını değiştir
        if not nakit_summary.empty:
            nakit_summary = nakit_summary.rename(columns={'Tutar': 'Nakit Toplam'})
        else:
            nakit_summary = pd.DataFrame(columns=['YTP Sicil No', 'Nakit Toplam'])
            
        if not visa_summary.empty:
            visa_summary = visa_summary.rename(columns={'Tutar': 'Visa Toplam'})
        else:
            visa_summary = pd.DataFrame(columns=['YTP Sicil No', 'Visa Toplam'])
        
        # Genel toplamları hesapla (YTP Sicil No boş olanlar)
        nakit_genel = nakit_df[nakit_df['YTP Sicil No'].isna()]['Tutar'].sum()
        visa_genel = visa_df[visa_df['YTP Sicil No'].isna()]['Tutar'].sum()
        
        # NaN değerleri 0 yap
        nakit_genel = 0 if pd.isna(nakit_genel) else nakit_genel
        visa_genel = 0 if pd.isna(visa_genel) else visa_genel
        
        # Kişisel verileri birleştir
        if not nakit_summary.empty or not visa_summary.empty:
            merged = pd.merge(nakit_summary, visa_summary, on='YTP Sicil No', how='outer')
            merged['Nakit Toplam'] = merged['Nakit Toplam'].fillna(0)
            merged['Visa Toplam'] = merged['Visa Toplam'].fillna(0)
            merged['Genel Toplam'] = merged['Nakit Toplam'] + merged['Visa Toplam']
        else:
            merged = pd.DataFrame(columns=['YTP Sicil No', 'Nakit Toplam', 'Visa Toplam', 'Genel Toplam'])
        
        # Kişisel toplamları hesapla
        kisisel_nakit_toplam = merged['Nakit Toplam'].sum()
        kisisel_visa_toplam = merged['Visa Toplam'].sum()
        
        # Genel toplam satırı (hem kişisel hem de genel toplamları içerir)
        genel_satir = pd.DataFrame([{
            'YTP Sicil No': 'Genel Toplam',
            'Nakit Toplam': kisisel_nakit_toplam + nakit_genel,
            'Visa Toplam': kisisel_visa_toplam + visa_genel,
            'Genel Toplam': kisisel_nakit_toplam + nakit_genel + kisisel_visa_toplam + visa_genel
        }])
        
        # Final tabloyu oluştur
        final = pd.concat([merged, genel_satir], ignore_index=True)
        
        # Sayısal sütunları düzenle
        for col in ['Nakit Toplam', 'Visa Toplam', 'Genel Toplam']:
            final[col] = final[col].round(2)
        
        return final
        
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        return pd.DataFrame()

def main():
    """Ana fonksiyon"""
    # Dosya yolu ve sayfa adı
    dosya_yolu = "hasilat/Hasilat_karsilastirma_sistemi_1.xlsx"
    sayfa_adi = "sistem yapılandırılmamış"
    
    print("SAP verisi işleniyor...")
    
    # SAP verisini işle
    sap_verisi = extract_sap_data(dosya_yolu, sayfa_adi)
    
    if sap_verisi.empty:
        print("Veri işlenemedi. Program sonlandırılıyor.")
        return
    
    # Sonuçları göster
    print("\n=== İşlenmiş SAP Verisi ===")
    print(sap_verisi.to_string(index=False))
    
    # Dosya adını belirle
    output_file = "SAP_Yapilandirilmis.xlsx"
    
    try:
        # Excel olarak kaydet
        sap_verisi.to_excel(output_file, index=False, engine="openpyxl")
        print(f"\n✅ Yapılandırılmış veri '{output_file}' olarak kaydedildi.")
        
        # Özet bilgi
        print(f"\n=== Özet ===")
        print(f"Toplam kişi sayısı: {len(sap_verisi) - 1}")  # Genel toplam satırını çıkar
        genel_toplam_satir = sap_verisi[sap_verisi['YTP Sicil No'] == 'Genel Toplam']
        if not genel_toplam_satir.empty:
            print(f"Toplam Nakit: {genel_toplam_satir['Nakit Toplam'].iloc[0]:.2f}")
            print(f"Toplam Visa: {genel_toplam_satir['Visa Toplam'].iloc[0]:.2f}")
            print(f"Genel Toplam: {genel_toplam_satir['Genel Toplam'].iloc[0]:.2f}")
        
    except Exception as e:
        print(f"❌ Excel dosyası kaydedilirken hata oluştu: {str(e)}")

if __name__ == "__main__":
    main()