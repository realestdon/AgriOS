# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields


class CashAllowancesType(models.Model):
    """ Base for Cash allowances model """
    _name = "cash.allowances.type"
    _description = "Cash Allowances Type"
    _order = "name asc"

    name = fields.Char('Name of Cash Allowance', required=True)
    rule_id = fields.Many2one('hr.salary.rule', 'Salary Rule',
        domain=[('sequence', '>=', 11),
                ('sequence', '<=', 24),
                ('active', '=', True)],
        help="""This is the Salary rule that will be used to compute the amount of\
                allowance in the payslip for each applicable employee""")
