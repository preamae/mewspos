# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
import logging
import json

_logger = logging.getLogger(__name__)


class AkbankGateway(BaseGateway):
    """Akbank POS Gateway (Yeni API)"""

    def prepare_3d_request(self, order, card):
        """3D Secure isteği hazırla"""
        config = self.config
        
        # Hash oluştur
        hash_data = CryptoUtils.create_hash_akbank(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            currency=order.get('currency', 'TRY'),
            installment=order.get('installment', 1),
            store_key=config['store_key']
        )

        # Akbank JSON API kullanır
        request_data = {
            'version': '1.0.0',
            'merchantId': config['merchant_id'],
            'terminalId': config['terminal_id'],
            'orderId': order['id'],
            'amount': self.format_amount(order['amount'], False),
            'currency': self.map_currency(order.get('currency', 'TRY')),
            'installment': str(order.get('installment', 1)),
            'transactionType': 'Sale',
            'cardOwner': card['name'],
            'cardNumber': card['number'],
            'cardExpireMonth': card['month'].zfill(2),
            'cardExpireYear': card['year'],
            'cardCvv': card['cvv'],
            'successUrl': order['success_url'],
            'failureUrl': order['fail_url'],
            'hash': hash_data,
            'secureOption': '3d',
            'language': order.get('lang', 'tr').upper(),
        }

        # Akbank için önce payment initiate isteği gönderilmeli
        return {
            'request_type': 'json',
            'payment_data': request_data,
            'gateway_url': config['gateway_3d_url'],
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        status = response_data.get('status', '')
        result_code = response_data.get('resultCode', '')
        
        # status: 'success' = başarılı
        # resultCode: '0000' = başarılı
        approved = (
            status == 'success' and 
            result_code == '0000'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('orderId'),
            'auth_code': response_data.get('authCode'),
            'host_ref_num':  response_data.get('hostReferenceNumber'),
            'rrn': response_data.get('rrn'),
            'md_status': '1' if approved else '0',
            'eci': response_data.get('eci'),
            'cavv': response_data.get('cavv'),
            'xid': response_data.get('xid'),
            'error_code': result_code,
            'error_message': response_data.get('resultMessage'),
            'transaction_id': response_data.get('transactionId'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        hash_data = CryptoUtils.create_hash_akbank(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            currency=order.get('currency', 'TRY'),
            installment=order.get('installment', 1),
            store_key=config['store_key']
        )

        data = {
            'version': '1.0.0',
            'merchantId': config['merchant_id'],
            'terminalId': config['terminal_id'],
            'orderId': order['id'],
            'amount': self.format_amount(order['amount'], False),
            'currency': self.map_currency(order.get('currency', 'TRY')),
            'installment':  str(order.get('installment', 1)),
            'transactionType': 'Sale',
            'cardOwner': card['name'],
            'cardNumber':  card['number'],
            'cardExpireMonth': card['month'].zfill(2),
            'cardExpireYear': card['year'],
            'cardCvv': card['cvv'],
            'hash': hash_data,
            'secureOption': 'NonSecure',
        }

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {config.get('client_id', '')}",
            }
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        try:
            response_data = response.json()
        except:
            return {'approved': False, 'error_message': 'Geçersiz JSON yanıtı'}
        
        status = response_data.get('status', '')
        result_code = response_data.get('resultCode', '')
        
        approved = (
            status == 'success' and 
            result_code == '0000'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('orderId'),
            'auth_code': response_data.get('authCode'),
            'host_ref_num': response_data.get('hostReferenceNumber'),
            'rrn': response_data.get('rrn'),
            'error_code': result_code,
            'error_message': response_data.get('resultMessage'),
            'transaction_id': response_data.get('transactionId'),
        }

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        hash_data = CryptoUtils.create_hash_akbank(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            currency=order.get('currency', 'TRY'),
            installment=1,
            store_key=config['store_key']
        )

        data = {
            'version': '1.0.0',
            'merchantId': config['merchant_id'],
            'terminalId': config['terminal_id'],
            'orderId':  order['id'],
            'transactionType': 'Void',
            'transactionId': order.get('transaction_id', ''),
            'hash': hash_data,
        }

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {config.get('client_id', '')}",
            }
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        hash_data = CryptoUtils.create_hash_akbank(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=refund_amount,
            currency=order.get('currency', 'TRY'),
            installment=1,
            store_key=config['store_key']
        )

        data = {
            'version': '1.0.0',
            'merchantId': config['merchant_id'],
            'terminalId': config['terminal_id'],
            'orderId': order['id'],
            'amount': self.format_amount(refund_amount, False),
            'currency': self.map_currency(order.get('currency', 'TRY')),
            'transactionType': 'Refund',
            'transactionId':  order.get('transaction_id', ''),
            'hash': hash_data,
        }

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {config.get('client_id', '')}",
            }
        }