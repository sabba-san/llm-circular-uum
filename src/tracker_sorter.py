#!/usr/bin/env python3
"""
UUM Circular & Project Document Intelligence System (Phase 1)
Automated Metadata Extractor, Classifier & Excel Tracker Generator

Authors: Ahmad Abbas & Team
Usage:
    python3 sort_tracker.py [--clean] [--output circular_Forms_tracker.xlsx] [--force-ocr]
"""

import os
import sys
import re
import json
import zipfile
import hashlib
import tempfile
import subprocess
import argparse
import xml.etree.ElementTree as ET
import xml.sax.saxutils

def find_root_dir():
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "circular_forms")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BASE_DIR = find_root_dir()
CIRCULAR_FORMS_DIR = os.path.join(BASE_DIR, "circular_forms")
DEFAULT_EXCEL_OUT = os.path.join(BASE_DIR, "circular_Forms_tracker.xlsx")
CACHE_FILE = os.path.join(BASE_DIR, ".metadata_cache.json")

DEPT_MAPPING = {
    "rmc": "Research Management Centre (RMC)",
    "bedahari": "Jabatan Bendahari",
    "bendahari": "Jabatan Bendahari",
    "icc": "Innovation and Commercialization Center (ICC)",
    "juu": "Jabatan Undang-Undang (JUU)",
}

CATEGORIES = [
    ("Procurement & Quotation", [r"perolehan", r"sebutharga", r"tender", r"pembekal", r"pesanan", r"pk\s*7", r"sebut harga"]),
    ("Travel & Mileage Claims", [r"perjalanan", r"perbatuan", r"elaun perjalanan", r"kursus dan perpindahan"]),
    ("Honorarium & Speaker Rates", [r"saguhati", r"pensyarah", r"penceramah", r"fasilitator", r"wp1\.8"]),
    ("Salary, Wages & Allowances", [r"gaji", r"upah", r"elaun", r"pembantu penyelidik", r"gra", r"pekerja sambilan", r"lebih masa"]),
    ("Asset Management & Disposal", [r"aset", r"inventori", r"lupus", r"kehilangan", r"kew\.pa", r"stok"]),
    ("Cashless & Banking Services", [r"cashless", r"tanpa tunai", r"duit now", r"duitnow", r"epay", r"kad kredit", r"kkk", r"fott", r"bank"]),
    ("Year-End Financial Procedures", [r"akhir tahun", r"penutupan akaun"]),
    ("Research Grants & Guidelines", [r"geran", r"penyelidikan", r"frgs", r"trgs", r"prgs", r"lrgs", r"satreps", r"pprn", r"dokumen 3p", r"senat"]),
    ("Consultancy & Commercialization", [r"perundingan", r"komersil", r"harta intelek", r"paten"]),
    ("Financial Governance & Policy", [r"kewangan", r"penjimatan", r"belanjawan", r"penurunan kuasa", r"akaun amanah", r"jamuan"]),
]

# Exact Form Metadata Registry
EXACT_FORM_REGISTRY = {
    # Bendahari Forms
    "1-borang-permohonan-pengesahan-kelayakan-pengecualian-cukai-s446-acp-1967-1.docx": {
        "code": "BEN-CUKAI-44",
        "title": "Borang Permohonan Pengesahan Kelayakan Pengecualian Cukai Pendapatan (S44(6) ACP 1967)",
        "dept": "Jabatan Bendahari",
        "circular": "Subseksyen 44(6) Akta Cukai Pendapatan 1967",
        "activity": "Tax Exemption Verification",
        "mandatory": "Conditional",
    },
    "Arahan_bayaran_melalui_FOTT_or_bankers_cheque_or_bank_draft.doc": {
        "code": "BEN-FOTT",
        "title": "Arahan Bayaran Melalui FOTT / Banker's Cheque / Bank Draft",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Kaedah Bayaran Luar Negara & Institusi Jabatan Bendahari",
        "activity": "Foreign / Banker's Draft Payment",
        "mandatory": "Conditional",
    },
    "BAYARAN_BULANAN_PINJAMAN_UUM_2019.pdf": {
        "code": "BEN-PINJ-JAD",
        "title": "Jadual Pengiraan Bayaran Bulanan Pinjaman UUM 2019",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Skim Pembiayaan Pinjaman Staf UUM",
        "activity": "Staff Loan Repayment Schedule",
        "mandatory": "Optional",
    },
    "BORANG PERMOHONAN PEROLEHAN TANPA PO.pdf": {
        "code": "BEN-PEROL-NOPO",
        "title": "Borang Permohonan Perolehan Tanpa Pesanan Kerajaan (PO)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perbendaharaan PK Series / Peraturan Perolehan UUM",
        "activity": "Procurement Without PO",
        "mandatory": "Conditional",
    },
    "BORANG_PENURUNAN_KUASA_KEWANGAN-20-9-2023.xlsx": {
        "code": "BEN-KUASA",
        "title": "Borang Penurunan Kuasa Kewangan Meluluskan Kertas Kerja & Perbelanjaan",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Penurunan Kuasa Kewangan Pegawai Universiti",
        "activity": "Financial Authority Delegation",
        "mandatory": "Mandatory",
    },
    "BORANG_PERMOHONAN_KOD_QR_DAN_PAUTAN_EPAY_UNIVERSITI_UTARA_MALAYSIA.docx": {
        "code": "BEN-EPAY-QR",
        "title": "Borang Permohonan Kod QR dan Pautan ePay UUM Bagi Kutipan PTJ",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 8/2023 & Bil. 6/2024 (Polisi Tanpa Tunai)",
        "activity": "Cashless & ePay Collection Setup",
        "mandatory": "Conditional",
    },
    "BORANG_PERMOHONAN_LUPUS_BARANG_TIADA_KOD_PENGENALAN_ID_1.xlsx": {
        "code": "BEN-LUPUS-NOID",
        "title": "Permohonan Pelupusan Aset Alih Yang Tiada Kod Pengenalan (ID)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Pelupusan Aset & Pengurusan Stor UUM",
        "activity": "Asset Disposal (Without ID)",
        "mandatory": "Conditional",
    },
    "BUKU_TUNAI.xls": {
        "code": "BEN-BUKU-TUNAI",
        "title": "Buku Tunai Terimaan & Bayaran (Format Rasmi)",
        "dept": "Jabatan Bendahari",
        "circular": "Arahan Perbendaharaan / Tatacara Pengurusan Wang Awam UUM",
        "activity": "Cash Book Accounting",
        "mandatory": "Mandatory",
    },
    "BorangSerahanAntaraPegawai.doc": {
        "code": "BEN-SERAH-WANG",
        "title": "Borang Serahan Wang Tunai Antara Pegawai di Jabatan",
        "dept": "Jabatan Bendahari",
        "circular": "Arahan Perbendaharaan Pengendalian Wang Tunai",
        "activity": "Cash Handover Internal",
        "mandatory": "Mandatory",
    },
    "Borang_Laporan_Kutipan_Melalui_Duit_Now.docx": {
        "code": "BEN-DUITNOW-REP",
        "title": "Borang Laporan Penyesuaian / Settlement Kutipan Melalui DuitNow",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 6/2024 (Polisi Tanpa Tunai)",
        "activity": "DuitNow Settlement Report",
        "mandatory": "Mandatory",
    },
    "Format Baru Borang Arahan Bayaran Kad Kredit Korporat.docx": {
        "code": "BEN-KKK-PAY",
        "title": "Borang Arahan Bayaran Kad Kredit Korporat (Format Baru)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 5/2026 (Panduan Kad Kredit Korporat)",
        "activity": "Corporate Credit Card Payment",
        "mandatory": "Mandatory",
    },
    "Kadar Elaun.pdf": {
        "code": "BEN-KADAR-ELN",
        "title": "Jadual Kadar Elaun Perjalanan Kenderaan, Makan dan Lojing",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 3/2023 (Pindaan Kadar Perbatuan)",
        "activity": "Travel Allowance Rate Schedule",
        "mandatory": "Optional",
    },
    "New-_Borang_Persetujuan_potongan_gaji_pembelian_telefon_melalui_pakej_celcom.doc": {
        "code": "BEN-CELCOM-POT",
        "title": "Borang Persetujuan Potongan Gaji Pembelian Telefon Pintar Melalui Pakej Celcom",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 2/2022 (Pakej Celcom Rasmi)",
        "activity": "Salary Deduction (Celcom)",
        "mandatory": "Conditional",
    },
    "PANDUAN-TUNTUTAN-PERJALANAN_terkini.pdf": {
        "code": "BEN-TRV-GUIDE",
        "title": "Panduan Tuntutan Perjalanan Rasmi, Berkursus, Bertukar & Berpindah (Terkini)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 3/2023 & Garis Panduan Tuntutan Rasmi",
        "activity": "Travel Claim Instructions",
        "mandatory": "Mandatory",
    },
    "PANDUAN_PINJAMAN_KENDERAAN_2019.pdf": {
        "code": "BEN-PINJ-KDRN",
        "title": "Panduan & Borang Permohonan Pembiayaan Membeli Kenderaan Staf UUM",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Skim Pembiayaan Pinjaman Kenderaan Staf UUM",
        "activity": "Vehicle Financing Application",
        "mandatory": "Conditional",
    },
    "PANDUAN_PINJAMAN_KOMPUTER_DAN_TELEFON_PINTAR_2019.pdf": {
        "code": "BEN-PINJ-IT",
        "title": "Panduan & Borang Permohonan Pembiayaan Komputer dan Telefon Pintar",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Skim Pembiayaan Komputer & Telefon Pintar",
        "activity": "IT Device Financing Application",
        "mandatory": "Conditional",
    },
    "PEMBUKAAN_AKAUN_-_Borang__Lampiran_PA1_1.docx": {
        "code": "BEN-PA1",
        "title": "Borang Permohonan Membuka Akaun Amanah / Projek (Lampiran PA1)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Akaun Amanah & Dokumen 3P UUM",
        "activity": "Trust / Project Account Setup",
        "mandatory": "Mandatory",
    },
    "PERMOHONAN PEROLEHAN- INTERNET.doc": {
        "code": "BEN-PEROL-NET",
        "title": "Borang Permohonan Perolehan Barangan / Perkhidmatan Melalui Internet",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perolehan Melalui Internet UUM",
        "activity": "Internet Procurement Approval",
        "mandatory": "Conditional",
    },
    "ZAKATA.pdf": {
        "code": "BEN-ZAKAT",
        "title": "Borang Kebenaran Potongan Gaji Zakat Pendapatan UUM",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Urusan Gaji & Potongan Zakat Kakitangan",
        "activity": "Zakat Salary Deduction",
        "mandatory": "Conditional",
    },
    "borang elaun lebih masa.pdf": {
        "code": "BEN-ELN-OT",
        "title": "Borang Tuntutan Bayaran Elaun Kerja Lebih Masa (OT)",
        "dept": "Jabatan Bendahari",
        "circular": "Perintah Am Bab B & Pekeliling Gaji Kakitangan",
        "activity": "Overtime Allowance Claim",
        "mandatory": "Conditional",
    },
    "borang-penilaian-prestasi-pembekal-protected-version-2-9-2024.xlsx": {
        "code": "BEN-PRESTASI-SUP",
        "title": "Borang Penilaian Prestasi Pembekal / Kontraktor UUM (Pindaan 2024)",
        "dept": "Jabatan Bendahari",
        "circular": "1Pekeliling Perbendaharaan PK Series (Perolehan Kerajaan)",
        "activity": "Supplier Performance Evaluation",
        "mandatory": "Mandatory",
    },
    "borang-permohonan-capaian-sistem-kewangan-8-5-2025-7.xlsx": {
        "code": "BEN-SYS-ACC",
        "title": "Borang Permohonan Capaian Sistem Maklumat Kewangan UUM (FIS)",
        "dept": "Jabatan Bendahari",
        "circular": "Dasar Keselamatan ICT & Pekeliling Capaian Sistem Kewangan",
        "activity": "Financial System User Access",
        "mandatory": "Conditional",
    },
    "borang-serahan-harian-kutipan-kad-kredit-2.docx": {
        "code": "BEN-SERAH-KK",
        "title": "Borang Serahan Harian / Settlement Kutipan Kad Kredit & Debit PTJ",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 6/2024 (Polisi Tanpa Tunai)",
        "activity": "Card Collection Daily Settlement",
        "mandatory": "Mandatory",
    },
    "borang-tuntutan-gaji-pekerja-sambilan-4-1.pdf": {
        "code": "BEN-GAJI-SAMBIL",
        "title": "Borang Tuntutan Gaji Pekerja Sambilan Harian (PSH)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perkhidmatan & Kadar Upah Pekerja Sambilan UUM",
        "activity": "Part-time Worker Wage Claim",
        "mandatory": "Mandatory",
    },
    "borang_arahan_pengeluaran_invois-updated-181124.xls": {
        "code": "BEN-INV-REQ",
        "title": "Borang Arahan Pengeluaran Invois Kepada Pihak Luar (Kemaskini Nov 2024)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 8/2026 (Pengkelasan Hasil UUM)",
        "activity": "External Invoice Issuance",
        "mandatory": "Mandatory",
    },
    "borang_permintaan pesanan.doc": {
        "code": "BEN-REQ-ORDER",
        "title": "Borang Permintaan Pesanan Tempatan / Belian Barangan",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perolehan Jabatan Bendahari",
        "activity": "Local Purchase Requisition",
        "mandatory": "Mandatory",
    },
    "borang_tuntutan_pembiayaan_alat_komunikasi.pdf": {
        "code": "BEN-KOM-CLAIM",
        "title": "Borang Tuntutan Bantuan Pembelian Alat Komunikasi Mudah Alih (Lampiran A)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Bendahari Bil. 2/2022 (Pindaan Elaun Telefon Bimbit)",
        "activity": "Mobile Phone Subsidy Claim",
        "mandatory": "Conditional",
    },
    "borangfotostat.doc": {
        "code": "BEN-SEWA-FOTO",
        "title": "Borang Permohonan Untuk Menyewa Mesin Fotostat PTJ",
        "dept": "Jabatan Bendahari",
        "circular": "Garis Panduan Penjimatan Perbelanjaan Awam",
        "activity": "Photostat Machine Lease Approval",
        "mandatory": "Conditional",
    },
    "brg arahan bayaran.doc": {
        "code": "BEN-ARAH-BAYAR",
        "title": "Borang Penghantaran Bil / Arahan Bayaran (Invois / Tuntutan)",
        "dept": "Jabatan Bendahari",
        "circular": "Arahan Perbendaharaan Prosedur Bayaran Bil",
        "activity": "Bill Payment Voucher Submission",
        "mandatory": "Mandatory",
    },
    "brgmaklumatakaun.doc": {
        "code": "BEN-EFT-VEND",
        "title": "Borang Maklumat Akaun Bank Penerima Bayaran EFT (Syarikat / Individu)",
        "dept": "Jabatan Bendahari",
        "circular": "Tatacara Bayaran Secara Electronic Fund Transfer (EFT)",
        "activity": "Vendor / Payee Bank EFT Setup",
        "mandatory": "Mandatory",
    },
    "kewpa-34---format-surat-lantikan-jawatankuasa-penyiasat-kehilangan-aset-alih.pdf": {
        "code": "KEW.PA-34",
        "title": "KEW.PA-34: Format Surat Pelantikan Jawatankuasa Penyiasat Kehilangan Aset",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perbendaharaan Tatacara Pengurusan Aset Alih (AM 2.8)",
        "activity": "Asset Loss Investigation Committee",
        "mandatory": "Mandatory",
    },
    "lampiran-l---laporan-awal-kehilangan-new-format-kewpa33.docx": {
        "code": "KEW.PA-33",
        "title": "KEW.PA-33: Laporan Awal Kehilangan Aset Alih Kerajaan (Lampiran L)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perbendaharaan Tatacara Pengurusan Aset Alih (AM 2.8)",
        "activity": "Asset Loss Initial Incident Report",
        "mandatory": "Mandatory",
    },
    "lampiran-m---laporan-akhir-kehilangan-new.docx": {
        "code": "KEW.PA-35",
        "title": "KEW.PA-35: Laporan Akhir Kehilangan Aset Alih Kerajaan (Lampiran M)",
        "dept": "Jabatan Bendahari",
        "circular": "Pekeliling Perbendaharaan Tatacara Pengurusan Aset Alih (AM 2.8)",
        "activity": "Asset Loss Final Investigation Report",
        "mandatory": "Mandatory",
    },
    "latestclaimform1.xls": {
        "code": "BEN-TUNTUT-GEN",
        "title": "Borang Tuntutan Pelbagai Perbelanjaan Rasmi (General Claim Form)",
        "dept": "Jabatan Bendahari",
        "circular": "Garis Panduan Tuntutan Perbelanjaan Rasmi Kakitangan",
        "activity": "General Official Expense Claim",
        "mandatory": "Mandatory",
    },
    "permohonan bayar balik.doc": {
        "code": "BEN-REFUND",
        "title": "Borang Permohonan Bayaran Balik Yuran / Lebihan Bayaran",
        "dept": "Jabatan Bendahari",
        "circular": "Tatacara Bayaran Balik Hasil Universiti",
        "activity": "Fee Refund Request",
        "mandatory": "Conditional",
    },
    "stor--borang-permohonan-pembelian-stok-2.docx": {
        "code": "BEN-STOR-STOK",
        "title": "Borang Permohonan Pembelian Stok / Bekalan Stor PTJ",
        "dept": "Jabatan Bendahari",
        "circular": "Tatacara Pengurusan Stor Kerajaan (TPS)",
        "activity": "Store Stock Requisition",
        "mandatory": "Mandatory",
    },
    "template-cvp.xlsx": {
        "code": "BEN-TEMPL-CVP",
        "title": "Templat Analisis Kos-Volum-Untung (Cost-Volume-Profit Analysis Template)",
        "dept": "Jabatan Bendahari",
        "circular": "Garis Panduan Perundingan & Penetapan Yuran Kursus/Seminar",
        "activity": "Financial CVP Modeling",
        "mandatory": "Optional",
    },
    "template-procost.zip": {
        "code": "BEN-TEMPL-PROCOST",
        "title": "Pakej Templat Pengiraan Kos Projek (Project Costing Templates)",
        "dept": "Jabatan Bendahari",
        "circular": "Garis Panduan Pengurusan Projek & Perundingan UUM",
        "activity": "Project Costing Modeling",
        "mandatory": "Optional",
    },

    # RMC Forms
    "BORANG PENERIMAAN ASET_PINDAAN 15 MEI 2025.docx": {
        "code": "RMC-ASET-TERIMA",
        "title": "Borang Penerimaan Aset & Inventori Penyelidikan (Pindaan Mei 2025)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) / Tatacara Pengurusan Aset RMC",
        "activity": "Research Asset Acceptance",
        "mandatory": "Mandatory",
    },
    "Borang_Pendaftaran_Projek_Penyelidikan_dalam_RaIIS__2_2_2026.docx": {
        "code": "RMC 001",
        "title": "Borang Permohonan Pendaftaran Projek Penyelidikan Dalam Sistem RaIIS (RMC 001)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Garis Panduan Pengurusan Penyelidikan",
        "activity": "Research Project Registration",
        "mandatory": "Mandatory",
    },
    "Borang_Pendaftaran_Projek_Perundingan_dalam_RaIIS__13_JAN_2026.docx": {
        "code": "RMC-CONS-01",
        "title": "Borang Permohonan Pendaftaran Projek Perundingan Dalam Sistem RaIIS",
        "dept": "Research Management Centre (RMC)",
        "circular": "Garis Panduan Perundingan Universiti Utara Malaysia 2024",
        "activity": "Consultancy Project Registration",
        "mandatory": "Mandatory",
    },
    "Borang_Perakuan_Tamat_Penyelidikan_Updated_2Mei2025.docx": {
        "code": "RMC-TAMAT",
        "title": "Senarai Semak & Borang Perakuan Tamat Penyelidikan (Pindaan Mei 2025)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Prosedur Penutupan Projek",
        "activity": "Research Project Closeout",
        "mandatory": "Mandatory",
    },
    "Borang_Permohonan_Belian_Perolehan_Penyelidikan_Perundingan.docx": {
        "code": "RMC 023",
        "title": "Borang Permohonan Perolehan Aset & Inventori Penyelidikan / Perundingan (RMC 023)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Panduan Kod Perbelanjaan & Dokumen 3P UUM",
        "activity": "Research Equipment Procurement",
        "mandatory": "Mandatory",
    },
    "Borang_RMC012-Borang_Permohonan_Pindaan_Vot_Pindaan_29.12.2021.docx": {
        "code": "RMC 012",
        "title": "Borang Permohonan Pindaan Vot Geran Penyelidikan (RMC 012)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) & Panduan Kod Perbelanjaan Penyelidikan",
        "activity": "Grant Vote Amendment (Virement)",
        "mandatory": "Mandatory",
    },
    "Borang_RMC021_Borang_Permohonan_Pertukaran_Ketua_Penambahan_dan_Pengguguran_Tarik_Diri_Ahli_Penyelidik_Pindaan_29.12.2021.docx": {
        "code": "RMC 021",
        "title": "Borang Permohonan Pertukaran Ketua / Ahli Penyelidik (RMC 021)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Perubahan Keahlian Projek",
        "activity": "Research Team Member Change",
        "mandatory": "Conditional",
    },
    "Borang_RMC_013_Perakuan_Penerimaan_Bayaran.docx": {
        "code": "RMC 013",
        "title": "Borang Perakuan Penerimaan Bayaran Saguhati / Upah Responden (RMC 013)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) & Panduan Kod Perbelanjaan Penyelidikan",
        "activity": "Respondent / Fieldwork Honorarium",
        "mandatory": "Mandatory",
    },
    "Borang_Tuntutan_Perbelanjaan_Penyelidkan_RIMC_Pindaan_Mac_2023(1).xlsx - BORANG.pdf": {
        "code": "RMC-TUNTUT-VOT",
        "title": "Panduan Potongan Vot & Borang Tuntutan Perbelanjaan Penyelidikan RMC",
        "dept": "Research Management Centre (RMC)",
        "circular": "Panduan Kod Perbelanjaan bagi Geran Penyelidikan",
        "activity": "Research Expense Claim by Vote",
        "mandatory": "Mandatory",
    },
    "Borang_Tuntutan_Perjalanan_2024(1).xlsx - Sheet1.pdf": {
        "code": "BEN-TRV-RMC",
        "title": "Borang Tuntutan Perjalanan, Kursus dan Perpindahan (Kegunaan Penyelidikan)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Pekeliling Bendahari Bil. 3/2023 & Dokumen 3P UUM",
        "activity": "Research Fieldwork Travel Claim",
        "mandatory": "Mandatory",
    },
    "Borang_tuntutan_gaji_pembantu_new_form_2023(1).docx": {
        "code": "RIMC 016",
        "title": "Borang Tuntutan Elaun Pembantu Penyelidik / RA (RIMC 016)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Prosedur Pelantikan RA/GRA",
        "activity": "RA Allowance Monthly Claim",
        "mandatory": "Mandatory",
    },
    "FORMAT_LAPORAN_AKHIR.pdf": {
        "code": "RMC-REP-FINAL",
        "title": "Format & Panduan Penyediaan Laporan Akhir Projek Penyelidikan",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Laporan Akhir Projek",
        "activity": "Final Research Reporting",
        "mandatory": "Mandatory",
    },
    "RMC006_Borang_Permohonan_Lanjut_Masa_Pindaan_1_Ogos_2023.docx": {
        "code": "RMC 006",
        "title": "Senarai Semak & Borang Permohonan Lanjutan Tempoh Penyelidikan (RMC 006)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Lanjutan Tempoh Projek",
        "activity": "Research Extension Request",
        "mandatory": "Conditional",
    },
    "RMC019-Borang_Permohonan_Menjalankan_Aktiviti_Penyelidikan_atau_Perundingan_Menggunakan_Peruntukan_Penyelidikan_atau_Perundingan_pindaan_16_Mac_2023.docx": {
        "code": "RMC 019",
        "title": "Borang Permohonan Menjalankan Aktiviti Penyelidikan / Perundingan (RMC 019)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) & Garis Panduan Perundingan UUM 2024",
        "activity": "Workshop / Fieldwork Approval",
        "mandatory": "Mandatory",
    },
    "RMC_008_Borang_Permohonan_RA_GRA_01122022.docx": {
        "code": "RMC 008",
        "title": "Senarai Semak & Borang Permohonan Lantikan Baru RA / GRA (RMC 008)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Pelantikan Pembantu Penyelidik",
        "activity": "RA / GRA Appointment Checklist",
        "mandatory": "Mandatory",
    },
    "Templat_Laporan_Teknikal_atau_Buku_Profil_Penyelidikan_Kemaskini_29.12.21.doc": {
        "code": "RMC-REP-TECH",
        "title": "Templat Laporan Teknikal / Buku Profil Penyelidikan (Pindaan 2021)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Dokumen 3P (Senat 326) - Penerbitan & Profil Penyelidikan",
        "activity": "Technical Report / Profile Book",
        "mandatory": "Optional",
    },
    "Website RMC_Perhatian Penyelidik.pdf": {
        "code": "RMC-NOTICE-CLAIM",
        "title": "Panduan & Perhatian Penyelidik Bagi Urusan Tuntutan Perbelanjaan RMC",
        "dept": "Research Management Centre (RMC)",
        "circular": "Garis Panduan Pengurusan Kewangan Penyelidikan RMC",
        "activity": "Research Claim Compliance Notice",
        "mandatory": "Optional",
    },
    "brgmaklumatakaun individu.docx": {
        "code": "BEN-EFT-IND-RMC",
        "title": "Borang Maklumat Akaun Bank Penerima Bayaran EFT (Individu)",
        "dept": "Jabatan Bendahari",
        "circular": "Tatacara Bayaran Secara Electronic Fund Transfer (EFT)",
        "activity": "Individual Bank EFT Setup",
        "mandatory": "Mandatory",
    },
    "brgmaklumatakaun_syarikat - HOTEL.doc": {
        "code": "BEN-EFT-HOTEL",
        "title": "Borang Maklumat Akaun Bank Penerima Bayaran EFT (Syarikat / Hotel)",
        "dept": "Jabatan Bendahari",
        "circular": "Tatacara Bayaran Secara Electronic Fund Transfer (EFT)",
        "activity": "Vendor / Hotel Bank EFT Setup",
        "mandatory": "Mandatory",
    },
    "Borang Permohonan Geran Universiti.docx": {
        "code": "RMC-APP-GU",
        "title": "Borang Permohonan Geran Penyelidikan Universiti (University Grant Application)",
        "dept": "Research Management Centre (RMC)",
        "circular": "Garis Panduan Geran Universiti UUM",
        "activity": "University Grant Application",
        "mandatory": "Mandatory",
    },
}

def clean_artifacts(root_dir):
    """Clean Windows metadata stream artifacts and desktop.ini files."""
    cleaned = 0
    for root, _, files in os.walk(root_dir):
        for f in files:
            if ":Zone.Identifier" in f or f.lower() == "desktop.ini":
                try:
                    os.remove(os.path.join(root, f))
                    cleaned += 1
                except OSError:
                    pass
    return cleaned

def compute_md5(filepath):
    """Compute MD5 hash to detect duplicate files."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def extract_text_from_pdf(filepath, use_ocr=True):
    """Extract text from PDF using pdftotext, fallback to pdfimages + tesseract for scanned documents."""
    text = ""
    try:
        res = subprocess.run(["pdftotext", "-f", "1", "-l", "3", filepath, "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        text = res.stdout.decode("utf-8", errors="ignore").strip()
    except Exception:
        pass

    if len(text) < 50 and use_ocr:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                img_prefix = os.path.join(tmpdir, "p1")
                subprocess.run(["pdfimages", "-png", "-f", "1", "-l", "1", filepath, img_prefix], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                imgs = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".png")]
                if imgs:
                    ocr_out = os.path.join(tmpdir, "ocr")
                    subprocess.run(["tesseract", imgs[0], ocr_out], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.path.exists(ocr_out + ".txt"):
                        with open(ocr_out + ".txt", "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read().strip()
        except Exception:
            pass

    return text

def extract_text_from_docx(filepath):
    """Extract text from .docx file via zipfile and ElementTree."""
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        texts = []
        for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            t = "".join(n.text for n in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if n.text)
            if t.strip():
                texts.append(t.strip())
        return "\n".join(texts)
    except Exception:
        return ""

def extract_text_from_doc(filepath):
    """Extract readable text strings from legacy .doc or .xls file."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        words = re.findall(rb"[\x20-\x7E]{4,}", data)
        return "\n".join(w.decode("latin1", errors="ignore").strip() for w in words if len(w.strip()) > 3)
    except Exception:
        return ""

def extract_text_from_xlsx(filepath):
    """Extract strings from .xlsx file."""
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "xl/sharedStrings.xml" in z.namelist():
                sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
                texts = []
                for si in sst.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    t = "".join(n.text for n in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") if n.text)
                    if t.strip():
                        texts.append(t.strip())
                return "\n".join(texts)
    except Exception:
        pass
    return ""

def clean_title_text(t):
    """Clean extra spaces, commas, and normalize casing for titles."""
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    # Remove leading colons or punctuation
    t = re.sub(r"^[:\-\s]+", "", t)
    # If entirely uppercase, convert to title case
    if t.isupper() and len(t) > 10:
        t = t.title()
    return t

def parse_circular_metadata(filename, filepath, raw_text, dept_key):
    """Extract structured metadata from circular text and filename."""
    dept_name = DEPT_MAPPING.get(dept_key.lower(), dept_key.upper())

    # 1. Parse Reference Number
    ref_no = ""
    m_ref = re.search(r"(PEKELILING\s+(?:BENDAHARI\s+)?BIL\.?\s*[\d\w\/\.\-]+(?:\s*TAHUN\s*\d{4})?)", raw_text, re.IGNORECASE)
    if m_ref:
        ref_no = " ".join(m_ref.group(1).split())
    elif "senat 326" in filename.lower() or "senat 326" in raw_text.lower():
        ref_no = "Kelulusan Senat 326"
    elif "senat" in filename.lower() or "senat" in raw_text.lower():
        m_s = re.search(r"Senat\s*(\d+)", filename + " " + raw_text, re.IGNORECASE)
        ref_no = f"Kelulusan Senat {m_s.group(1)}" if m_s else "Senat UUM"
    elif "pk 7.1" in filename.lower() or "pk 7.1" in raw_text.lower():
        ref_no = "1Pekeliling Perbendaharaan PK 7.1"
    elif "pk 7.5" in filename.lower() or "pk 7.5" in raw_text.lower():
        ref_no = "1Pekeliling Perbendaharaan PK 7.5"
    elif "kjp" in filename.lower():
        ref_no = "Kementerian Ekonomi Bil 1/2024 (KJP)"
    elif "frgs" in filename.lower():
        ref_no = "KPT FRGS 2025"
    elif "trgs" in filename.lower():
        ref_no = "KPT TRGS-SF 2024"
    elif "prgs" in filename.lower():
        ref_no = "KPT PRGS 2025"
    elif "pprn" in filename.lower():
        ref_no = "PPRN 2.0 (Pindaan 2025)"
    elif "satreps" in filename.lower():
        ref_no = "SATREPS FY2026"
    elif "dsrg" in filename.lower():
        ref_no = "MCMC DSRG 2025"

    # Fallback to filename patterns
    if not ref_no or len(ref_no) < 4:
        m_fn = re.search(r"(?:pekeliling[-_ ]bend(?:ahari)?[-_ ]bil[-_ ]*|pb[-_ ]*)([\d\.\-\/]+)[-_ ](\d{4})", filename, re.IGNORECASE)
        if m_fn:
            ref_no = f"Pekeliling Bendahari Bil. {m_fn.group(1)}/{m_fn.group(2)}"
        elif re.match(r"^\d{4}-\d+", filename):
            parts = filename.replace(".pdf", "").split("-")
            ref_no = f"Pekeliling Bendahari Bil. {int(parts[1])}/{parts[0]}"
        elif re.match(r"^\d+-\d{4}", filename):
            parts = filename.replace(".pdf", "").split("-")
            ref_no = f"Pekeliling Bendahari Bil. {parts[0]}/{parts[1]}"
        elif "panduan perundingan" in filename.lower():
            ref_no = "UUM/RMC/2024"
        elif "panduan perolehan sebutharga" in filename.lower():
            ref_no = "UUM Sebutharga 2024"
        else:
            ref_no = os.path.splitext(filename)[0].replace("_", " ").title()

    # 2. Extract Date & Year
    effective_date = ""
    year = ""
    m_date = re.search(r"(\d{1,2}\s+(?:Januari|Februari|Mac|April|Mei|Jun|Julai|Ogos|September|Oktober|November|Disember|January|February|March|May|June|July|August|October|December)\s+20\d\d)", raw_text, re.IGNORECASE)
    if m_date:
        effective_date = m_date.group(1).strip()
        m_yr = re.search(r"20\d\d", effective_date)
        if m_yr:
            year = m_yr.group(0)

    if not year:
        m_all_yr = re.findall(r"20\d\d", filename + " " + raw_text)
        if m_all_yr:
            year = m_all_yr[0]
            effective_date = year
        else:
            # Check 2-digit year in filename like _26 or 13-2009
            m_short = re.search(r"[-_](2[0-6])\.pdf", filename)
            if m_short:
                year = "20" + m_short.group(1)
                effective_date = year
            else:
                year = "Unknown"
                effective_date = "Unknown"

    # 3. Extract Title
    title = ""
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    for i, line in enumerate(lines[:35]):
        if re.search(r"(Dato\'|Prof\.|Tuan\/Puan|Dato\/Tuan\/Puan)", line, re.IGNORECASE):
            sub_lines = [l for l in lines[i+1:i+5] if not l.startswith("Dengan ") and not l.startswith("Merujuk ") and len(l) > 3]
            if sub_lines:
                title = " ".join(sub_lines[:2])
            break
        elif re.search(r"^(TAJUK|PERKARA|SUBJECT)\s*[:\-]", line, re.IGNORECASE):
            title = re.sub(r"^(TAJUK|PERKARA|SUBJECT)\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
            break

    # If title not found or short, infer from filename
    if not title or len(title) < 8:
        clean_name = os.path.splitext(filename)[0]
        clean_name = re.sub(r"^[0-9\-_]+", "", clean_name)
        clean_name = re.sub(r"pekeliling[-_ ]bendahari[-_ ]bil\.?[-_ ]*[\d\.\-_/]+", "", clean_name, flags=re.IGNORECASE)
        clean_name = clean_name.replace("-", " ").replace("_", " ").strip()
        title = clean_name if len(clean_name) > 6 else os.path.splitext(filename)[0].replace("_", " ")

    title = clean_title_text(title)

    # 4. Determine Category
    category = "Financial Governance & Policy"
    text_corpus = (filename + " " + title + " " + raw_text[:400]).lower()
    for cat_name, patterns in CATEGORIES:
        if any(re.search(p, text_corpus) for p in patterns):
            category = cat_name
            break

    # 5. Lifecycle Status (Active vs Superseded)
    status = "Active"
    supersedes = ""
    if "gaji" in text_corpus:
        if year != "2026" and year != "2025" and year != "Unknown":
            status = "Superseded"
            supersedes = f"Tarikh Pembayaran Gaji {int(year)-1}" if year.isdigit() else ""
    elif "akhir tahun" in text_corpus:
        if year != "2026" and year != "Unknown":
            status = "Superseded"
            supersedes = f"Urusan Akhir Tahun {int(year)-1}" if year.isdigit() else ""
    elif "perbatuan" in text_corpus or "kadar elaun" in text_corpus:
        if year and year.isdigit() and int(year) < 2023:
            status = "Superseded"
    elif "penyelidik muda" in text_corpus:
        if year == "2025":
            status = "Superseded"
            supersedes = "Garis Panduan Penyelidikan Penyelidik Muda 2024"
    elif "pprn" in text_corpus and "bil 1" in filename.lower():
        status = "Superseded"

    # 6. Attached / Required Forms
    req_forms = []
    form_matches = re.findall(r"(RMC\s*\d+|KEW\.PA[\-\s]*\d+|BORANG\s+[A-Z0-9\-_]+)", raw_text[:1200], re.IGNORECASE)
    for fm in form_matches:
        fm_clean = " ".join(fm.split()).upper()
        if fm_clean not in req_forms and len(fm_clean) > 4:
            req_forms.append(fm_clean)

    if not req_forms:
        if "perjalanan" in text_corpus or "perbatuan" in text_corpus:
            req_forms.append("Borang Tuntutan Perjalanan (Terkini)")
        elif "saguhati" in text_corpus or "wp1.8" in text_corpus:
            req_forms.append("Borang Tuntutan Bayaran Saguhati Pensyarah/Penceramah")
        elif "dokumen 3p" in text_corpus or "senat 326" in text_corpus:
            req_forms.append("RMC 001, RMC 006, RMC 008, RMC 012, RMC 016, RMC 019, RMC 021, RMC 023, Borang Perakuan Tamat")
        elif "geran" in text_corpus:
            req_forms.append("Borang Permohonan Geran, RMC 001")
        elif "perundingan" in text_corpus:
            req_forms.append("Borang Pendaftaran Perundingan RaIIS, RMC 019")
        elif "kad kredit" in text_corpus or "kkk" in text_corpus:
            req_forms.append("Borang Arahan Bayaran Kad Kredit Korporat")

    return {
        "ref_no": ref_no,
        "title": title,
        "department": dept_name,
        "category": category,
        "effective_date": effective_date,
        "year": year,
        "status": status,
        "supersedes": supersedes,
        "required_forms": ", ".join(req_forms) if req_forms else "-",
        "filename": filename,
        "filepath": filepath,
    }

def parse_form_metadata(filename, filepath, raw_text, dept_key):
    """Extract metadata for official forms and templates."""
    dept_name = DEPT_MAPPING.get(dept_key.lower(), dept_key.upper())
    ext = os.path.splitext(filename)[1].lower()

    # Check exact registry first
    if filename in EXACT_FORM_REGISTRY:
        info = EXACT_FORM_REGISTRY[filename]
        return {
            "form_code": info["code"],
            "title": info["title"],
            "department": info["dept"],
            "related_circular": info["circular"],
            "activity_type": info["activity"],
            "is_mandatory": info["mandatory"],
            "filename": filename,
            "filepath": filepath,
            "format": ext.replace(".", "").upper(),
            "notes": f"Standard UUM template ({ext.replace('.', '').upper()})",
        }

    # Fallback heuristic
    form_code = os.path.splitext(filename)[0][:18].replace("_", " ").title()
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

    return {
        "form_code": form_code,
        "title": title,
        "department": dept_name,
        "related_circular": "Dokumen 3P / Pekeliling Bendahari",
        "activity_type": "Administrative / Financial",
        "is_mandatory": "Mandatory",
        "filename": filename,
        "filepath": filepath,
        "format": ext.replace(".", "").upper(),
        "notes": f"Standard UUM template ({ext.replace('.', '').upper()})",
    }

class ExcelWriter:
    """Creates a standards-compliant OpenXML (.xlsx) file without external dependencies."""

    @staticmethod
    def escape_xml(s):
        return xml.sax.saxutils.escape(str(s if s is not None else ""))

    @classmethod
    def write_workbook(cls, out_path, sheet1_name, sheet1_headers, sheet1_rows, sheet2_name, sheet2_headers, sheet2_rows):
        shared_strings = []
        string_map = {}

        def get_str_id(val):
            s = str(val if val is not None else "")
            if s not in string_map:
                string_map[s] = len(shared_strings)
                shared_strings.append(s)
            return string_map[s]

        def build_sheet_xml(headers, rows):
            cols_xml = "<cols>"
            for i in range(1, len(headers) + 1):
                max_len = len(headers[i - 1])
                for r in rows:
                    if i - 1 < len(r):
                        max_len = max(max_len, len(str(r[i - 1])))
                width = min(max(max_len + 3, 14), 55)
                cols_xml += f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
            cols_xml += "</cols>"

            sheet_data = "<sheetData>"
            sheet_data += f'<row r="1" spans="1:{len(headers)}">'
            for c_idx, h in enumerate(headers, 1):
                col_letter = chr(64 + c_idx) if c_idx <= 26 else f"A{chr(64 + c_idx - 26)}"
                s_id = get_str_id(h)
                sheet_data += f'<c r="{col_letter}1" t="s" s="1"><v>{s_id}</v></c>'
            sheet_data += "</row>"

            for r_idx, row in enumerate(rows, 2):
                sheet_data += f'<row r="{r_idx}" spans="1:{len(headers)}">'
                for c_idx, val in enumerate(row, 1):
                    col_letter = chr(64 + c_idx) if c_idx <= 26 else f"A{chr(64 + c_idx - 26)}"
                    s_id = get_str_id(val)
                    sheet_data += f'<c r="{col_letter}{r_idx}" t="s"><v>{s_id}</v></c>'
                sheet_data += "</row>"
            sheet_data += "</sheetData>"

            last_col = chr(64 + len(headers)) if len(headers) <= 26 else f"A{chr(64 + len(headers) - 26)}"
            auto_filter = f'<autoFilter ref="A1:{last_col}{max(len(rows) + 1, 1)}"/>'

            return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
{cols_xml}
{sheet_data}
{auto_filter}
</worksheet>"""

        sheet1_xml = build_sheet_xml(sheet1_headers, sheet1_rows)
        sheet2_xml = build_sheet_xml(sheet2_headers, sheet2_rows)

        sst_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">"""
        for s in shared_strings:
            sst_xml += f"<si><t>{cls.escape_xml(s)}</t></si>"
        sst_xml += "</sst>"

        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

        wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

        wb_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
<sheet name="{sheet1_name}" sheetId="1" r:id="rId1"/>
<sheet name="{sheet2_name}" sheetId="2" r:id="rId2"/>
</sheets>
</workbook>"""

        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/><color rgb="FF000000"/></font>
<font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD3D3D3"/></left><right style="thin"><color rgb="FFD3D3D3"/></right><top style="thin"><color rgb="FFD3D3D3"/></top><bottom style="thin"><color rgb="FFD3D3D3"/></bottom></border>
</borders>
<cellStyleXfs count="1">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
</cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
</cellXfs>
</styleSheet>"""

        if os.path.exists(out_path):
            backup_path = out_path + ".bak"
            try:
                import shutil
                shutil.copy2(out_path, backup_path)
            except Exception:
                pass

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
            z.writestr("xl/workbook.xml", wb_xml)
            z.writestr("xl/styles.xml", styles_xml)
            z.writestr("xl/sharedStrings.xml", sst_xml)
            z.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
            z.writestr("xl/worksheets/sheet2.xml", sheet2_xml)

def process_all_documents(use_ocr=True, force_ocr=False):
    """Scan and process all documents across all departments."""
    cache = {}
    if os.path.exists(CACHE_FILE) and not force_ocr:
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    circulars = []
    forms = []
    seen_hashes = {}
    duplicates = []

    ptj_folders = [
        ("Bedahari", "02_Circulars", "circular"),
        ("Bedahari", "02_forms", "form"),
        ("RMC", "01_Circulars", "circular"),
        ("RMC", "01_Forms", "form"),
        ("ICC", "03_Circulars", "circular"),
        ("ICC", "03_forms", "form"),
        ("JUU", "04_circulars", "circular"),
        ("JUU", "04_forms", "form"),
    ]

    print("[*] Scanning circular_forms directories...")

    for dept, folder, doc_type in ptj_folders:
        dir_path = os.path.join(CIRCULAR_FORMS_DIR, dept, folder)
        if not os.path.exists(dir_path):
            continue

        files = sorted(os.listdir(dir_path))
        for filename in files:
            if filename.startswith(".") or ":Zone.Identifier" in filename or filename.lower() == "desktop.ini":
                continue

            filepath = os.path.join(dir_path, filename)
            if not os.path.isfile(filepath):
                continue

            # Check duplicate hash
            file_hash = compute_md5(filepath)
            if file_hash in seen_hashes:
                duplicates.append((filename, seen_hashes[file_hash]))
                continue
            seen_hashes[file_hash] = filepath

            cached_meta = cache.get(filepath)
            raw_text = ""
            if cached_meta:
                raw_text = cached_meta.get("raw_text", "")
            else:
                ext = os.path.splitext(filename)[1].lower()
                if ext == ".pdf":
                    raw_text = extract_text_from_pdf(filepath, use_ocr=use_ocr)
                elif ext == ".docx":
                    raw_text = extract_text_from_docx(filepath)
                elif ext in [".doc", ".xls"]:
                    raw_text = extract_text_from_doc(filepath)
                elif ext == ".xlsx":
                    raw_text = extract_text_from_xlsx(filepath)

                cache[filepath] = {"raw_text": raw_text[:3000], "hash": file_hash}

            # Check if this is a form
            is_form = (doc_type == "form") or ("borang permohonan geran universiti" in filename.lower())

            if is_form:
                meta = parse_form_metadata(filename, os.path.relpath(filepath, BASE_DIR), raw_text, dept)
                forms.append(meta)
            else:
                meta = parse_circular_metadata(filename, os.path.relpath(filepath, BASE_DIR), raw_text, dept)
                circulars.append(meta)

    # Save cache
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

    # Sort Circulars: Department ASC, Status (Active first), Category ASC, Date/Year DESC
    def circ_sort_key(c):
        status_rank = 0 if c["status"] == "Active" else 1
        year_val = int(c["year"]) if c["year"].isdigit() else 0
        return (c["department"], status_rank, c["category"], -year_val, c["ref_no"])

    circulars.sort(key=circ_sort_key)

    for idx, c in enumerate(circulars, 1):
        c_code = "BEN" if "Bendahari" in c["department"] else ("RMC" if "RMC" in c["department"] else "CIRC")
        c["id"] = f"CIRC-{c_code}-{idx:03d}"

    # Sort Forms: Department ASC, Activity Type ASC, Form Code ASC
    def form_sort_key(f):
        return (f["department"], f["activity_type"], f["form_code"])

    forms.sort(key=form_sort_key)

    for idx, f in enumerate(forms, 1):
        f_code = "BEN" if "Bendahari" in f["department"] else ("RMC" if "RMC" in f["department"] else "FORM")
        f["id"] = f"FORM-{f_code}-{idx:03d}"

    return circulars, forms, duplicates

def main():
    parser = argparse.ArgumentParser(description="UUM Circular & Form Master Tracker Auto-Sorter")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean Windows artifact files before processing")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for scanned PDFs")
    parser.add_argument("--force-ocr", action="store_true", help="Force re-extraction ignoring cache")
    parser.add_argument("--output", default=DEFAULT_EXCEL_OUT, help="Path for output Excel tracker")
    parser.add_argument("--export-json", help="Optional path to export raw metadata as JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("  UUM CIRCULAR & PROJECT DOCUMENT TRACKER AUTOMATION")
    print("=" * 70)

    if args.clean:
        cleaned_count = clean_artifacts(BASE_DIR)
        if cleaned_count > 0:
            print(f"[+] Cleaned {cleaned_count} Windows artifact (:Zone.Identifier / desktop.ini) files.")

    circulars, forms, duplicates = process_all_documents(use_ocr=not args.no_ocr, force_ocr=args.force_ocr)

    print(f"\n[+] Processing Summary:")
    print(f"    - Unique Circulars: {len(circulars)}")
    print(f"    - Unique Forms:     {len(forms)}")
    print(f"    - Duplicates skipped: {len(duplicates)}")
    for d_name, orig in duplicates:
        print(f"      * Skipped duplicate: {d_name} (Matches {orig})")

    circ_headers = [
        "Circular_ID",
        "Ref_No",
        "Title",
        "Department",
        "Category",
        "Effective_Date",
        "Status",
        "Supersedes_Ref_No",
        "Required_Forms",
        "File_Path",
    ]
    circ_rows = [
        [
            c["id"],
            c["ref_no"],
            c["title"],
            c["department"],
            c["category"],
            c["effective_date"],
            c["status"],
            c["supersedes"],
            c["required_forms"],
            c["filepath"],
        ]
        for c in circulars
    ]

    form_headers = [
        "Form_ID",
        "Form_Code",
        "Form_Title",
        "Department",
        "Related_Circular_Ref",
        "Project_Activity_Type",
        "Is_Mandatory",
        "File_Path",
        "File_Format",
        "Notes",
    ]
    form_rows = [
        [
            f["id"],
            f["form_code"],
            f["title"],
            f["department"],
            f["related_circular"],
            f["activity_type"],
            f["is_mandatory"],
            f["filepath"],
            f["format"],
            f["notes"],
        ]
        for f in forms
    ]

    print(f"\n[*] Generating Excel workbook with standardized sheets ('circulars' & 'forms')...")
    ExcelWriter.write_workbook(
        args.output,
        "circulars",
        circ_headers,
        circ_rows,
        "forms",
        form_headers,
        form_rows,
    )
    print(f"[✓] Successfully generated: {args.output}")

    if args.export_json:
        export_data = {"circulars": circulars, "forms": forms}
        with open(args.export_json, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"[✓] Exported metadata JSON to: {args.export_json}")

    print("\n" + "=" * 70)
    print("  STATUS OVERVIEW:")
    active_circs = sum(1 for c in circulars if c["status"] == "Active")
    superseded_circs = len(circulars) - active_circs
    print(f"  • Circulars: {len(circulars)} total ({active_circs} Active, {superseded_circs} Superseded)")
    print(f"  • Forms:     {len(forms)} total mapped to project activity types")
    print("=" * 70)

if __name__ == "__main__":
    main()
