# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MewsPosGateway(models.Model):
    """Payment Gateway definitions (Ödeme Geçidi tanımları)"""
    _name = 'mews.pos.gateway'
    _description = 'Mews POS Gateway (Ödeme Geçidi)'
    _order = 'sequence, name'

    name = fields.Char(string='Gateway Adı', required=True)
    code = fields.Selection([
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
        ('tosla', 'Tosla / ParamPos'),
        ('param_pos', 'ParamPos'),
    ], string='Gateway Kodu', required=True)
    
    sequence = fields.Integer(string='Sıra', default=10)
    active = fields.Boolean(string='Aktif', default=True)
    
    description = fields.Text(string='Açıklama')
    
    # Gateway supports all banks (like ParamPos Tosla)
    supports_all_banks = fields.Boolean(
        string='Tüm Bankaları Destekler',
        default=False,
        help='Bu gateway tüm bankaları destekliyorsa işaretleyin (örn: ParamPos Tosla)'
    )
    
    # Related banks
    bank_ids = fields.One2many(
        'mews.pos.bank',
        'gateway_id',
        string='Bankalar',
        help='Bu gateway ile çalışan bankalar'
    )
    
    bank_count = fields.Integer(
        string='Banka Sayısı',
        compute='_compute_bank_count',
        store=True
    )
    
    @api.depends('bank_ids')
    def _compute_bank_count(self):
        for gateway in self:
            gateway.bank_count = len(gateway.bank_ids)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Gateway kodu benzersiz olmalıdır!'),
    ]
