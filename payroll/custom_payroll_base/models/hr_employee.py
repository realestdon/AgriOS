# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from pytz import timezone
from odoo import models, fields,api


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employee_no = fields.Char(
        'Internal Number',
        compute='_compute_employee_number',
        store=True,)
    payroll_no = fields.Char(
        'Payroll Number')
    deduction_ids = fields.One2many(
        'base.deductions',
        'employee_id',
        'Deductions')

    @api.depends('payroll_no')
    def _compute_employee_number(self):
        for rec in self:
            rec.employee_no = rec.payroll_no or str(rec.id).zfill(4)

    def compute_deductions(self, payslip, rule):
        for rec in self:
            user_tz = self.env.context.get('tz') or 'UTC'
            local_tz = timezone(user_tz)
            deductions = rec.deduction_ids
            recurring_domain = [
                ('date_end', '=', None),
                ('is_permanent', '=', True),
                ('rule_id', '=', rule.id),
                ('employee_id', 'in', rec.ids)
            ]

            recurring_deductions = deductions.search(recurring_domain).filtered(
                lambda m: m.date_start.astimezone(
                    local_tz).date() <= payslip.date_to
            )


            # For non-recurring deductions
            non_recurring_domain = [
                ('is_permanent', '=', False),
                ('rule_id', '=', rule.id),
                ('employee_id', 'in', rec.ids)
            ]
            non_recurring_deductions = []
            if non_recurring_domain:
                non_recurring_deductions = deductions.search(
                    non_recurring_domain).filtered(
                    lambda m: m.date_start.astimezone(
                        local_tz).date() <= payslip.date_to and
                              m.date_end.astimezone(
                                  local_tz).date() >= payslip.date_from
                )
            all_deductions = recurring_deductions + non_recurring_deductions

            return sum(all_deductions.mapped('amount'))
