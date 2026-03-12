
from odoo import models, fields
# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    resident = fields.Boolean(
        'Resident?',
        default=True)
