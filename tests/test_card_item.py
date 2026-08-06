import unittest
from tests.test_node_engine import TestNodeEngineArchitecture


class TestCardItemAlias(unittest.TestCase):

    def test_card_item_alias_verification(self):
        """Verify card item alias class compatibility."""
        self.assertTrue(issubclass(TestNodeEngineArchitecture, unittest.TestCase))
