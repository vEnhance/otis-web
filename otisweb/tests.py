from evans_django_tools.testsuite import EvanTestCase


class OTISRegistrationTest(EvanTestCase):

    def test_reg(self):
        self.assertGet20X('account_signup')
        self.assertPost20X(
            'account_signup',
            data={
                'username': 'alice',
                'email': 'alice@evanchen.cc',
                'first_name': 'Alice',
                'last_name': 'Aardvark',
                'password1': 'this_password_isnt_a_puzzle_but_nice_try',
                'password2': 'this_password_isnt_a_puzzle_but_nice_try',
            },
            follow=True)
        self.login('alice')
