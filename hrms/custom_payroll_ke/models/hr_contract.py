
from odoo import models, fields
# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

TAX_APPLICABLE = [('paye',
                 'P.A.Y.E - Pay As You Earn'),
                ('wht',
                 'Withholding Tax')]
class HrContract(models.Model):
    _inherit = "hr.contract"

    tax_applicable = fields.Selection(
            TAX_APPLICABLE,
            'Applicable Tax',
            required=True,
            default='paye')
