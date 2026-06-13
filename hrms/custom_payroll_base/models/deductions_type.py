# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields


class DeductionsType(models.Model):
    """ Base for post tax deductions model"""
    _name = "deductions.type"
    _description = "After Tax Deduction Type"
    _order = "name asc"

    name = fields.Char('Name of Deduction', required=True)
    rule_id = fields.Many2one('hr.salary.rule', 'Salary Rule',
                              domain=[('sequence', '>=', 107),
                                      ('sequence', '<=', 114),
                                      ('active', '=', True)],
                              help="""This is the payslip rule which is used to calculate \
        how much of this deduction will be effected in the payroll.\
        Try to match the name of the rule with the name of the \
        deduction you are creating""")
