# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestBinLookup(TransactionCase):
    """BIN numarası ile banka tespiti testleri"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Test bankaları oluştur
        cls.akbank = cls.env['mews.pos.bank'].create({
            'name': 'Akbank Test',
            'code': 'akbank_test',
            'gateway_type': 'akbank_pos',
            'payment_model': '3d_secure',
            'environment': 'test',
        })
        
        cls.garanti = cls.env['mews.pos.bank'].create({
            'name': 'Garanti Test',
            'code': 'garanti_test',
            'gateway_type': 'garanti_pos',
            'payment_model': '3d_secure',
            'environment': 'test',
        })
        
        # Test BIN numaraları oluştur
        cls.bin_akbank = cls.env['mews.pos.bin'].create({
            'name': 'Akbank Test Card',
            'bin_number': '540667',
            'bank_id': cls.akbank.id,
            'card_type': 'mastercard',
        })
        
        cls.bin_garanti = cls.env['mews.pos.bin'].create({
            'name': 'Garanti Test Card',
            'bin_number': '552608',
            'bank_id': cls.garanti.id,
            'card_type': 'mastercard',
        })
        
        # Taksit yapılandırmaları oluştur
        cls.env['mews.pos.installment.config'].create({
            'bank_id': cls.akbank.id,
            'installment_count': 2,
            'interest_rate': 0.0,
            'min_amount': 100.0,
        })
        
        cls.env['mews.pos.installment.config'].create({
            'bank_id': cls.akbank.id,
            'installment_count': 3,
            'interest_rate': 0.0,
            'min_amount': 150.0,
        })
        
        cls.env['mews.pos.installment.config'].create({
            'bank_id': cls.garanti.id,
            'installment_count': 2,
            'interest_rate': 0.0,
            'min_amount': 100.0,
        })

    def test_bin_lookup_akbank(self):
        """Akbank BIN numarasından banka tespiti"""
        bin_record = self.env['mews.pos.bin'].search([
            ('bin_number', '=', '540667'),
            ('active', '=', True)
        ], limit=1)
        
        self.assertTrue(bin_record, "BIN kaydı bulunamadı")
        self.assertEqual(bin_record.bank_id.id, self.akbank.id, "Yanlış banka tespit edildi")
        self.assertEqual(bin_record.bank_id.name, 'Akbank Test')

    def test_bin_lookup_garanti(self):
        """Garanti BIN numarasından banka tespiti"""
        bin_record = self.env['mews.pos.bin'].search([
            ('bin_number', '=', '552608'),
            ('active', '=', True)
        ], limit=1)
        
        self.assertTrue(bin_record, "BIN kaydı bulunamadı")
        self.assertEqual(bin_record.bank_id.id, self.garanti.id, "Yanlış banka tespit edildi")
        self.assertEqual(bin_record.bank_id.name, 'Garanti Test')

    def test_bin_not_found(self):
        """Kayıtlı olmayan BIN numarası"""
        bin_record = self.env['mews.pos.bin'].search([
            ('bin_number', '=', '999999'),
            ('active', '=', True)
        ], limit=1)
        
        self.assertFalse(bin_record, "Olmayan BIN kaydı bulundu")

    def test_installment_configs_for_bank(self):
        """Bankaya ait taksit yapılandırmalarını getirme"""
        amount = 200.0
        
        configs = self.env['mews.pos.installment.config'].search([
            ('bank_id', '=', self.akbank.id),
            ('active', '=', True),
            ('min_amount', '<=', amount),
        ], order='installment_count')
        
        self.assertEqual(len(configs), 2, "Beklenmeyen taksit yapılandırma sayısı")
        
        # İlk yapılandırma 2 taksit olmalı
        self.assertEqual(configs[0].installment_count, 2)
        result = configs[0].calculate_installment(amount)
        self.assertEqual(result['installment_count'], 2)
        self.assertEqual(result['installment_amount'], 100.0)
        self.assertEqual(result['total_amount'], 200.0)

    def test_bin_unique_constraint(self):
        """BIN numarasının benzersiz olması gerektiğini test et"""
        from odoo.exceptions import ValidationError
        from odoo.tools import mute_logger
        
        # Integrity constraint violations are logged at ERROR level
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['mews.pos.bin'].create({
                'name': 'Duplicate BIN',
                'bin_number': '540667',  # Zaten var
                'bank_id': self.garanti.id,
                'card_type': 'visa',
            })
