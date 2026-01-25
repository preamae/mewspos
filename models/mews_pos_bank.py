# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MewsPosBank(models.Model):
    """Banka tanımlamaları ve POS yapılandırması"""
    _name = 'mews.pos.bank'
    _description = 'Mews POS Banka Tanımı'
    _order = 'sequence, name'

    name = fields.Char(string='Banka Adı', required=True)
    code = fields.Char(string='Banka Kodu', required=True)
    sequence = fields.Integer(string='Sıra', default=10)
    active = fields.Boolean(string='Aktif', default=True)
    
    # Gateway reference (instead of selection)
    gateway_id = fields.Many2one(
        'mews.pos.gateway',
        string='Ödeme Geçidi',
        required=False,  # Not required to avoid migration issues
        ondelete='restrict',
        help='Bu bankanın kullandığı ödeme geçidi'
    )
    
    # Deprecated field - kept for backward compatibility
    gateway_type = fields.Selection([
        ('akbank_pos', 'Akbank POS'),
        ('estv3_pos', 'EST V3 POS (Payten/Asseco)'),
        ('garanti_pos', 'Garanti POS'),
        ('posnet', 'PosNet (YapıKredi)'),
        ('posnet_v1', 'PosNet V1 (Albaraka)'),
        ('payfor', 'PayFor (Finansbank)'),
        ('payflex_mpi', 'PayFlex MPI (Ziraat/Vakıfbank)'),
        ('payflex_common', 'PayFlex Common Payment'),
        ('interpos', 'InterPos (Denizbank)'),
        ('kuveyt_pos', 'Kuveyt POS'),
        ('vakif_katilim', 'Vakıf Katılım POS'),
        ('tosla', 'Tosla'),
        ('param_pos', 'ParamPos'),
    ], string='Gateway Tipi (Deprecated)', compute='_compute_gateway_type', store=True)
    
    @api.depends('gateway_id.code')
    def _compute_gateway_type(self):
        """Compute gateway_type from gateway_id for backward compatibility"""
        for bank in self:
            bank.gateway_type = bank.gateway_id.code if bank.gateway_id else False
    
    payment_model = fields.Selection([
        ('3d_secure', '3D Secure'),
        ('3d_pay', '3D Pay'),
        ('3d_host', '3D Host'),
        ('non_secure', 'Non Secure'),
    ], string='Ödeme Modeli', default='3d_secure', required=True)
    
    merchant_id = fields.Char(string='Üye İşyeri No')
    terminal_id = fields.Char(string='Terminal No')
    username = fields.Char(string='Kullanıcı Adı')
    password = fields.Char(string='Şifre')
    store_key = fields.Char(string='Store Key / 3D Secure Key')
    client_id = fields.Char(string='Client ID')
    
    payment_api_url = fields.Char(string='Payment API URL')
    gateway_3d_url = fields.Char(string='3D Gateway URL')
    gateway_3d_host_url = fields.Char(string='3D Host Gateway URL')
    
    environment = fields.Selection([
        ('test', 'Test Ortamı'),
        ('production', 'Canlı Ortam'),
    ], string='Ortam', default='test', required=True)
    
    logo = fields.Binary(string='Banka Logosu')
    
    installment_config_ids = fields.One2many(
        'mews.pos.installment.config',
        'bank_id',
        string='Taksit Yapılandırmaları'
    )
    
    category_restriction_ids = fields.One2many(
        'mews.pos.category.restriction',
        'bank_id',
        string='Kategori Kısıtlamaları'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Banka kodu benzersiz olmalıdır!')
    ]

    def get_account_config(self):
        """Python için hesap yapılandırmasını döndür"""
        return {
            'bank_code': self.code,
            'merchant_id': self.merchant_id,
            'terminal_id':  self.terminal_id,
            'username': self.username,
            'password': self.password,
            'store_key': self.store_key,
            'client_id': self.client_id,
            'payment_model': self.payment_model,
            'environment': self.environment,
            'endpoints': {
                'payment_api': self.payment_api_url,
                'gateway_3d': self.gateway_3d_url,
                'gateway_3d_host':  self.gateway_3d_host_url,
            }
        }