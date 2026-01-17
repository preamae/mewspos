# -*- coding: utf-8 -*-
import hashlib
import base64
import requests
import json
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from zeep import Client
from zeep.transports import Transport
from lxml import etree
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import uuid

_logger = logging.getLogger(__name__)

class BankIntegrationBase:
    """Tüm banka entegrasyonları için temel sınıf"""
    
    def __init__(self, acquirer):
        self.acquirer = acquirer
        self.config = acquirer.get_bank_config()
        
    def _format_amount(self, amount):
        """Tutarı banka formatına çevir"""
        return "{:.2f}".format(amount).replace('.', '').replace(',', '')
    
    def _generate_hash(self, data_string):
        """SHA1 hash oluştur"""
        return hashlib.sha1(data_string.encode('utf-8')).hexdigest()
    
    def _generate_sha256(self, data_string):
        """SHA256 hash oluştur"""
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    
    def _generate_sha512(self, data_string):
        """SHA512 hash oluştur"""
        return hashlib.sha512(data_string.encode('utf-8')).hexdigest()
    
    def _make_request(self, url, data, method='POST'):
        """HTTP isteği gönder"""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Odoo/19.0'
        }
        
        try:
            if method == 'POST':
                response = requests.post(url, data=data, headers=headers, timeout=30)
            else:
                response = requests.get(url, params=data, headers=headers, timeout=30)
            
            return response
        except Exception as e:
            _logger.error(f"Request error: {str(e)}")
            raise UserError(_("Banka bağlantı hatası: %s") % str(e))
    
    def create_payment_form(self, order_data):
        """Ödeme formu oluştur"""
        raise NotImplementedError
    
    def process_3d_response(self, response_data):
        """3D yanıtını işle"""
        raise NotImplementedError
    
    def refund(self, transaction, amount):
        """İade işlemi"""
        raise NotImplementedError
    
    def cancel(self, transaction):
        """İptal işlemi"""
        raise NotImplementedError

class AkbankIntegration(BankIntegrationBase):
    """Akbank (EST V3) Python Entegrasyonu"""
    
    def create_payment_form(self, order_data):
        """Akbank için ödeme formu oluştur"""
        import random
        import string
        
        # Rastgele değer üret
        rnd = ''.join(random.choices(string.digits, k=20))
        
        # Hash için veri
        hash_data = (
            f"{self.config.get('merchant_id')}"
            f"{order_data.get('order_id')}"
            f"{self._format_amount(order_data.get('amount'))}"
            f"{order_data.get('success_url')}"
            f"{order_data.get('fail_url')}"
            f"Auth"
            f"{order_data.get('installment', '')}"
            f"{rnd}"
            f"{self.config.get('store_key')}"
        )
        
        # Hash hesapla
        hashval = self._generate_sha512(hash_data)
        
        form_data = {
            'clientid': self.config.get('merchant_id'),
            'storetype': '3d',
            'trantype': 'Auth',
            'amount': self._format_amount(order_data.get('amount')),
            'currency': '949',
            'oid': order_data.get('order_id'),
            'okUrl': order_data.get('success_url'),
            'failUrl': order_data.get('fail_url'),
            'lang': 'tr',
            'rnd': rnd,
            'hash': hashval,
            'refreshtime': '0',
            'instalment': order_data.get('installment', ''),
        }
        
        return {
            'action': self.config.get('gateway_url'),
            'method': 'POST',
            'inputs': form_data
        }
    
    def process_3d_response(self, response_data):
        """Akbank 3D yanıtını işle"""
        md_status = response_data.get('mdStatus', '')
        
        result = {
            'success': md_status in ['1', '2', '3', '4'],
            'md_status': md_status,
            'order_id': response_data.get('oid'),
            'auth_code': response_data.get('AuthCode'),
            'trans_id': response_data.get('TransId'),
            'error_msg': response_data.get('ErrMsg'),
            'raw_response': response_data
        }
        
        return result

class GarantiIntegration(BankIntegrationBase):
    """Garanti BBVA Python Entegrasyonu"""
    
    def create_payment_form(self, order_data):
        """Garanti için ödeme formu oluştur"""
        
        # Terminal provizyon şifresi hash
        prov_password = self.config.get('provision_password', '')
        terminal_id = self.config.get('terminal_id', '')
        security_data = hashlib.sha1(f"{prov_password}{terminal_id}".encode()).hexdigest()
        
        # Hash için veri
        hash_data = (
            f"{self.config.get('terminal_id')}"
            f"{order_data.get('order_id')}"
            f"{self._format_amount(order_data.get('amount'))}"
            f"{order_data.get('success_url')}"
            f"{order_data.get('fail_url')}"
            f"sales"
            f"{order_data.get('installment', '')}"
            f"{self.config.get('store_key')}"
        )
        
        # İlk hash
        first_hash = hashlib.sha1(hash_data.encode()).hexdigest()
        
        # Final hash
        final_hash = hashlib.sha512(f"{first_hash}{security_data}".encode()).hexdigest()
        
        form_data = {
            'secure3dsecuritylevel': '3D',
            'mode': 'TEST' if self.config.get('test_mode') else 'PROD',
            'apiversion': 'v0.01',
            'terminalprovuserid': self.config.get('provision_user'),
            'terminaluserid': self.config.get('terminal_user'),
            'terminalmerchantid': self.config.get('merchant_id'),
            'txntype': 'sales',
            'txnamount': self._format_amount(order_data.get('amount')),
            'txncurrencycode': '949',
            'txninstallmentcount': order_data.get('installment', ''),
            'orderid': order_data.get('order_id'),
            'successurl': order_data.get('success_url'),
            'errorurl': order_data.get('fail_url'),
            'customeripaddress': order_data.get('customer_ip', '127.0.0.1'),
            'terminalid': self.config.get('terminal_id'),
            'secure3dhash': final_hash
        }
        
        return {
            'action': self.config.get('gateway_url'),
            'method': 'POST',
            'inputs': form_data
        }

class YapiKrediIntegration(BankIntegrationBase):
    """Yapı Kredi PosNet Python Entegrasyonu"""
    
    def create_payment_form(self, order_data):
        """Yapı Kredi için ödeme formu oluştur"""
        
        # XML verisi oluştur
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<PosnetRequest>
    <mid>{self.config.get('merchant_id')}</mid>
    <tid>{self.config.get('terminal_id')}</tid>
    <tranType>Sale</tranType>
    <orderID>{order_data.get('order_id')}</orderID>
    <amount>{self._format_amount(order_data.get('amount'))}</amount>
    <currencyCode>YT</currencyCode>
    <installment>{order_data.get('installment', '')}</installment>
    <extra>
        <webhost>10.10.10.10</webhost>
        <webip>10.10.10.10</webip>
    </extra>
</PosnetRequest>"""
        
        # SOAP isteği
        client = Client(self.config.get('gateway_url'))
        
        try:
            response = client.service.BankAuthRequest(xml_data)
            
            # XML yanıtını parse et
            root = ET.fromstring(response)
            
            approved = root.find('approved').text == '1'
            auth_code = root.find('authCode').text if approved else ''
            
            form_data = {
                'approved': approved,
                'auth_code': auth_code,
                'trans_id': root.find('transId').text if approved else '',
                'raw_response': response
            }
            
            return form_data
        except Exception as e:
            _logger.error(f"Yapı Kredi SOAP error: {str(e)}")
            raise UserError(_("Yapı Kredi bağlantı hatası"))

class ToslaIntegration(BankIntegrationBase):
    """Tosla Payment Gateway Integration"""
    
    def create_payment_form(self, order_data):
        """Create payment form for Tosla gateway"""
        try:
            # Tosla uses REST API with JSON
            api_url = self.config.get('payment_api_url') or self.config.get('endpoints', {}).get('payment_api')
            
            if not api_url:
                raise UserError(_("Tosla Payment API URL yapılandırılmamış"))
            
            # Prepare request data
            request_data = {
                'clientId': self.config.get('client_id'),
                'merchantId': self.config.get('merchant_id'),
                'terminalId': self.config.get('terminal_id'),
                'orderId': order_data.get('order_id'),
                'amount': str(order_data.get('amount')),
                'currency': 'TRY',
                'installment': str(order_data.get('installment', 1)),
                'cardNumber': order_data.get('card_number'),
                'cardHolderName': order_data.get('card_holder'),
                'cardExpMonth': order_data.get('card_exp_month'),
                'cardExpYear': order_data.get('card_exp_year'),
                'cardCvv': order_data.get('card_cvv'),
                'callbackUrl': order_data.get('success_url'),
                'failUrl': order_data.get('fail_url'),
            }
            
            # Generate hash/signature if required
            if self.config.get('store_key'):
                hash_string = (
                    f"{request_data['clientId']}"
                    f"{request_data['orderId']}"
                    f"{request_data['amount']}"
                    f"{self.config.get('store_key')}"
                )
                request_data['hash'] = self._generate_sha256(hash_string)
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Odoo/19.0'
            }
            
            # Make API request
            response = requests.post(
                api_url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise UserError(_("Tosla API hatası: %s") % response.status_code)
            
            result = response.json()
            
            # Tosla returns 3D Secure redirect URL
            if result.get('redirectUrl'):
                form_data = {
                    'redirect_url': result.get('redirectUrl'),
                    'redirect_method': 'GET',
                    'transaction_id': result.get('transactionId'),
                    'form_fields': {},
                }
            else:
                # If direct response (non-3D)
                form_data = {
                    'approved': result.get('success', False),
                    'auth_code': result.get('authCode', ''),
                    'transaction_id': result.get('transactionId', ''),
                    'error_message': result.get('errorMessage', ''),
                }
            
            return form_data
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Tosla connection error: {str(e)}")
            raise UserError(_("Tosla bağlantı hatası: %s") % str(e))
        except Exception as e:
            _logger.error(f"Tosla error: {str(e)}")
            raise UserError(_("Tosla işlem hatası: %s") % str(e))

def get_bank_integration(bank):
    """
    Factory function to get appropriate bank integration instance
    
    Args:
        bank: mews.pos.bank record
        
    Returns:
        BankIntegrationBase instance or None
    """
    gateway_type = bank.gateway_type
    
    integration_map = {
        'akbank_pos': AkbankIntegration,
        'estv3_pos': AkbankIntegration,  # EST V3 is similar to Akbank
        'garanti_pos': GarantiIntegration,
        'posnet': YapiKrediIntegration,
        'posnet_v1': YapiKrediIntegration,
        'tosla': ToslaIntegration,
    }
    
    integration_class = integration_map.get(gateway_type)
    
    if integration_class:
        # Create a pseudo acquirer object for compatibility
        class BankAcquirerAdapter:
            def __init__(self, bank_record):
                self.bank = bank_record
                
            def get_bank_config(self):
                return self.bank.get_account_config()
        
        adapter = BankAcquirerAdapter(bank)
        return integration_class(adapter)
    
    _logger.warning(f"No integration found for gateway type: {gateway_type}")
    return None

class PaymentAcquirer(models.Model):
    """Ödeme Sağlayıcısı Genişletmesi"""
    _inherit = 'payment.provider'
    
    # Banka tipi
    bank_type = fields.Selection([
        ('akbank', 'Akbank'),
        ('garanti', 'Garanti BBVA'),
        ('yapikredi', 'Yapı Kredi'),
        ('isbank', 'İş Bankası'),
        ('finansbank', 'QNB Finansbank'),
        ('ziraat', 'Ziraat Bankası'),
        ('vakifbank', 'Vakıfbank'),
        ('denizbank', 'Denizbank'),
        ('hsbc', 'HSBC'),
        ('teb', 'TEB'),
        ('sekurbank', 'Şekerbank'),
        ('halkbank', 'Halkbank'),
    ], string='Banka Tipi')
    
    # Banka kimlik bilgileri
    merchant_id = fields.Char(string='Üye İşyeri No')
    terminal_id = fields.Char(string='Terminal No')
    store_key = fields.Char(string='Store Key')
    provision_password = fields.Char(string='Provizyon Şifresi')
    provision_user = fields.Char(string='Provizyon Kullanıcısı')
    
    # API URL'leri
    gateway_url = fields.Char(string='3D Gateway URL')
    api_url = fields.Char(string='API URL')
    
    # Taksit ayarları
    max_installment = fields.Integer(string='Maksimum Taksit', default=12)
    installment_options = fields.Char(
        string='Taksit Seçenekleri',
        default='2,3,6,9,12',
        help='Virgülle ayrılmış taksit seçenekleri'
    )
    
    # Kategori kısıtlamaları
    category_restriction_ids = fields.One2many(
        'pos.category.restriction',
        'acquirer_id',
        string='Kategori Kısıtlamaları'
    )
    
    def get_bank_config(self):
        """Banka yapılandırmasını döndür"""
        return {
            'bank_type': self.bank_type,
            'merchant_id': self.merchant_id,
            'terminal_id': self.terminal_id,
            'store_key': self.store_key,
            'provision_password': self.provision_password,
            'provision_user': self.provision_user,
            'gateway_url': self.gateway_url,
            'api_url': self.api_url,
            'test_mode': self.state == 'test'
        }
    
    def get_integration_handler(self):
        """Banka entegrasyon handler'ını döndür"""
        bank_handlers = {
            'akbank': AkbankIntegration,
            'garanti': GarantiIntegration,
            'yapikredi': YapiKrediIntegration,
        }
        
        handler_class = bank_handlers.get(self.bank_type)
        if not handler_class:
            raise UserError(_("Bu banka tipi için handler bulunamadı"))
        
        return handler_class(self)
    
    def get_available_installments(self, amount, category_id=None):
        """Kullanılabilir taksit seçeneklerini döndür"""
        self.ensure_one()
        
        # Kategori kısıtlaması kontrolü
        max_installment = self.max_installment
        if category_id:
            restriction = self.category_restriction_ids.filtered(
                lambda r: r.category_id.id == category_id
            )
            if restriction:
                max_installment = min(max_installment, restriction.max_installment)
        
        # Taksit seçeneklerini filtrele
        available_installments = []
        try:
            options = [int(x.strip()) for x in self.installment_options.split(',')]
            options = [opt for opt in options if 2 <= opt <= max_installment]
            
            # Tek çekim her zaman mevcut
            available_installments.append({
                'installment': 1,
                'label': 'Tek Çekim',
                'installment_amount': amount,
                'total_amount': amount
            })
            
            # Taksit seçenekleri
            for opt in options:
                # Basit faiz hesaplama (gerçek uygulamada banka oranları kullanılmalı)
                if opt <= 3:
                    total = amount * 1.02  # %2 faiz
                elif opt <= 6:
                    total = amount * 1.05  # %5 faiz
                else:
                    total = amount * 1.08  # %8 faiz
                
                installment_amount = total / opt
                
                available_installments.append({
                    'installment': opt,
                    'label': f'{opt} Taksit',
                    'installment_amount': round(installment_amount, 2),
                    'total_amount': round(total, 2),
                    'interest_amount': round(total - amount, 2)
                })
                
        except Exception as e:
            _logger.error(f"Installment calculation error: {str(e)}")
        
        return available_installments
    
    def create_payment_transaction(self, order_data, category_id=None):
        """Ödeme işlemi oluştur"""
        self.ensure_one()
        
        # Taksit kontrolü
        installment = order_data.get('installment', 1)
        if installment > 1:
            available = self.get_available_installments(
                order_data.get('amount'),
                category_id
            )
            available_counts = [a['installment'] for a in available]
            
            if installment not in available_counts:
                raise UserError(_("Bu taksit seçeneği kullanılamaz"))
        
        # Banka handler'ını al
        handler = self.get_integration_handler()
        
        # Ödeme formu oluştur
        payment_form = handler.create_payment_form(order_data)
        
        # İşlem kaydı oluştur
        transaction = self.env['payment.transaction'].create({
            'provider_id': self.id,
            'amount': order_data.get('amount'),
            'currency_id': self.env.ref('base.TRY').id,
            'reference': order_data.get('order_id'),
            'partner_id': order_data.get('partner_id'),
            'state': 'pending',
        })
        
        return {
            'transaction': transaction,
            'payment_form': payment_form
        }

class POSCategoryRestriction(models.Model):
    """Kategori Bazlı Taksit Kısıtlaması"""
    _name = 'pos.category.restriction'
    _description = 'Kategori Taksit Kısıtlaması'
    
    acquirer_id = fields.Many2one(
        'payment.provider',
        string='Ödeme Sağlayıcısı',
        required=True
    )
    category_id = fields.Many2one(
        'product.category',
        string='Ürün Kategorisi',
        required=True
    )
    max_installment = fields.Integer(
        string='Maksimum Taksit',
        default=12,
        help='Bu kategori için maksimum taksit sayısı'
    )
    installment_allowed = fields.Boolean(
        string='Taksit İzni',
        default=True,
        help='Bu kategoride taksit yapılabilir mi?'
    )
    
    _sql_constraints = [
        ('acquirer_category_unique',
         'unique(acquirer_id, category_id)',
         'Aynı kategori için birden fazla kısıtlama olamaz')
    ]