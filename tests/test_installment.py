# -*- coding:  utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestInstallmentConfig(TransactionCase):
    """Taksit yapılandırması testleri"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Test bankası oluştur
        cls.bank = cls.env['mews.pos.bank'].create({
            'name': 'Test Bankası',
            'code': 'test_bank',
            'gateway_type': 'estv3_pos',
            'payment_model': '3d_secure',
            'environment': 'test',
        })
        
        # Taksit yapılandırması oluştur
        cls.installment_config = cls.env['mews.pos.installment.config'].create({
            'bank_id': cls.bank.id,
            'installment_count': 3,
            'interest_rate': 1.5,
            'min_amount': 100,
        })

    def test_calculate_installment(self):
        """Taksit hesaplama testi"""
        result = self.installment_config.calculate_installment(1000)
        
        self.assertEqual(result['installment_count'], 3)
        self.assertEqual(result['original_amount'], 1000)
        self.assertAlmostEqual(result['total_amount'], 1015, places=2)
        self.assertAlmostEqual(result['installment_amount'], 338.33, places=2)
        self.assertAlmostEqual(result['interest_amount'], 15, places=2)

    def test_installment_count_validation(self):
        """Taksit sayısı validasyonu testi"""
        with self.assertRaises(ValidationError):
            self.env['mews.pos.installment.config'].create({
                'bank_id':  self.bank.id,
                'installment_count': 1,  # Geçersiz - minimum 2 olmalı
                'interest_rate':  0,
            })

    def test_campaign_rate(self):
        """Kampanya oranı testi"""
        from datetime import date, timedelta
        
        today = date.today()
        
        self.installment_config.write({
            'campaign_active': True,
            'campaign_rate':  0,
            'campaign_start_date': today - timedelta(days=1),
            'campaign_end_date':  today + timedelta(days=1),
        })
        
        effective_rate = self.installment_config.get_effective_rate()
        self.assertEqual(effective_rate, 0)  # Kampanya oranı


class TestCategoryRestriction(TransactionCase):
    """Kategori kısıtlaması testleri"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.bank = cls.env['mews.pos.bank'].create({
            'name': 'Test Bankası',
            'code': 'test_bank_2',
            'gateway_type': 'estv3_pos',
            'payment_model': '3d_secure',
            'environment':  'test',
        })
        
        cls.category = cls.env['product.category'].create({
            'name':  'Test Kategori',
        })
        
        cls.restriction = cls.env['mews.pos.category.restriction'].create({
            'bank_id': cls.bank.id,
            'category_id': cls.category.id,
            'max_installment': 6,
            'min_installment': 2,
            'blocked_installments': '3,5',
        })

    def test_blocked_installments(self):
        """Engellenen taksit listesi testi"""
        blocked = self.restriction.get_blocked_installment_list()
        self.assertEqual(blocked, [3, 5])

    def test_allowed_installments(self):
        """İzin verilen taksitler testi"""
        available = [
            {'installment_count': 2},
            {'installment_count': 3},
            {'installment_count': 4},
            {'installment_count': 5},
            {'installment_count': 6},
            {'installment_count': 9},
        ]
        
        allowed = self.restriction.get_allowed_installments(available)
        allowed_counts = [a['installment_count'] for a in allowed]
        
        self.assertIn(2, allowed_counts)
        self.assertNotIn(3, allowed_counts)  # Engelli
        self.assertIn(4, allowed_counts)
        self.assertNotIn(5, allowed_counts)  # Engelli
        self.assertIn(6, allowed_counts)
        self.assertNotIn(9, allowed_counts)  # Max aşımı