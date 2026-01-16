# -*- coding: utf-8 -*-

import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentGatewayService:
    """Python Gateway Servisi"""
    
    def __init__(self, env):
        self.env = env
    
    def create_3d_form(self, transaction, card_data):
        """3D Secure form verisi oluştur"""
        # Lazy import to avoid circular dependency
        from odoo.addons.mews_pos.lib.gateways.gateway_factory import GatewayFactory
        
        bank = transaction.bank_id
        
        # Gateway oluştur
        gateway = self._create_gateway(bank, GatewayFactory)
        
        # Sipariş verisi hazırla
        order_data = {
            'id': transaction.transaction_id,
            'amount':  float(transaction.total_amount),
            'currency':  transaction.currency,
            'installment':  int(transaction.installment_count),
            'success_url': transaction._get_callback_url('success'),
            'fail_url': transaction._get_callback_url('fail'),
            'lang': 'tr',
            'ip_address': transaction.ip_address or '127.0.0.1',
            'email': transaction.order_id.partner_id.email if transaction.order_id else 'test@test.com',
        }
        
        # Kart verisi hazırla
        card = {
            'number': card_data.get('number', '').replace(' ', ''),
            'month': card_data.get('month', '').zfill(2),
            'year': card_data.get('year', ''),
            'cvv': card_data.get('cvv', ''),
            'name': card_data.get('name', '').upper(),
        }
        
        try:
            # 3D form verisi al
            form_data = gateway.prepare_3d_request(order_data, card)
            
            _logger.info(f"3D form verisi oluşturuldu: {transaction.transaction_id}")
            
            return {
                'success': True,
                'data': form_data
            }
            
        except Exception as e: 
            _logger.error(f"3D form oluşturma hatası: {str(e)}")
            raise UserError(_("3D form oluşturulamadı: %s") % str(e))
    
    def process_3d_callback(self, transaction, callback_data):
        """3D Secure callback işle"""
        from odoo.addons.mews_pos.lib.gateways.gateway_factory import GatewayFactory
        
        bank = transaction.bank_id
        
        # Gateway oluştur
        gateway = self._create_gateway(bank, GatewayFactory)
        
        try:
            # Callback yanıtını parse et
            result = gateway.parse_3d_response(callback_data)
            
            _logger.info(f"3D callback işlendi: {transaction.transaction_id}, Başarılı: {result.get('approved')}")
            
            # Yanıtı normalize et
            normalized = gateway.normalize_response(result)
            
            return {
                'success': normalized['success'],
                'data': normalized
            }
            
        except Exception as e:
            _logger.error(f"3D callback işleme hatası: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': {'approved': False, 'error_message': str(e)}
            }
    
    def process_non_secure_payment(self, transaction, card_data):
        """Non-Secure ödeme işle"""
        from odoo.addons.mews_pos.lib.gateways.gateway_factory import GatewayFactory
        
        bank = transaction.bank_id
        
        # Gateway oluştur
        gateway = self._create_gateway(bank, GatewayFactory)
        
        # Sipariş verisi
        order_data = {
            'id': transaction.transaction_id,
            'amount': float(transaction.total_amount),
            'currency': transaction.currency,
            'installment': int(transaction.installment_count),
            'ip_address': transaction.ip_address or '127.0.0.1',
            'email': transaction.order_id.partner_id.email if transaction.order_id else 'test@test.com',
        }
        
        # Kart verisi
        card = {
            'number':  card_data.get('number', '').replace(' ', ''),
            'month': card_data.get('month', '').zfill(2),
            'year': card_data.get('year', ''),
            'cvv': card_data.get('cvv', ''),
            'name': card_data.get('name', '').upper(),
        }
        
        try:
            # Ödeme isteği hazırla
            request_data = gateway.prepare_payment_request(order_data, card)
            
            # İstek gönder
            response = gateway.make_request(
                request_data['url'],
                request_data['data'],
                request_data.get('headers')
            )
            
            # Yanıtı parse et
            result = gateway.parse_payment_response(response)
            
            _logger.info(f"Non-secure ödeme işlendi: {transaction.transaction_id}, Başarılı: {result.get('approved')}")
            
            # Yanıtı normalize et
            normalized = gateway.normalize_response(result)
            
            return {
                'success': normalized['success'],
                'data': normalized
            }
            
        except Exception as e:
            _logger.error(f"Non-secure ödeme hatası: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': {'approved': False, 'error_message': str(e)}
            }
    
    def process_cancel(self, transaction):
        """İptal işlemi"""
        from odoo.addons.mews_pos.lib.gateways.gateway_factory import GatewayFactory
        
        bank = transaction.bank_id
        
        # Gateway oluştur
        gateway = self._create_gateway(bank, GatewayFactory)
        
        order_data = {
            'id': transaction.transaction_id,
            'amount': float(transaction.total_amount),
            'currency': transaction.currency,
            'host_ref_num': transaction.host_ref_num,
            'auth_code': transaction.auth_code,
            'transaction_id': transaction.bank_order_id,
        }
        
        try:
            # İptal isteği hazırla
            request_data = gateway.prepare_cancel_request(order_data)
            
            # İstek gönder
            response = gateway.make_request(
                request_data['url'],
                request_data['data'],
                request_data.get('headers')
            )
            
            # Yanıtı parse et
            result = gateway.parse_payment_response(response)
            
            _logger.info(f"İptal işlendi: {transaction.transaction_id}, Başarılı: {result.get('approved')}")
            
            return {
                'success': result.get('approved', False),
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"İptal hatası: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_refund(self, transaction, amount=None):
        """İade işlemi"""
        from odoo.addons.mews_pos.lib.gateways.gateway_factory import GatewayFactory
        
        bank = transaction.bank_id
        
        # Gateway oluştur
        gateway = self._create_gateway(bank, GatewayFactory)
        
        refund_amount = amount if amount else float(transaction.total_amount)
        
        order_data = {
            'id': transaction.transaction_id,
            'amount':  refund_amount,
            'currency': transaction.currency,
            'host_ref_num': transaction.host_ref_num,
            'auth_code': transaction.auth_code,
            'transaction_id': transaction.bank_order_id,
        }
        
        try:
            # İade isteği hazırla
            request_data = gateway.prepare_refund_request(order_data, refund_amount)
            
            # İstek gönder
            response = gateway.make_request(
                request_data['url'],
                request_data['data'],
                request_data.get('headers')
            )
            
            # Yanıtı parse et
            result = gateway.parse_payment_response(response)
            
            _logger.info(f"İade işlendi: {transaction.transaction_id}, Başarılı: {result.get('approved')}")
            
            return {
                'success': result.get('approved', False),
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"İade hatası: {str(e)}")
            return {
                'success': False,
                'error':  str(e)
            }
    
    def _create_gateway(self, bank, GatewayFactory):
        """Gateway instance oluştur"""
        config = bank.get_account_config()
        gateway_type = bank.gateway_type
        
        try:
            gateway = GatewayFactory.create(gateway_type, config)
            return gateway
        except ValueError as e:
            raise UserError(str(e))