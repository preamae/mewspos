# -*- coding: utf-8 -*-

import requests
import logging
from abc import ABC, abstractmethod

_logger = logging.getLogger(__name__)


class BaseGateway(ABC):
    """Tüm gateway'ler için base sınıf"""

    def __init__(self, config):
        self.config = config
        self.timeout = 30
        self.test_mode = config.get('environment') == 'test'

    @abstractmethod
    def prepare_payment_request(self, order, card):
        """Ödeme isteği hazırla"""
        pass

    @abstractmethod
    def prepare_3d_request(self, order, card):
        """3D Secure isteği hazırla"""
        pass

    @abstractmethod
    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        pass

    @abstractmethod
    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        pass

    def make_request(self, url, data, headers=None, method='POST'):
        """HTTP isteği gönder"""
        try: 
            _logger.info(f"Gateway isteği: {url}")
            _logger.debug(f"Request data: {data}")

            if headers is None:
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}

            if method == 'POST':
                response = requests.post(url, data=data, headers=headers, timeout=self.timeout)
            else:
                response = requests.get(url, params=data, headers=headers, timeout=self.timeout)

            response.raise_for_status()
            
            _logger.info(f"Gateway yanıtı: {response.status_code}")
            _logger.debug(f"Response: {response.text[: 500]}")

            return response

        except requests.exceptions.Timeout:
            _logger.error("Gateway timeout")
            raise Exception("İstek zaman aşımına uğradı")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Gateway isteği hatası: {str(e)}")
            raise Exception(f"İstek hatası: {str(e)}")

    def format_amount(self, amount, include_decimal=True):
        """Tutarı gateway formatına çevir"""
        if include_decimal:
            # 100.50 -> 10050
            return str(int(amount * 100))
        else:
            # 100.50 -> 100.50
            return f"{amount:.2f}"

    def format_installment(self, installment):
        """Taksit sayısını formata çevir"""
        return str(installment) if installment > 1 else ''

    def map_currency(self, currency):
        """Para birimi kodunu map et"""
        currency_map = {
            'TRY': '949',
            'USD': '840',
            'EUR': '978',
            'GBP':  '826',
        }
        return currency_map.get(currency, '949')

    def normalize_response(self, raw_response):
        """Yanıtı standart formata çevir"""
        return {
            'success': raw_response.get('approved', False),
            'status':  'approved' if raw_response.get('approved') else 'declined',
            'order_id':  raw_response.get('order_id'),
            'transaction_id': raw_response.get('transaction_id'),
            'auth_code': raw_response.get('auth_code'),
            'host_ref_num': raw_response.get('host_ref_num'),
            'rrn': raw_response.get('rrn'),
            'error_code': raw_response.get('error_code'),
            'error_message': raw_response.get('error_message'),
            'md_status': raw_response.get('md_status'),
            'eci':  raw_response.get('eci'),
            'cavv': raw_response.get('cavv'),
            'xid': raw_response.get('xid'),
            'raw_response': raw_response,
        }

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        raise NotImplementedError("Bu gateway iptal işlemini desteklemiyor")

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        raise NotImplementedError("Bu gateway iade işlemini desteklemiyor")

    def prepare_status_request(self, order):
        """Durum sorgulama isteği hazırla"""
        raise NotImplementedError("Bu gateway durum sorgulama desteklemiyor")