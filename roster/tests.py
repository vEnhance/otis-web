from core.factories import UnitFactory, UnitGroupFactory, UserFactory  # NOQA
from django.conf import settings
from django.shortcuts import get_object_or_404
from otisweb.tests import OTISTestCase

from roster.factories import AssistantFactory, InvoiceFactory, RegistrationContainerFactory, StudentFactory, StudentRegistrationFactory  # NOQA
from roster.models import Student, StudentRegistration

from .admin import build_students


class RosterTest(OTISTestCase):
	def test_curriculum(self):
		staff = AssistantFactory.create()
		alice = StudentFactory.create(assistant=staff)

		unitgroups = UnitGroupFactory.create_batch(4)
		for unitgroup in unitgroups:
			for letter in 'BDZ':
				UnitFactory.create(code=letter + unitgroup.subject[0] + 'W', group=unitgroup)

		self.login(alice)
		self.assertContains(self.get('currshow', alice.pk), text="you are not an instructor")

		self.login(staff)
		self.assertNotContains(self.get('currshow', alice.pk), text="you are not an instructor")

		data = {
			'group-0': [1, ],
			'group-1': [4, 6],
			'group-3': [10, 11, 12],
		}
		self.post('currshow', alice.pk, data=data)
		self.assertEqual(len(get_object_or_404(Student, pk=alice.pk).curriculum.all()), 6)

	def test_finalize(self):
		alice = StudentFactory.create(newborn=True)
		self.login(alice)
		self.assertContains(
			self.post('finalize', alice.pk, data={'submit': True}), 'You should select some units'
		)
		units = UnitFactory.create_batch(20)
		alice.curriculum.set(units)
		self.assertContains(
			self.post('finalize', alice.pk, data={}), 'Your curriculum has been finalized!'
		)
		self.assertEqual(alice.unlocked_units.count(), 3)

	def test_invoice(self):
		alice = StudentFactory.create(semester__show_invoices=True)
		self.login(alice)
		InvoiceFactory.create(
			student=alice,
			preps_taught=2,
			hours_taught=8.4,
			adjustment=-100,
			extras=100,
			total_paid=400
		)
		response = self.get('invoice')
		self.assertContains(response, "752.00")
		checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
		self.assertEqual(len(checksum), 36)
		self.assertContains(response, checksum)

	def test_invoice_standalone(self):
		alice = StudentFactory.create()
		InvoiceFactory.create(student=alice)
		self.assertGet20X(
			'invoice-standalone', alice.pk, alice.get_checksum(settings.INVOICE_HASH_KEY)
		)
		self.assertGetDenied('invoice-standalone', alice.pk, '?')
		self.login(alice)
		self.assertGetDenied('invoice-standalone', alice.pk, '?')

	def test_master_schedule(self):
		alice = StudentFactory.create()
		units = UnitFactory.create_batch(30)
		alice.curriculum.set(units[0:18])
		self.login(UserFactory.create(is_staff=True))
		self.assertContains(self.get('master-schedule'), text=alice.user.first_name, count=18)

	def test_update_invoice(self):
		firefly = AssistantFactory.create()
		alice = StudentFactory.create(assistant=firefly)
		InvoiceFactory.create(student=alice)
		self.login(firefly)
		self.assertGet20X('edit-invoice', alice.pk)
		self.assertPost20X(
			'edit-invoice',
			alice.pk,
			data={
				'preps_taught': 2,
				'hours_taught': 8.4,
				'adjustment': 0,
				'extras': 0,
				'total_paid': 1152,
				'forgive': False
			}
		)

	def test_inquiry(self):
		firefly = AssistantFactory.create()
		alice = StudentFactory.create(assistant=firefly)
		units = UnitFactory.create_batch(20)
		self.login(alice)
		for i in range(6):
			resp = self.post(
				"inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "UNLOCK",
				}
			)
			self.assertContains(resp, "Petition automatically approved")
		self.assertEqual(alice.curriculum.count(), 6)
		self.assertEqual(alice.unlocked_units.count(), 6)
		self.assertContains(
			self.post("inquiry", alice.pk, data={
				'unit': units[19].pk,
				"action_type": "UNLOCK",
			}), "Petition submitted, wait for it!"
		)
		self.assertEqual(alice.curriculum.count(), 6)
		self.assertEqual(alice.unlocked_units.count(), 6)

		self.login(firefly)
		for i in range(6, 10):
			self.assertContains(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "UNLOCK",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 10)
		self.assertEqual(alice.unlocked_units.count(), 10)

		self.login(alice)
		for i in range(11, 14):
			self.assertContains(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "UNLOCK",
				}), "more than 9 unfinished"
			)
		self.assertEqual(alice.curriculum.count(), 10)
		self.assertEqual(alice.unlocked_units.count(), 10)

		for i in range(15, 18):
			self.assertContains(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "APPEND",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 13)
		self.assertEqual(alice.unlocked_units.count(), 10)

		self.assertContains(
			self.post("inquiry", alice.pk, data={
				"unit": units[19].pk,
				"action_type": "DROP"
			}), "abnormally large"
		)

		self.login(firefly)
		for i in range(5, 14):
			self.assertContains(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "DROP",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 8)
		self.assertEqual(alice.unlocked_units.count(), 5)

		self.assertContains(
			self.post("inquiry", alice.pk, data={
				'unit': units[5].pk,
				"action_type": "UNLOCK",
			}), "Petition automatically approved"
		)
		self.assertEqual(alice.curriculum.count(), 9)
		self.assertEqual(alice.unlocked_units.count(), 6)

	def test_create_student(self):
		container = RegistrationContainerFactory.create(num_preps=2)

		StudentRegistrationFactory.create(track='A', container=container)
		StudentRegistrationFactory.create(track='B', container=container)
		self.assertEqual(build_students(StudentRegistration.objects.all()), 2)
		alice = Student.objects.get(track='A')
		self.assertEqual(alice.invoice.total_owed, 1824)
		bob = Student.objects.get(track='B')
		self.assertEqual(bob.invoice.total_owed, 1152)

		container.num_preps = 1
		container.save()
		StudentRegistrationFactory.create(track='C', container=container)
		self.assertEqual(build_students(StudentRegistration.objects.all()), 1)
		carol = Student.objects.get(track='C')
		self.assertEqual(carol.invoice.total_owed, 240)


# TODO tests for reg
# TODO tests for update profile
