# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields, api


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    parent_id = fields.Many2one('hr.payroll.structure', string='Parent')

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        if self.parent_id:
            parent_rules = self.parent_id.rule_ids
            existing_codes = self.rule_ids.mapped('code')
            new_rules = parent_rules.filtered(
                lambda r: r.code not in existing_codes
            )
            if new_rules:
                self.rule_ids = [(4, rule.id) for rule in new_rules]
                # Re-sort all rules by sequence
                self.rule_ids = self.rule_ids.sorted(key=lambda r: r.sequence)

    def _sync_parent_rules(self):
        if self.parent_id:
            parent_rules = self.parent_id.rule_ids
            existing_codes = self.rule_ids.mapped('code')
            new_rules = parent_rules.filtered(
                lambda r: r.code not in existing_codes
            )
            if new_rules:
                self.write({'rule_ids': [(4, rule.id) for rule in new_rules]})
                # Re-sort by sequence after sync
                sorted_rules = self.rule_ids.sorted(key=lambda r: r.sequence)
                self.write({
                    'rule_ids': [(5, 0, 0)] + [(4, rule.id) for rule in
                                               sorted_rules]
                })
