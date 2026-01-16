# -*- coding:  utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from unittest.mock import patch, MagicMock


class TestTransaction(TransactionCase):
    """İşlem testleri"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.bank = cls.env['mews.pos.bank'].create({
            'name': 'Test Bankası',
            'code': 'test_bank_tx',
            'gateway_type': 'estv3_pos',
            'payment_model': '3d_secure',
            'environment': 'test',
        })
        
        cls.transaction = cls.env['mews.pos.transaction'].create({
            'bank_id': cls.bank.id,
            'amount': 1000,
            'total_amount': 1000,
            'installment_count': 1,
            'currency':  'TRY',
        })

    def test_transaction_creation(self):
        """İşlem oluşturma testi"""
        self.assertTrue(self.transaction.transaction_id)
        self.assertEqual(self.transaction.state, 'draft')
        self.assertEqual(self.transaction.amount, 1000)

    def test_card_type_detection(self):
        """Kart tipi tespit testi"""
        self.assertEqual(self.transaction._detect_card_type('4111111111111111'), 'visa')
        self.assertEqual(self.transaction._detect_card_type('5111111111111111'), 'mastercard')
        self.assertEqual(self.transaction._detect_card_type('3411111111111111'), 'amex')
        self.assertEqual(self.transaction._detect_card_type('9792111111111111'), 'troy')

    def test_callback_url_generation(self):
        """Callback URL oluşturma testi"""
        success_url = self.transaction._get_callback_url('success')
        fail_url = self.transaction._get_callback_url('fail')
        
        self.assertIn('/mews_pos/callback/success/', success_url)
        self.assertIn('/mews_pos/callback/fail/', fail_url)
        self.assertIn(self.transaction.transaction_id, success_url)

    def test_cancel_not_success(self):
        """Başarısız işlem iptal testi"""
        with self.assertRaises(UserError):
            self.transaction.action_cancel()

    def test_refund_not_success(self):
        """Başarısız işlem iade testi"""
        with self.assertRaises(UserError):
            self.transaction.action_refund()

    def test_interest_calculation(self):
        """Faiz hesaplama testi"""
        self.transaction.write({
            'amount': 1000,
            'total_amount': 1100,
        })
        
        self.assertEqual(self.transaction.interest_amount, 100)