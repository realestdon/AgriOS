# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields


class BenefitType(models.Model):
    """ Base for benefits model """
    _name = "benefit.type"
    _description = "Benefit Type"
    _order = "name asc"

    name = fields.Char('Name of Benefit', required=True)
    rule_id = fields.Many2one('hr.salary.rule', 'Payroll Rule',
                              domain=[('sequence', '<=', '36'),
                                      ('sequence', '>=', '31'),
                                      ('active', '=', True)],
                              help='Pick a salary rule that will be used to compute this \
        type of benefit in the payslip',)
