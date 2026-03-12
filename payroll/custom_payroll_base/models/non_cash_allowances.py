# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields,api,_
from odoo.exceptions import ValidationError
from odoo.addons import decimal_precision as dp
from odoo.tools.safe_eval import safe_eval as Eval


class NonCashAllowances(models.Model):
    _name = "non.cash.allowances"
    _description = "Benefits"
    _order = "contract_id, name asc"


    @api.depends('computation', 'fixed')
    def compute_benefit(self):
        if self.computation == 'fixed':
            self.amount = self.fixed
        elif self.computation == 'formula':
            baselocaldict = {
                'result': None,
                'contract': self.contract_id,
                'benefit': self}
            localdict = dict(baselocaldict)
            try:
                Eval(self.formula, localdict, mode='exec', nocopy=True)
            except BaseException:
                raise ValidationError(
                    _('Wrong formula defined for this benefit: %s\n [%s].') %
                    (self.name, self.formula))
            self.amount = localdict['result']
        else:
            self.amount = 0.00

    @api.depends('benefit_id.name', 'contract_id.name')
    def compute_name(self):
        for rec in self:
            rec.name = f"{rec.benefit_id.name} ({rec.contract_id.name})"

    def default_date(self):
        """ returns today's date and time """
        return fields.Datetime.now(self)


    def _default_company_id(self):
        return self.env.company.id

    def _default_formula(self):
        return """
# Available variables for use in formula:
# --------------------------------------
# contract: the current contract record
# benefit: the current benefit record
# Note: returned value have to be set in the variable 'result'
result = 0.00
"""
    name = fields.Char(
        'Name',
        compute='compute_name',
        store=True)
    benefit_id = fields.Many2one(
        'benefit.type',
        'Type of Benefit',
        required=True)
    rule_id = fields.Many2one(
        related='benefit_id.rule_id',
        store=True,
        string="Salary Rule")
    contract_id = fields.Many2one(
        'hr.contract',
        'Contract',
        required=True)
    amount = fields.Float(
        'Computed Value',
        compute='compute_benefit',
        digits=dp.get_precision('Account'),
        store=True)
    computation = fields.Selection([('fixed',
                                     'Use the fixed value'),
                                    ('formula',
                                     'Use a Formula')],
                                   'Computation Method',
                                   required=True)
    fixed = fields.Float(
        'Fixed Value',
        digits=dp.get_precision('Account'))
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
    formula = fields.Text(
        'Formula',
        default=_default_formula)
    date_start = fields.Datetime('Date Start', default=default_date)
    date_end = fields.Datetime('Date End')
    is_permanent = fields.Boolean('No Date End')