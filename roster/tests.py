from core.factories import UnitFactory, UnitGroupFactory, UserFactory  # NOQA
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from evans_django_tools.testsuite import EvanTestCase

from roster.factories import AssistantFactory, InvoiceFactory, RegistrationContainerFactory, StudentFactory, StudentRegistrationFactory  # NOQA
from roster.models import Student, StudentRegistration

from .admin import build_students


class RosterTest(EvanTestCase):
	def test_curriculum(self):
		staff = AssistantFactory.create()
		alice = StudentFactory.create(assistant=staff)

		unitgroups = UnitGroupFactory.create_batch(4)
		for unitgroup in unitgroups:
			for letter in 'BDZ':
				UnitFactory.create(code=letter + unitgroup.subject[0] + 'W', group=unitgroup)

		self.login(alice)
		self.assertHas(self.get('currshow', alice.pk), text="you are not an instructor")

		self.login(staff)
		self.assertNotHas(self.get('currshow', alice.pk), text="you are not an instructor")

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
		self.assertHas(
			self.post('finalize', alice.pk, data={'submit': True}, follow=True),
			'You should select some units'
		)
		units = UnitFactory.create_batch(20)
		alice.curriculum.set(units)
		self.assertHas(
			self.post('finalize', alice.pk, data={}, follow=True),
			'Your curriculum has been finalized!'
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
		response = self.get('invoice', follow=True)
		self.assertHas(response, "752.00")
		checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
		self.assertEqual(len(checksum), 36)
		self.assertHas(response, checksum)

	def test_master_schedule(self):
		alice = StudentFactory.create(user__first_name="Adalhaidis")
		units = UnitFactory.create_batch(10)
		alice.curriculum.set(units[0:8])
		self.login(UserFactory.create(is_staff=True))
		self.assertHas(self.get('master-schedule'), text=alice.user.first_name, count=8)

	def test_update_invoice(self):
		firefly = AssistantFactory.create()
		alice = StudentFactory.create(assistant=firefly)
		invoice = InvoiceFactory.create(student=alice)
		self.login(firefly)
		self.assertGet20X('edit-invoice', alice.pk)
		self.assertPostRedirects(
			self.url('invoice', invoice.pk),
			'edit-invoice',
			invoice.pk,
			data={
				'preps_taught': 2,
				'hours_taught': 8.4,
				'adjustment': 0,
				'extras': 0,
				'total_paid': 1152,
				'forgive': False
			},
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
			self.assertHas(resp, "Petition automatically approved")
		self.assertEqual(alice.curriculum.count(), 6)
		self.assertEqual(alice.unlocked_units.count(), 6)
		self.assertHas(
			self.post("inquiry", alice.pk, data={
				'unit': units[19].pk,
				"action_type": "UNLOCK",
			}), "Petition submitted, wait for it!"
		)
		self.assertEqual(alice.curriculum.count(), 6)
		self.assertEqual(alice.unlocked_units.count(), 6)

		self.login(firefly)
		for i in range(6, 10):
			self.assertHas(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "UNLOCK",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 10)
		self.assertEqual(alice.unlocked_units.count(), 10)

		self.login(alice)
		for i in range(11, 14):
			self.assertHas(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "UNLOCK",
				}), "more than 9 unfinished"
			)
		self.assertEqual(alice.curriculum.count(), 10)
		self.assertEqual(alice.unlocked_units.count(), 10)

		for i in range(15, 18):
			self.assertHas(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "APPEND",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 13)
		self.assertEqual(alice.unlocked_units.count(), 10)

		self.assertHas(
			self.post("inquiry", alice.pk, data={
				"unit": units[19].pk,
				"action_type": "DROP"
			}), "abnormally large"
		)

		self.login(firefly)
		for i in range(5, 14):
			self.assertHas(
				self.post("inquiry", alice.pk, data={
					'unit': units[i].pk,
					"action_type": "DROP",
				}), "Petition automatically approved"
			)
		self.assertEqual(alice.curriculum.count(), 8)
		self.assertEqual(alice.unlocked_units.count(), 5)

		self.assertHas(
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

	def test_student_assistant_list(self):
		for i in range(1, 6):
			asst = AssistantFactory.create(
				user__first_name=f"F{i}",
				user__last_name=f"L{i}",
				user__email=f"user{i}@evanchen.cc",
				shortname=f"Short{i}",
			)
			StudentFactory.create_batch(i * i, user__first_name="GoodKid", assistant=asst)
		StudentFactory.create(user__first_name="BadKid")
		staff = UserFactory.create(is_staff=True)
		self.login(staff)
		resp = self.assertGet20X('instructors')
		for i in range(1, 6):
			self.assertHas(resp, f'"F{i} L{i}"')
			self.assertHas(resp, f'user{i}@evanchen.cc')
		self.assertHas(resp, "GoodKid", count=1 + 4 + 9 + 16 + 25)
		self.assertHas(resp, r'&lt;user5@evanchen.cc&gt;')
		self.assertNotHas(resp, "BadKid")
		self.assertNotHas(resp, "out of sync")  # only admins can see the sync button

		admin = UserFactory.create(is_staff=True, is_superuser=True)
		self.login(admin)
		resp = self.assertGet20X('instructors')
		self.assertHas(resp, "out of sync")

		group = Group.objects.get(name="Active Staff")
		qs: QuerySet[User] = group.user_set.all()  # type: ignore
		self.assertEqual(qs.count(), 0)

		resp = self.assertPostOK('instructors')
		self.assertEqual(qs.count(), 5)
		self.assertNotHas(resp, "out of sync")
		resp = self.assertGetOK('instructors')
		self.assertNotHas(resp, "out of sync")

		self.login(staff)
		self.assertPost40X('instructors')  # staff can't post


# TODO tests for reg
# TODO tests for update profile
