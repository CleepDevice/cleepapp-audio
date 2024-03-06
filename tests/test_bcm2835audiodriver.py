import unittest
import logging
import sys

sys.path.append("../")
from backend.bcm2835audiodriver import Bcm2835AudioDriver
from cleep.exception import (
    InvalidParameter,
    MissingParameter,
    CommandError,
    Unauthorized,
)
from cleep.libs.tests import session, lib
from cleep.libs.tests.common import get_log_level
import os
import time
from unittest.mock import Mock, MagicMock, patch

LOG_LEVEL = get_log_level()


class TestBcm2835AudioDriver(unittest.TestCase):
    def setUp(self):
        self.session = lib.TestLib()
        logging.basicConfig(
            level=LOG_LEVEL,
            format=u"%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s",
        )

    def tearDown(self):
        pass

    def init_session(self):
        self.fs = Mock()
        self.driver = Bcm2835AudioDriver()
        self.driver.cleep_filesystem = Mock()
        self.driver._on_registered()

    def test__get_card_name(self):
        self.driver = Bcm2835AudioDriver()
        self.driver.cleep_filesystem = Mock()
        devices_names = [
            {
                "card_name": "Headphones",
                "card_desc": "bcm2835 Headphones",
                "device_name": "Headphones",
                "device_desc": "bcm2835 Headphones",
            },
        ]

        result = self.driver._get_card_name(devices_names)

        self.assertEqual(result, "Headphones")

    def test__get_card_name_card_not_found(self):
        self.driver = Bcm2835AudioDriver()
        self.driver.cleep_filesystem = Mock()
        devices_names = [
            {
                "card_name": "Headphones",
                "card_desc": "Headphones",
                "device_name": "Headphones",
                "device_desc": "Headphones",
            },
        ]

        result = self.driver._get_card_name(devices_names)

        self.assertIsNone(result)

    def test_get_card_capabilities(self):
        self.init_session()

        (playback, capture) = self.driver.get_card_capabilities()

        self.assertTrue(playback)
        self.assertFalse(capture)

    @patch("backend.bcm2835audiodriver.Tools")
    @patch("backend.bcm2835audiodriver.ConfigTxt")
    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test__install(self, mock_asound, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        self.init_session()
        self.driver._install()
        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_configtxt.return_value.enable_audio.called)

    @patch("backend.bcm2835audiodriver.Tools")
    @patch("backend.bcm2835audiodriver.ConfigTxt")
    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test__install_enable_audio_failed(
        self, mock_asound, mock_configtxt, mock_tools
    ):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        mock_configtxt.return_value.enable_audio.return_value = False
        self.init_session()

        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), "Error enabling raspberry pi audio")
        self.assertTrue(mock_asound.return_value.delete.called)

    @patch("backend.bcm2835audiodriver.Tools")
    def test__install_with_no_audio_supported(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": False}
        self.init_session()

        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), "Raspberry pi has no onboard audio device")

    @patch("backend.bcm2835audiodriver.Tools")
    @patch("backend.bcm2835audiodriver.ConfigTxt")
    def test__uninstall(self, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        self.init_session()
        self.driver._uninstall()
        self.assertTrue(mock_configtxt.return_value.disable_audio.called)

    @patch("backend.bcm2835audiodriver.Tools")
    @patch("backend.bcm2835audiodriver.ConfigTxt")
    def test__uninstall_disable_audio_failed(self, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        mock_configtxt.return_value.disable_audio.return_value = False
        self.init_session()

        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), "Error disabling raspberry pi audio")

    @patch("backend.bcm2835audiodriver.Tools")
    def test__uninstall_with_no_audio_supported(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": False}
        self.init_session()

        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), "Raspberry pi has no onboard audio device")

    def test_is_intalled(self):
        self.init_session()
        self.driver.configtxt.is_audio_enabled = Mock(return_value=True)

        self.assertTrue(self.driver.is_installed())

    def test_is_intalled_not_installed(self):
        self.init_session()
        self.driver.configtxt.is_audio_enabled = Mock(return_value=False)

        self.assertFalse(self.driver.is_installed())

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test_enable(self, mock_asound):
        self.init_session()
        mock_alsa = MagicMock()
        self.driver.alsa = mock_alsa
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))
        self.driver.get_control_numid = Mock(return_value=1)

        self.assertTrue(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertTrue(mock_alsa.amixer_control.called)
        self.assertTrue(mock_alsa.save.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    @patch("backend.bcm2835audiodriver.Alsa")
    def test_enable_no_card_infos(self, mock_alsa, mock_asound):
        self.init_session()
        self.driver.get_cardid_deviceid = Mock(return_value=(None, None))

        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertFalse(mock_asound.return_value.save_default_file.called)
        self.assertFalse(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_alsa.return_value.save.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    @patch("backend.bcm2835audiodriver.Alsa")
    def test_enable_alsa_save_default_file_failed(self, mock_alsa, mock_asound):
        mock_asound.return_value.save_default_file.return_value = False
        self.init_session()
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))

        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertFalse(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_alsa.return_value.save.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test_enable_alsa_amixer_control_failed(self, mock_asound):
        self.init_session()
        mock_alsa = MagicMock()
        mock_alsa.amixer_control.return_value = False
        self.driver.alsa = mock_alsa
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))
        self.driver.get_control_numid = Mock(return_value=1)

        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertTrue(mock_alsa.amixer_control.called)
        self.assertFalse(mock_alsa.save.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test_disable(self, mock_asound):
        self.init_session()

        self.assertTrue(self.driver.disable())

        self.assertTrue(mock_asound.return_value.delete.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test_disable_asound_delete_failed(self, mock_asound):
        mock_asound.return_value.delete.return_value = False
        self.init_session()

        self.assertFalse(self.driver.disable())

        self.assertTrue(mock_asound.return_value.delete.called)

    @patch("backend.bcm2835audiodriver.EtcAsoundConf")
    def test_is_enabled(self, mock_asound):
        self.init_session()

        self.driver.is_card_enabled = Mock(return_value=True)
        mock_asound.return_value.exists.return_value = True
        self.assertTrue(self.driver.is_enabled())

        self.driver.is_card_enabled = Mock(return_value=False)
        mock_asound.return_value.exists.return_value = True
        self.assertFalse(self.driver.is_enabled())

        self.driver.is_card_enabled = Mock(return_value=True)
        mock_asound.return_value.exists.return_value = False
        self.assertFalse(self.driver.is_enabled())

    def test__set_volumes_controls(self):
        self.init_session()
        self.driver.alsa = Mock()
        self.driver.alsa.get_simple_controls.return_value = ["PCM"]
        self.driver.get_control_numid = Mock(return_value=3)

        self.driver._set_volumes_controls()

        self.assertEqual(self.driver.volume_control, "PCM")
        self.assertEqual(self.driver.volume_control_numid, 3)

    def test_get_volumes(self):
        self.init_session()
        mock_alsa = Mock()
        mock_alsa.get_volume.return_value = 66
        self.driver.alsa = mock_alsa

        vols = self.driver.get_volumes()
        self.assertEqual(vols, {"playback": 66, "capture": None})

    def test_set_volumes(self):
        self.init_session()
        mock_alsa = Mock()
        mock_alsa.set_volume.return_value = 99
        self.driver.alsa = mock_alsa

        vols = self.driver.set_volumes(playback=12, capture=34)
        self.assertEqual(vols, {"playback": 99, "capture": None})

    def test_require_reboot(self):
        self.init_session()

        self.assertFalse(self.driver.require_reboot())


if __name__ == "__main__":
    # coverage run --omit="*lib/python*/*","test_*" --concurrency=thread test_bcm2835audiodriver.py; coverage report -m -i
    unittest.main()
