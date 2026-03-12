# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dishon Kadoh (<dishon.kadoh@gmail.com>).
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PayeCalculatorController(http.Controller):

    # ── Page route ────────────────────────────────────────────────────────────
    @http.route(
        '/paye-calculator',
        type='http', auth='public', website=True, sitemap=True,
    )
    def paye_calculator(self, **kw):
        return request.render('custom_payroll_website.paye_calculator_page', {})

    # ── Structures for country dropdown ───────────────────────────────────────
    @http.route(
        '/paye/structures',
        type='json', auth='public', methods=['POST'], csrf=False,
    )
    def get_structures(self, country_id=None, **kw):
        """
        Return all hr.payroll.structure records, optionally filtered by
        country_id (matched via the structure's own country_id field).

        Response:
        {
          "structures": [
            { "id": 1, "name": "Kenya Basic", "country_id": 113,
              "country_name": "Kenya", "country_code": "KE" }
          ]
        }
        """
        try:
            Structure = request.env['hr.payroll.structure'].sudo()
            domain = []
            if country_id:
                domain.append(('country_id', '=', int(country_id)))

            structures = Structure.search(domain, order='name asc')
            result = []
            for s in structures:
                result.append({
                    'id':           s.id,
                    'name':         s.name,
                    'country_id':   s.country_id.id   if s.country_id else None,
                    'country_name': s.country_id.name if s.country_id else None,
                    'country_code': s.country_id.code if s.country_id else None,
                })
            return {'success': True, 'structures': result}
        except Exception as e:
            _logger.exception("PAYE /paye/structures error")
            return {'success': False, 'error': str(e), 'structures': []}

    # ── Countries that have at least one structure ─────────────────────────────
    @http.route(
        '/paye/countries',
        type='json', auth='public', methods=['POST'], csrf=False,
    )
    def get_countries(self, **kw):
        """
        Return distinct countries found on hr.payroll.structure.country_id,
        so the frontend can build the country selector from real data.
        """
        try:
            Structure = request.env['hr.payroll.structure'].sudo()
            structures = Structure.search([('country_id', '!=', False)])
            seen = {}
            for s in structures:
                c = s.country_id
                if c.id not in seen:
                    seen[c.id] = {
                        'id':   c.id,
                        'name': c.name,
                        'code': c.code,
                    }
            return {'success': True, 'countries': list(seen.values())}
        except Exception as e:
            _logger.exception("PAYE /paye/countries error")
            return {'success': False, 'error': str(e), 'countries': []}

    # ── Main compute endpoint ─────────────────────────────────────────────────
    @http.route(
        '/paye/compute',
        type='json', auth='public', methods=['POST'], csrf=False,
    )
    def compute_payroll(self, structure_id, gross_salary,
                        is_resident=True, is_secondary=False,
                        deduct_nssf=True, deduct_paye=True,
                        deduct_housing=True, deduct_nhif=True, **kw):
        """
        Given a structure_id and gross_salary, evaluate every active salary
        rule in that structure (in sequence order) and return a breakdown.

        We replicate Odoo's own localdict pattern so that rules written as:
            result = contract.wage * 0.06
            result = categories.BASIC * 0.30
        …work correctly.

        Rules that fail (bad Python, missing variables, etc.) are flagged
        individually rather than crashing the whole response.

        Response:
        {
          "success": true,
          "currency": "KES",
          "gross": 50000.0,
          "lines": [
            {
              "code":     "BASIC",
              "name":     "Basic Salary",
              "category": "BASIC",
              "amount":   50000.0,
              "appears_on_payslip": true,
              "error":    null
            },
            ...
          ],
          "net": 35000.0,
          "total_deductions": 15000.0
        }
        """
        try:
            gross_salary = float(gross_salary)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'gross_salary must be a number'}

        try:
            Structure = request.env['hr.payroll.structure'].sudo()
            struct = Structure.browse(int(structure_id))
            if not struct.exists():
                return {'success': False, 'error': f'Structure {structure_id} not found'}

            currency = struct.country_id.currency_id.name if (
                struct.country_id and struct.country_id.currency_id
            ) else 'KES'

            # Fetch rules ordered by sequence
            rules = request.env['hr.salary.rule'].sudo().search(
                [('struct_id', '=', struct.id), ('active', '=', True)],
                order='sequence asc',
            )

            # ── Build localdict ────────────────────────────────────────────
            # This mirrors what hr.payslip._get_payslip_lines() does.
            # We create lightweight proxy objects so rules can reference
            # contract.wage, employee.*, categories.XXX, etc.
            localdict = _build_localdict(gross_salary, struct,
                                          is_resident=bool(is_resident),
                                          is_secondary=bool(is_secondary),
                                          deduct_nssf=bool(deduct_nssf),
                                          deduct_paye=bool(deduct_paye),
                                          deduct_housing=bool(deduct_housing),
                                          deduct_nhif=bool(deduct_nhif))

            lines = []
            skipped_rules = []

            for salary_rule in rules:
                amount, error, skipped = _evaluate_rule(salary_rule, localdict)

                # Update categories accumulator for successfully computed rules
                cat_code = salary_rule.category_id.code if salary_rule.category_id else ''
                if cat_code and not error and not skipped:
                    prev = getattr(localdict['categories'], cat_code, 0.0)
                    setattr(localdict['categories'], cat_code, float(prev) + amount)

                # ── C020 sync ─────────────────────────────────────────────────
                # C020 (Allowed Deductions) must include NSSF (C012).
                # There is an intermediate rule in the base structure that copies
                # C012 → C020, but it may not be in this structure's rule set.
                # We keep C020 in sync with C012 after every rule so P080
                # (which computes C020 + C037 + C038) always has the right NSSF base.
                cats = localdict['categories']
                c012 = getattr(cats, 'C012', 0.0)
                if c012 > 0:
                    object.__setattr__(cats, 'C020', c012)

                # Store on ALL accumulator aliases so every cross-rule pattern works:
                #   rule.P046.amount  / rules.P046  / result_rules.P046['amount']
                if salary_rule.code and not error and not skipped:
                    result_obj = _RuleResult(amount)
                    setattr(localdict['rule'],         salary_rule.code, result_obj)
                    setattr(localdict['rules'],        salary_rule.code, result_obj)
                    setattr(localdict['result_rules'], salary_rule.code, result_obj)

                if skipped:
                    skipped_rules.append({
                        'code': salary_rule.code,
                        'name': salary_rule.name,
                        'reason': 'Requires employee contract data',
                    })
                    continue

                lines.append({
                    'code':               salary_rule.code,
                    'name':               salary_rule.name,
                    'category':           cat_code,
                    'category_name':      salary_rule.category_id.name if salary_rule.category_id else '',
                    'amount':             round(amount, 2),
                    'appears_on_payslip': salary_rule.appears_on_payslip,
                    'sequence':           salary_rule.sequence,
                    'error':              error,
                })

            # ── Apply deduction toggles ───────────────────────────────────
            DEDUCT_FLAGS = {
                'P046': bool(deduct_nssf),    # NSSF Tier I
                'P047': bool(deduct_nssf),    # NSSF Tier II
                'P055': bool(deduct_nssf),    # Total NSSF (employee)
                'P086': bool(deduct_paye),    # P.A.Y.E
                'P090': bool(deduct_paye),    # Tax Payable (sum)
                'P101': bool(deduct_paye),    # Net P.A.Y.E
                'P105': bool(deduct_paye),    # Net Tax Payable (sum) ← shown on payslip
                'P066': bool(deduct_nhif),    # S.H.I.F
                'P067': bool(deduct_housing), # Housing Levy
            }
            for line in lines:
                code = (line.get('code') or '').upper()
                if code in DEDUCT_FLAGS and not DEDUCT_FLAGS[code]:
                    line['amount']  = 0.0
                    line['toggled_off'] = True

            # ── Net and deductions using exact category codes ─────────────
            # Based on the actual salary structure category map:
            #   C034 = Net Pay Category      (populated by P116)
            #   C035 = Sum of Net Pay        (populated by P120) ← use this as net
            #   C031 = Sum of Net Tax Payable (PAYE after relief)
            #   C012 = Sum of NSSF Contributions
            #   C033 = Sum of Post Tax Deductions
            #   C037 = Housing Levy
            #   C038 = S.H.I.F
            #   C011 = NSSF Member Contributions
            #   C025 = Sum of Tax Payable

            # Net = last Net Pay rule result (P120 → C035)
            net_line = next(
                (l for l in reversed(lines)
                 if l['category'] in ('C035', 'C034') and not l['error']),
                None
            )
            if net_line:
                net = net_line['amount']
            else:
                # Fallback: C006 - C031(net tax) - C033(post-tax ded) - C012(NSSF)
                cats = localdict['categories']
                net = (getattr(cats, 'C006', gross_salary)
                       - getattr(cats, 'C031', 0.0)
                       - getattr(cats, 'C033', 0.0)
                       - getattr(cats, 'C012', 0.0))

            # Total deductions shown = NSSF + SHIF + Housing + Net PAYE
            # These are the deductions visible on the payslip
            DEDUCTION_CATS = {'C012', 'C031', 'C033', 'C037', 'C038'}
            total_deductions = sum(
                l['amount'] for l in lines
                if l['category'] in DEDUCTION_CATS and not l['error'] and l['appears_on_payslip']
            )
            # If nothing appears_on_payslip in those cats, use all lines in those cats
            if not total_deductions:
                total_deductions = sum(
                    l['amount'] for l in lines
                    if l['category'] in DEDUCTION_CATS and not l['error']
                )

            return {
                'success':          True,
                'currency':         currency,
                'gross':            gross_salary,
                'lines':            lines,
                'net':              round(net, 2),
                'total_deductions': round(total_deductions, 2),
                'skipped_rules':    skipped_rules,
            }

        except Exception as e:
            _logger.exception("PAYE /paye/compute error")
            return {'success': False, 'error': str(e)}


# ── Helpers ───────────────────────────────────────────────────────────────────

class _Browsable:
    """
    Generic proxy object.
    Returns a _CallableZero for any unknown attribute so rules can do:
        contract.some_field          → 0.0
        contract.some_method()       → 0.0
        contract.some_field.sub      → 0.0
        contract.some_field.search() → []
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return _CallableZero()

    def __bool__(self):
        return True

    def __float__(self):
        return 0.0

    def __int__(self):
        return 0


class _CallableZero:
    """
    A zero that is also callable and has attributes.
    Handles patterns like:
        contract.wage_type == 'monthly'   → _CallableZero() == 'monthly' → False
        env['model'].search([])           → _CallableZero()([]) → _CallableZero()
        inputs.BONUS.amount               → _CallableZero().amount → _CallableZero()
        rule.P001()                        → _CallableZero()() → _CallableZero()
    """
    def __call__(self, *args, **kwargs):
        return _CallableZero()

    def __getattr__(self, name):
        return _CallableZero()

    def __getitem__(self, key):
        return _CallableZero()

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0

    def __bool__(self):
        return False

    def __float__(self):
        return 0.0

    def __int__(self):
        return 0

    def __add__(self, other):
        return float(other)

    def __radd__(self, other):
        return float(other)

    def __sub__(self, other):
        return -float(other)

    def __rsub__(self, other):
        return float(other)

    def __mul__(self, other):
        return 0.0

    def __rmul__(self, other):
        return 0.0

    def __truediv__(self, other):
        return 0.0

    def __rtruediv__(self, other):
        return 0.0

    def __eq__(self, other):
        # Allow comparisons: contract.wage_type == 'monthly' → False
        if isinstance(other, (int, float)) and other == 0:
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "0.0"

    def __str__(self):
        return "0.0"


class _WorkedDaysCollection:
    """
    Proxy for worked_days.
    Rules use: worked_days.number_of_days, worked_days.number_of_hours
    and also: worked_days.WORK100.number_of_days (line type code access)
    """
    def __init__(self, number_of_days=26.0, number_of_hours=208.0):
        self.number_of_days  = number_of_days
        self.number_of_hours = number_of_hours

    def __getattr__(self, name):
        # worked_days.WORK100 → return sub-object with same day/hour values
        return _WorkedDaysCollection(self.number_of_days, self.number_of_hours)

    def __float__(self):
        return self.number_of_days

    def __add__(self, other):
        return self.number_of_days + other

    def __radd__(self, other):
        return other + self.number_of_days

    def __bool__(self):
        return True


class _RuleAccumulator:
    """
    Proxy for both 'rule' (singular) and 'rules' (plural).
    Supports:
        rule.P001.amount      — attribute access
        rule.P001()           — callable (some rules call the result)
        rule['P001'].amount   — dict-style access
    Unknown rules return _RuleResult(0.0) so unset rules evaluate to 0.
    """
    def __getattr__(self, name):
        return _RuleResult(0.0)

    def __getitem__(self, key):
        return _RuleResult(0.0)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


class _RuleResult:
    """
    Wraps a computed rule amount.
    Must support:
        result = rule.P001.amount        → float
        result = rule.P001()             → float  (callable!)
        result = rule.P001 * 0.06        → float arithmetic
        result = rule.P001.total         → float
    """
    def __init__(self, amount):
        self.amount = float(amount)
        self.total  = float(amount)

    # ── callable: rule.P001() ─────────────────────────────────────────────────
    def __call__(self, *args, **kwargs):
        return self.amount

    # ── numeric ops ──────────────────────────────────────────────────────────
    def __float__(self):   return self.amount
    def __int__(self):     return int(self.amount)
    def __bool__(self):    return bool(self.amount)
    def __repr__(self):    return f"_RuleResult({self.amount})"

    def __add__(self, o):      return self.amount + float(o)
    def __radd__(self, o):     return float(o) + self.amount
    def __sub__(self, o):      return self.amount - float(o)
    def __rsub__(self, o):     return float(o) - self.amount
    def __mul__(self, o):      return self.amount * float(o)
    def __rmul__(self, o):     return float(o) * self.amount
    def __truediv__(self, o):  return self.amount / float(o)
    def __rtruediv__(self, o): return float(o) / self.amount
    def __neg__(self):         return -self.amount
    def __abs__(self):         return abs(self.amount)

    def __eq__(self, o):   return self.amount == float(o) if isinstance(o, (int, float)) else False
    def __lt__(self, o):   return self.amount < float(o)
    def __le__(self, o):   return self.amount <= float(o)
    def __gt__(self, o):   return self.amount > float(o)
    def __ge__(self, o):   return self.amount >= float(o)

    def __getattr__(self, name):
        # Catch-all so rule.P001.some_unknown_attr → 0.0
        return _CallableZero()

    def __getitem__(self, key):
        # result_rules.P015['amount'] → self.amount
        if key == 'amount':
            return self.amount
        if key == 'total':
            return self.total
        return self.amount  # default: treat any key as the amount


class _CategoriesProxy:
    """
    Proxy for the 'categories' accumulator in salary rule localdict.
    Returns plain float 0.0 for unknown codes — rules do arithmetic directly:
        PAY = categories.C006   →  float
        if PAY <= LEL:          →  float comparison
    Supports both attribute and item access:
        categories.C006         →  float
        categories['C006']      →  float  (some rules use dict-style)
    """
    def __init__(self, seed=None):
        if seed:
            for k, v in seed.items():
                object.__setattr__(self, k, float(v))

    def __getattr__(self, name):
        return 0.0

    def __getitem__(self, key):
        return getattr(self, key, 0.0)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __setattr__(self, name, value):
        try:
            object.__setattr__(self, name, float(value))
        except (TypeError, ValueError):
            object.__setattr__(self, name, 0.0)

    def __bool__(self):
        return True


def _build_localdict(gross_salary, struct,
                     is_resident=True, is_secondary=False,
                     deduct_nssf=True, deduct_paye=True,
                     deduct_housing=True, deduct_nhif=True):
    """
    Build the localdict that mirrors hr.payslip._get_payslip_lines().

    Key fixes based on actual salary rules:
      - employee.resident (not is_resident) — used in NSSF/SHIF/Housing conditions
      - categories.C006 pre-seeded as gross_salary — rules use this for gross pay
      - categories.C023 pre-seeded as gross_salary — taxable pay (PAYE uses this)
      - contract.tax_applicable = 'paye' — PAYE condition checks this
      - result_rules provided as another accumulator alias (P066 uses result_rules.P015)
    """
    contract = _Browsable(
        wage=gross_salary,
        basic_salary=gross_salary,
        gross_salary=gross_salary,
        tax_applicable='paye',                          # P086 condition
        schedule_pay='monthly',                         # P101 condition: contract.schedule_pay in ['monthly']
        structure_type_id=_Browsable(default_schedule_pay='monthly'),  # P001 condition
        resource_calendar_id=_Browsable(hours_per_week=40, work_time_rate=1.0),
    )

    employee = _Browsable(
        name='Preview Employee',
        gender='male',
        birthday=False,
        identification_id='',
        active=True,
        km_home_work=0,
        resident=is_resident,
        is_resident=is_resident,
        is_secondary_employee=is_secondary,
        secondary_employee=is_secondary,
        employee_type='employee',                       # P091 condition: employee.employee_type == 'employee'
        company_id=_Browsable(currency_id=_Browsable(name='KES')),
        department_id=_Browsable(name=''),
        job_id=_Browsable(name=''),
    )

    # payslip.paid_amount = gross_salary — Basic Pay rule uses this directly
    payslip = _Browsable(
        name='Preview Payslip',
        number='',
        paid_amount=gross_salary,   # result = payslip.paid_amount
        wage=gross_salary,
    )

    # Categories proxy — NOT pre-seeded. Rules run in sequence order so
    # by the time NSSF/SHIF/Housing (seq 46+) run, the Gross Pay rule
    # (seq ~5) will have already set categories.C006 through accumulation.
    # Pre-seeding caused C006 and C023 to be double-counted (seed + rule result).
    categories = _CategoriesProxy()

    rule_accumulator = _RuleAccumulator()
    worked_days      = _WorkedDaysCollection(number_of_days=26.0, number_of_hours=208.0)
    inputs           = _Browsable()
    env              = struct.env

    return {
        'contract':      contract,
        'employee':      employee,
        'categories':    categories,
        'rule':          rule_accumulator,    # singular
        'rules':         rule_accumulator,    # plural
        'result_rules':  rule_accumulator,    # P066 uses: result_rules.P015['amount']
        'payslip':       payslip,
        'worked_days':   worked_days,
        'inputs':        inputs,
        'env':           env,
        'is_resident':   is_resident,
        'is_secondary':  is_secondary,
        'result':        0.0,
        'result_rate':   100.0,
        'result_qty':    1.0,
    }



# Patterns that indicate a rule requires a real contract/payslip to compute.
# We detect these and skip them gracefully rather than showing an error.
_CONTRACT_METHOD_PATTERNS = (
    'compute_cash_allowances',
    'compute_non_cash_benefits',
    'compute_deductions',
    'compute_benefits',
    '.date_from',
    '.date_to',
    'payslip.date',
    'cash_all.search',
    'benefits.search',
    'rec.cash_allowances',
    'rec.benefits',
)

# Category codes that represent earnings we can derive from gross salary alone.
# All others that require contract methods will be skipped.
_SALARY_ONLY_CATEGORIES = {'BASIC', 'GROSS', 'ALW', 'DED', 'NET', 'COMP'}


def _rule_needs_contract(code_str):
    """Return True if the rule's Python code calls contract-specific methods."""
    if not code_str:
        return False
    return any(pattern in code_str for pattern in _CONTRACT_METHOD_PATTERNS)


def _evaluate_rule(rule_record, localdict):
    """
    Evaluate a single hr.salary.rule against localdict.
    Returns (amount, error, skipped).

    Steps mirror Odoo's own hr.payslip._get_payslip_lines():
      1. Check condition (none / always / python) — skip rule if False
      2. Evaluate amount (fix / percentage / code)

    Condition semantics (matching Odoo behaviour):
      result = True          → run rule
      result = False         → skip rule
      result = categories.C020  → run if C020 > 0, skip if C020 == 0.0
      result = categories.C001  → run if C001 > 0 (P010 pattern)

    IMPORTANT: P080 condition is `result = categories.C020` which is 0.0
    when there are no pension deductions. We must still run P080 because
    it computes C037+C038 (Housing+SHIF) regardless of C020.
    Solution: for rules whose condition is ONLY a category read, treat 0.0
    as True (the rule should still run and produce 0 if needed).
    We detect this by checking if the condition is a pure `result = categories.XXX`
    expression — in that case we always run the rule.
    """
    try:
        # ── Step 1: evaluate condition ────────────────────────────────────────
        condition_select = rule_record.condition_select  # 'none'|'range'|'python'

        if condition_select == 'python':
            condition_code = (rule_record.condition_python or '').strip()

            # Skip rules that call contract methods needing real employee data
            if _rule_needs_contract(condition_code):
                return 0.0, None, True

            if condition_code:
                # Detect pure "result = categories.CXXX" conditions.
                # These are used as pass-through guards in Odoo (run only when
                # that category has been computed). In our calculator they should
                # always run — the amount code handles the 0 case.
                import re as _re
                _pure_cat = _re.fullmatch(
                    r'result\s*=\s*categories\.\w+', condition_code)
                if not _pure_cat:
                    local = dict(localdict)
                    local['result'] = False
                    local['env']    = localdict['env']
                    exec(condition_code, local)  # noqa: S102
                    condition_result = local.get('result', False)
                    # Only skip on explicit False/None/0 when condition is a
                    # boolean expression (True/False), not a numeric guard.
                    # If result is a non-zero number, treat as True.
                    # If result is exactly False (bool), skip.
                    if condition_result is False:
                        return 0.0, None, False  # condition not met

        # ── Step 2: evaluate amount ───────────────────────────────────────────
        amount_select = rule_record.amount_select  # 'fix'|'percentage'|'code'

        if amount_select == 'fix':
            return float(rule_record.amount_fix or 0.0), None, False

        elif amount_select == 'percentage':
            base_expr = (rule_record.amount_percentage_base or '').strip()
            if base_expr:
                local = dict(localdict)
                local['result'] = 0.0
                local['env']    = localdict['env']
                exec(f"_base = {base_expr}", local)  # noqa: S102
                base = float(local.get('_base', 0.0) or 0.0)
            else:
                base = float(localdict['contract'].wage)
            return base * (float(rule_record.amount_percentage or 0.0) / 100.0), None, False

        elif amount_select == 'code':
            code = (rule_record.amount_python_compute or '').strip()
            if not code:
                return 0.0, None, False

            if _rule_needs_contract(code):
                return 0.0, None, True  # needs real contract — skip

            local = dict(localdict)
            local['result']      = 0.0
            local['result_rate'] = 100.0
            local['result_qty']  = 1.0
            local['env']         = localdict['env']

            exec(code, local)  # noqa: S102

            amount = float(local.get('result', 0.0) or 0.0)
            rate   = float(local.get('result_rate', 100.0) or 100.0)
            qty    = float(local.get('result_qty', 1.0) or 1.0)
            return amount * rate / 100.0 * qty, None, False

        return 0.0, None, False

    except Exception as e:
        _logger.warning(
            "PAYE calculator: rule '%s' (%s) evaluation error: %s",
            rule_record.name, rule_record.code, e,
        )
        return 0.0, str(e), False