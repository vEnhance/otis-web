# Create your tests here.

from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory

from exams.calculator import expr_compute


class ArithmeticTest(OTISTestCase):
	def checkCalculator(self, expr: str, out: float):
		v = expr_compute(expr)
		assert v is not None
		self.assertAlmostEquals(v, out)

	def test_arithmetic(self):
		self.checkCalculator('1/3^4', 1 / 81)
		self.checkCalculator('sin(pi)', 0)
		self.checkCalculator('sqrt(1/2)-cos(pi/4)', 0)
		self.checkCalculator('(2*sqrt(2))^2 - 4^(3/2)', 0)
		self.checkCalculator('16900/4*pi', 13273.2289614)

	def test_pdf(self):
		pass


class ExamTest(OTISTestCase):
	def test_pdf(self):
		alice = StudentFactory.create(semester__exam_family='Waltz')
		self.login(alice)
		# TODO freeze time
