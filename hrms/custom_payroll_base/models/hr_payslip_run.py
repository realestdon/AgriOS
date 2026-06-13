# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields, api, _


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    name = fields.Char(required=True, compute="_compute_name",store=True)

    # @api.depends('date_start', 'date_end', 'company_id')
    @api.depends('date_start', 'date_end')
    def _compute_name(self):
        for rec in self:
            month, year = '', ''

            if rec.date_start:
                month = rec.date_start.strftime('%B')
                year = rec.date_start.strftime('%Y')

            if rec.date_end:
                end_month = rec.date_end.strftime('%B')
                end_year = rec.date_end.strftime('%Y')

                if month and end_month != month:
                    month = f"{month} and {end_month}"
                elif not month:
                    month = end_month

                if year and end_year != year:
                    year = f"{year} - {end_year}"
                elif not year:
                    year = end_year

            # company_name = rec.company_id.display_name or ''
            # parts = [p for p in [f"{month} {year}".strip(), company_name] if p]
            parts = [p for p in [f"{month} {year}".strip()] if p]
            rec.name = " - ".join(parts) if parts else "New Batch"