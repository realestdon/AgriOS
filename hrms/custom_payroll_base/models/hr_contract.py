# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from pytz import timezone
from datetime import datetime
from odoo import models, fields, api, _


class HrContract(models.Model):
    _inherit = "hr.contract"

    benefits = fields.One2many(
        'non.cash.allowances',
        'contract_id',
        'Benefits')
    cash_allowances = fields.One2many(
        'cash.allowances',
        'contract_id',
        'Cash Allowances')

    def compute_cash_allowances(self, payslip, rule):
        for rec in self:
            user_tz = self.env.context.get('tz') or 'UTC'
            local_tz = timezone(user_tz)
            cash_all = rec.cash_allowances

            payslip_start_dt = datetime.combine(payslip.date_from,
                                                datetime.min.time()).replace(
                tzinfo=local_tz)
            payslip_end_dt = datetime.combine(payslip.date_to,
                                              datetime.min.time()).replace(
                tzinfo=local_tz)

            recurring_domain = [
                ('is_permanent', '=', True),
                ('rule_id', '=', rule.id),
                ('contract_id', 'in', rec.ids)
            ]

            recurring_allowances = cash_all.search(recurring_domain).filtered(
                lambda m: m.date_start.astimezone(
                    local_tz).date() <= payslip.date_to
            )

            # For non-recurring deductions
            non_recurring_domain = [
                ('is_permanent', '=', False),
                ('rule_id', '=', rule.id),
                ('contract_id', 'in', rec.ids)
            ]
            non_recurring_allowances = []

            if non_recurring_domain:
                non_recurring_allowances = cash_all.search(
                    non_recurring_domain).filtered(
                    lambda m: m.date_start.astimezone(
                        local_tz).date() <= payslip.date_to and
                              m.date_end.astimezone(
                                  local_tz).date() >= payslip.date_from
                )

            all_allowances = recurring_allowances + non_recurring_allowances

            return sum(all_allowances.mapped('amount'))

    def compute_non_cash_benefits(self, payslip, rule):
        for rec in self:
            user_tz = self.env.context.get('tz') or 'UTC'
            local_tz = timezone(user_tz)
            cash_all = rec.benefits

            payslip_start_dt = datetime.combine(payslip.date_from,
                                                datetime.min.time()).replace(
                tzinfo=local_tz)
            payslip_end_dt = datetime.combine(payslip.date_to,
                                              datetime.min.time()).replace(
                tzinfo=local_tz)

            recurring_domain = [
                ('is_permanent', '=', True),
                ('rule_id', '=', rule.id),
                ('contract_id', 'in', rec.ids)
            ]

            recurring_allowances = cash_all.search(recurring_domain).filtered(
                lambda m: m.date_start.astimezone(
                    local_tz).date() <= payslip.date_to
            )

            # For non-recurring deductions
            non_recurring_domain = [
                ('is_permanent', '=', False),
                ('rule_id', '=', rule.id),
                ('contract_id', 'in', rec.ids)
            ]
            non_recurring_allowances = []

            if non_recurring_domain:
                non_recurring_allowances = cash_all.search(
                    non_recurring_domain).filtered(
                    lambda m: m.date_start.astimezone(
                        local_tz).date() <= payslip.date_to and
                              m.date_end.astimezone(
                                  local_tz).date() >= payslip.date_from
                )

            all_allowances = recurring_allowances + non_recurring_allowances

            return sum(all_allowances.mapped('amount'))
