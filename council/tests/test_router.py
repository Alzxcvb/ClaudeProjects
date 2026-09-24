import unittest

from council.router import route


class RouterTest(unittest.TestCase):
    def test_route_returns_council(self):
        self.assertEqual(route("any question"), "council")
        self.assertEqual(route(""), "council")
        self.assertEqual(route("will X happen by 2027?"), "council")


if __name__ == "__main__":
    unittest.main()
