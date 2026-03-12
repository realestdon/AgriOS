# -*- coding:utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).

from odoo import models, fields,api


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def _satisfy_condition(self, localdict):
        """
        @param rule_id: id of hr.salary.rule to be tested
        @param contract_id: id of hr.contract to be tested
        @return: returns True if the given rule match the
        condition for the given contract. Return False otherwise.
        """
        localdict = dict(localdict, rule=self)  # include current rule object
        return super(HrSalaryRule, self)._satisfy_condition(localdict)

    def _compute_rule(self, localdict):
        """
        :param  rule_id: id  of rule  to compute
        :param localdict:  dictionary containing the environement
        in which to compute the rule
        return: returns a tuple build as the base/amount computed,
        the quantity and the rate :type: (float, float, float)
        """
        localdict = dict(localdict, rule=self)  # include current rule object
        return super(HrSalaryRule, self)._compute_rule(localdict)