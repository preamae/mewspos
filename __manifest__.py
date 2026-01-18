# -*- coding: utf-8 -*-
{
    'name': 'Mews Sanal POS Entegrasyonu',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Türk bankaları için sanal POS entegrasyonu',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'payment',
        'product',
        'website_sale',
        'web',  # Web modülünü ekleyin
    ],
    'data': [
        # 1. GÜVENLİK - EN ÖNCE
        'security/ir.model.access.csv',

        # 2. VIEWS (Model extend) - DATA'DAN ÖNCE
        'views/payment_provider_views.xml',
        'views/product_public_category_views.xml',
        'views/product_template_views.xml',
        'views/bin_views.xml',
        'views/installment_views.xml',
        'views/installment_calculator_wizard_views.xml',
        'views/refund_wizard_views.xml',

        # 3. DATA - EN SON (model extend edildikten sonra)
        'data/payment_provider_data.xml',

        # 4. TEMPLATES
        'views/templates.xml',
        'templates/payment_3d.xml',
        'templates/product_installments.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            'mews_pos/static/src/css/installment.css',
            'mews_pos/static/src/js/installment_calculator.js',
            # Kart formu ve taksit JS’i
            'mews_pos/static/src/js/payment_installments.js',
            # Kart tasarımı için CSS (istersen)
            'mews_pos/static/src/css/payment_card.css',
        ],
    },
    'external_dependencies': {
        'python': [
            'requests',
            'zeep',
            'cryptography',
            'lxml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
