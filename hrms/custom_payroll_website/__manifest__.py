# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

{
    'name': 'Kenya Payroll Calculator',
    'version': '1.0',
    'sequence': -3,
    'depends': [
        'website',
        'om_hr_payroll',
        'custom_payroll_ke'
    ],
    'license': 'LGPL-3',
    'data': [
        'views/payroll_calculator_template.xml',
        'views/paye_calculator_menus.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'custom_payroll_website/static/src/js/payroll_calculator.js',
            'custom_payroll_website/static/src/css/payroll_calculator.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}