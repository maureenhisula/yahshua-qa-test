"""
Backend unit tests for payroll calculation modules.

Run with: python manage.py test tests
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse

from payroll_app.calculations.tax_calculator import (
    calculate_annual_income_tax,
    calculate_monthly_withholding_tax,
)
from payroll_app.calculations.sss_calculator import calculate_sss
from payroll_app.calculations.philhealth_calculator import calculate_philhealth, calculate_pagibig
from payroll_app.models import Employee


class TaxCalculatorTests(TestCase):

    def test_zero_salary_no_tax(self):
        """Salary of 0 should have no tax."""
        self.assertEqual(calculate_annual_income_tax(Decimal('0')), Decimal('0.00'))

    def test_below_250000_no_tax(self):
        """Annual salary below 250,000 should be tax-exempt."""
        self.assertEqual(calculate_annual_income_tax(Decimal('200000')), Decimal('0.00'))

    def test_exactly_250000_should_be_exempt(self):
        """
        Annual salary of EXACTLY 250,000 should be tax-exempt (0%).
        BUG #1: This test will FAIL because the code uses >= instead of >.
        The boundary 250,000 is incorrectly taxed at 15%.
        """
        result = calculate_annual_income_tax(Decimal('250000'))
        self.assertEqual(result, Decimal('0.00'),
                         "Annual salary of 250,000 should be tax-exempt (0%), not taxed at 15%.")

    def test_250001_taxed_at_15_percent(self):
        """Annual salary of 250,001 should be taxed at 15% on the excess."""
        result = calculate_annual_income_tax(Decimal('250001'))
        expected = (Decimal('250001') - Decimal('250000')) * Decimal('0.15')
        self.assertAlmostEqual(float(result), float(expected), places=2)

    def test_400000_bracket(self):
        """Annual salary of 400,000 should be in the 15% bracket."""
        result = calculate_annual_income_tax(Decimal('400000'))
        expected = (Decimal('400000') - Decimal('250000')) * Decimal('0.15')
        self.assertAlmostEqual(float(result), float(expected.quantize(Decimal('0.01'))), places=2)

    def test_500000_bracket(self):
        """Annual salary of 500,000 → 22,500 + 20% of excess over 400,000."""
        result = calculate_annual_income_tax(Decimal('500000'))
        expected = Decimal('22500') + (Decimal('500000') - Decimal('400000')) * Decimal('0.20')
        self.assertAlmostEqual(float(result), float(expected), places=2)

    def test_monthly_withholding_for_25000_salary(self):
        """Monthly salary of 25,000 → annual 300,000 → some tax."""
        result = calculate_monthly_withholding_tax(Decimal('25000'))
        # Annual 300,000 → 15% of (300,000 - 250,000) = 7,500/year → 625/month
        self.assertGreaterEqual(float(result), 0)


class SSSCalculatorTests(TestCase):

    def test_zero_salary(self):
        result = calculate_sss(Decimal('0'))
        self.assertEqual(result['employee'], Decimal('0.00'))
        self.assertEqual(result['employer'], Decimal('0.00'))

    def test_salary_below_3250(self):
        """Salary below 3,250 uses minimum MSC of 3,000."""
        result = calculate_sss(Decimal('3000'))
        self.assertEqual(result['employee'], Decimal('135.00'))   # 3000 * 4.5%
        self.assertEqual(result['employer'], Decimal('285.00'))   # 3000 * 9.5%

    def test_salary_ceiling(self):
        """Salary above 19,750 uses maximum MSC of 20,000."""
        result = calculate_sss(Decimal('50000'))
        self.assertEqual(result['employee'], Decimal('900.00'))   # 20000 * 4.5%
        self.assertEqual(result['employer'], Decimal('1900.00'))  # 20000 * 9.5%

    def test_salary_25000_uses_ceiling(self):
        """25,000 salary should hit MSC ceiling."""
        result = calculate_sss(Decimal('25000'))
        self.assertEqual(result['employee'], Decimal('900.00'))


class PhilHealthCalculatorTests(TestCase):

    def test_zero_salary(self):
        result = calculate_philhealth(Decimal('0'))
        self.assertEqual(result['employee'], Decimal('0.00'))

    def test_floor_applied(self):
        """Salary below 10,000 uses minimum base of 10,000."""
        result = calculate_philhealth(Decimal('5000'))
        # Floor: 10,000 * 5% = 500 total, 250 each
        self.assertEqual(result['employee'], Decimal('250.00'))
        self.assertEqual(result['employer'], Decimal('250.00'))

    def test_normal_salary(self):
        """45,000 salary: 45,000 * 5% = 2,250 total, 1,125 each."""
        result = calculate_philhealth(Decimal('45000'))
        self.assertEqual(result['employee'], Decimal('1125.00'))
        self.assertEqual(result['employer'], Decimal('1125.00'))

    def test_ceiling_applied(self):
        """Salary above 100,000 uses ceiling of 100,000."""
        result = calculate_philhealth(Decimal('300000'))
        # Ceiling: 100,000 * 5% = 5,000 total, 2,500 each
        self.assertEqual(result['employee'], Decimal('2500.00'))
        self.assertEqual(result['employer'], Decimal('2500.00'))


class PagIbigCalculatorTests(TestCase):

    def test_zero_salary(self):
        result = calculate_pagibig(Decimal('0'))
        self.assertEqual(result['employee'], Decimal('0.00'))

    def test_salary_above_5000_capped_at_200(self):
        """Salary above 5,000: 2% capped at 200."""
        result = calculate_pagibig(Decimal('25000'))
        self.assertEqual(result['employee'], Decimal('200.00'))
        self.assertEqual(result['employer'], Decimal('200.00'))

    def test_low_salary_not_capped(self):
        """Salary of 4,000: 2% = 80, not capped."""
        result = calculate_pagibig(Decimal('4000'))
        self.assertEqual(result['employee'], Decimal('80.00'))


class EmployeeAPITests(TestCase):

    def setUp(self):
        self.client = Client()
        self.employee = Employee.objects.create(
            first_name='Test',
            last_name='User',
            email='test@example.com',
            position='Developer',
            department='Engineering',
            employment_type='regular',
            monthly_salary=Decimal('50000'),
            date_hired='2023-01-01',
        )

    def test_list_employees(self):
        response = self.client.get('/api/employees/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_get_employee(self):
        response = self.client.get(f'/api/employees/{self.employee.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test@example.com')

    def test_get_nonexistent_employee_returns_404(self):
        response = self.client.get('/api/employees/99999/')
        self.assertEqual(response.status_code, 404)

    def test_calculate_payroll_missing_employee_should_return_404(self):
        """
        BUG #3: This test will FAIL because the view returns HTTP 200
        when the employee is not found instead of HTTP 404.
        """
        import json
        response = self.client.post(
            '/api/calculate-payroll/',
            data=json.dumps({'employee_id': 99999, 'period_month': 1, 'period_year': 2025}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404,
                         "Missing employee should return 404, not 200.")

    def test_calculate_payroll_success(self):
        import json
        response = self.client.post(
            '/api/calculate-payroll/',
            data=json.dumps({
                'employee_id': self.employee.pk,
                'period_month': 3,
                'period_year': 2025,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('net_pay', data)
        self.assertIn('income_tax', data)

class PayrollAssessmentAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.employee = Employee.objects.create(
            first_name='Assessment',
            last_name='User',
            email='assessment@example.com',
            position='QA Tester',
            department='QA',
            employment_type='regular',
            monthly_salary=Decimal('50000'),
            date_hired='2026-01-01',
        )

    def test_valid_payroll_calculation(self):
        response = self.client.post(
            '/api/calculate-payroll/',
            data={
                'employee_id': self.employee.pk,
                'period_month': 9,
                'period_year': 2026,
            },
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 201])
        data = response.json()
        self.assertEqual(data['basic_salary'], '50000.00')
        self.assertIn('net_pay', data)
        self.assertIn('income_tax', data)

    def test_period_month_above_maximum_rejected(self):
        response = self.client.post(
            '/api/calculate-payroll/',
            data={
                'employee_id': self.employee.pk,
                'period_month': 13,
                'period_year': 2026,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_period_year_below_minimum_rejected(self):
        response = self.client.post(
            '/api/calculate-payroll/',
            data={
                'employee_id': self.employee.pk,
                'period_month': 9,
                'period_year': 1999,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_salary_rejected(self):
        response = self.client.post(
            '/api/calculate-payroll/',
            data={
                'employee_id': self.employee.pk,
                'period_month': 9,
                'period_year': 2026,
                'override_salary': 'abc',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_salary_should_be_rejected(self):
        response = self.client.post(
            '/api/calculate-payroll/',
            data={
                'employee_id': self.employee.pk,
                'period_month': 9,
                'period_year': 2026,
                'override_salary': '-1000.00',
            },
            content_type='application/json',
        )

        self.assertEqual(
            response.status_code,
            400,
            "Negative salary should be rejected with HTTP 400.",
        )
