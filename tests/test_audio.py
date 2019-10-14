import unittest
import logging
import sys
sys.path.append('../')
from backend.audio import Audio
from raspiot.utils import InvalidParameter, MissingParameter, CommandError, Unauthorized
from raspiot.libs.tests import session
import os
import time
from mock import Mock

class TestAudio(unittest.TestCase):

    def setUp(self):
        self.session = session.TestSession(logging.CRITICAL)
        _mod = Audio
        self.module = self.session.setup(_mod)

    def tearDown(self):
        self.session.clean()

if __name__ == "__main__":
    unittest.main()
    
