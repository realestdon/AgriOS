# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields,api,_
from odoo.exceptions import ValidationError
from odoo.addons import decimal_precision as dp
from odoo.tools.safe_eval import safe_eval as Eval


class BaseDeductions(models.Model):
    _name = "base.deductions"
    _description = "After Tax Deduction"
    _order = "id, name asc"

    @api.depends('computation', 'fixed')
    def compute_deduction(self):
        for rec in self:
            if rec.computation == 'fixed':
                rec.amount = rec.fixed

            elif rec.computation == 'formula':
                baselocaldict = {
                    'result': None,
                    'employee': rec.employee_id,
                    'deduction': rec}
                localdict = dict(baselocaldict)
                try:
                    Eval(rec.formula, localdict, mode='exec', nocopy=True)
                except BaseException:
                    raise ValidationError(
                        _('Error in the formula defined for this\
                              deduction: %s\n [%s].') %
                        (rec.name, rec.formula))
                rec.amount = localdict['result']
            else:
                rec.amount = 0.00

    def _default_formula(self):
        return """
    # Available variables for use in formula:
    # --------------------------------------
    # employee: selected employee record
    # deduction: current deduction record
    # Note: returned value have to be set in the variable 'result'
    result = 0.00
    """

    def _default_company_id(self):
        return self.env.company.id
    def default_date(self):
        """ returns today's date and time """
        return fields.Datetime.now(self)

    @api.depends('deduction_id.name', 'employee_id.name')
    def compute_name(self):
        for rec in self:
            rec.name = f"{rec.deduction_id.name} ({rec.employee_id.name})"

    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        default=_default_company_id,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string="Currency",
        required=True)
    name = fields.Char(
        'Name',
        compute='compute_name',
        store=True)
    deduction_id = fields.Many2one(
        'deductions.type',
        'Type of Deduction',
        required=True)
    rule_id = fields.Many2one(
        'hr.salary.rule',
        related='deduction_id.rule_id',
        string='Payslip Rule')
    employee_id = fields.Many2one(
        'hr.employee',
        'Employee Name',
        required=True)
    fixed = fields.Float(
        'Fixed Amount',
        digits=dp.get_precision('Account'))
    computation = fields.Selection([('fixed',
                                     'Fixed Amount'),
                                    ('formula',
                                     'Use a Formula'),
                                    ],
                                   'Computation Method',
                                   required=True)
    amount = fields.Float(
        'Amount to Deduct',
        compute='compute_deduction',
        digits=dp.get_precision('Account'),
        store=True)
    formula = fields.Text(
        'Formula',
        default=_default_formula)
    date_start = fields.Datetime('Date Start', default=default_date)
    date_end = fields.Datetime('Date End')
    is_permanent = fields.Boolean('No Date End')
