# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

{
    'name': 'Custom Payroll KE',
    'version': '1.0',
    'sequence': -2,
    'summary': 'Kenya payroll localization built on the Custom Payroll Base module',
    'description': '''
Kenya Payroll Localization Module

This module extends the Custom Payroll Base module to support payroll processing
in Kenya. It introduces Kenya-specific payroll structures, salary rules, and
statutory deductions required for compliance with Kenyan labor and tax laws.

Key features include:
- Kenya payroll structure configuration
- PAYE tax computation
- NSSF contributions
- NHIF deductions
- Support for Kenya-specific allowances and benefits
- Integration with the base payroll engine for shared global payroll rules

The module is designed to work with the Custom Payroll Base module, allowing
organizations to maintain common payroll logic across multiple countries while
adding country-specific payroll requirements for Kenya.
''',
    'category': 'Human Resources/Payroll',
    'author': 'Dishon Kadoh',
    'website': 'https://dishonkadoh.com/',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'om_hr_payroll',
        'custom_payroll_base'
    ],
    'data': [
        'data/hr_payroll_structure_type.xml',
        'data/hr_payroll_structure.xml',
        'data/hr_salary_rule_category.xml',
        'data/hr_salary_rule.xml',
        'views/hr_employee.xml',
        'views/hr_contract.xml',
    ],
    'installable': True,
    'application': True,
}