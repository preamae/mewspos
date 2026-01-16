# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MewsPosBin(models.Model):
    _name = 'mews.pos.bin'
    _description = 'Kart BIN Numaraları'
    _order = 'bin_number'
    
    name = fields.Char(string='Açıklama', required=True)
    bin_number = fields.Char(string='BIN Numarası', size=6, required=True)
    bank_id = fields.Many2one('mews.pos.bank', string='Banka', required=True)
    card_type = fields.Selection([
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('amex', 'American Express'),
        ('discover', 'Discover'),
        ('troy', 'Troy'),
        ('other', 'Diğer')
    ], string='Kart Türü')
    active = fields.Boolean(string='Aktif', default=True)
    
    _sql_constraints = [
        ('bin_number_unique', 'unique(bin_number)', 'Bu BIN numarası zaten kayıtlı!'),
    ]