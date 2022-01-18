import unittest
import logging
import sys
sys.path.append('../')
from backend.usbaudiodriver import UsbAudioDriver
from cleep.exception import InvalidParameter, MissingParameter, CommandError, Unauthorized
from cleep.libs.tests import session, lib
import os
import time
from mock import Mock, MagicMock, patch

class TestUsbAudioDriver(unittest.TestCase):
    def setUp(self):
        self.session = lib.TestLib()
        logging.basicConfig(level=logging.FATAL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')

    def tearDown(self):
        pass

    def init_session(self, card_name='UACDemoV10'):
        self.driver = UsbAudioDriver()
        self.driver.cleep_filesystem = Mock()
        self.driver._get_card_name = Mock(return_value=card_name)

        self.driver._on_registered()

    def test__get_card_name(self):
        self.driver = UsbAudioDriver()
        self.driver.cleep_filesystem = Mock()
        devices_names = [
            { 'card_name': 'Headphones', 'card_desc': 'bcm2835 Headphones', 'device_name': 'Headphones', 'device_desc': 'bcm2835 Headphones' },
            { 'card_name': 'UACDemoV10', 'card_desc': 'UACDemoV1.0', 'device_name': 'USB Audio', 'device_desc': 'USB Audio' },
        ]

        result = self.driver._get_card_name(devices_names)

        self.assertEqual(result, 'UACDemoV10')

    def test__get_card_name_card_not_found(self):
        self.driver = UsbAudioDriver()
        self.driver.cleep_filesystem = Mock()
        devices_names = [
            { 'card_name': 'Headphones', 'card_desc': 'bcm2835 Headphones', 'device_name': 'Headphones', 'device_desc': 'bcm2835 Headphones' },
        ]

        result = self.driver._get_card_name(devices_names)

        self.assertIsNone(result)

    @patch('backend.usbaudiodriver.ConfigTxt')
    @patch('backend.usbaudiodriver.EtcAsoundConf')
    @patch('backend.usbaudiodriver.Console')
    def test__install(self, mock_console, mock_asound, mock_configtxt):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 0})
        mock_configtxt.return_value.enable_audio.return_value = True

        self.assertTrue(self.driver._install())

        mock_asound.return_value.delete.assert_called()
        mock_configtxt.return_value.enable_audio.assert_called()
        mock_console.return_value.command.assert_called()

    @patch('backend.usbaudiodriver.ConfigTxt')
    @patch('backend.usbaudiodriver.EtcAsoundConf')
    @patch('backend.usbaudiodriver.Console')
    def test__install_command_failed(self, mock_console, mock_asound, mock_configtxt):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 1})
        mock_configtxt.return_value.enable_audio.return_value = True

        self.assertFalse(self.driver._install())

    @patch('backend.usbaudiodriver.ConfigTxt')
    @patch('backend.usbaudiodriver.EtcAsoundConf')
    @patch('backend.usbaudiodriver.Console')
    def test__install_enable_audio_failed(self, mock_console, mock_asound, mock_configtxt):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 0})
        mock_configtxt.return_value.enable_audio.return_value = False

        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), 'Error enabling USB audio')

    @patch('backend.usbaudiodriver.Console')
    def test__uninstall(self, mock_console):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 0})

        self.assertTrue(self.driver._uninstall())

    @patch('backend.usbaudiodriver.Console')
    def test__uninstall_failed(self, mock_console):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 1})

        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), 'Unable to uninstall USB audio')

    @patch('backend.usbaudiodriver.Console')
    def test_is_intalled(self, mock_console):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 0})

        self.assertTrue(self.driver.is_installed())

    @patch('backend.usbaudiodriver.Console')
    def test_is_intalled_not_installed(self, mock_console):
        self.init_session()
        mock_console.return_value.command = Mock(return_value={'returncode': 1})

        self.assertFalse(self.driver.is_installed())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_enable(self, mock_asoundconf):
        self.init_session()
        self.driver.get_cardid_deviceid = Mock(return_value=(1,1))
        self.driver.alsa = Mock()

        self.driver.enable()

        mock_asoundconf.return_value.delete.assert_called()
        mock_asoundconf.return_value.save_default_file.assert_called_with(1,1)
        self.driver.alsa.save.assert_called()

    def test_enable_no_card_name(self):
        self.init_session(card_name=None)

        with self.assertRaises(Exception) as cm:
            self.driver.enable()
        self.assertEqual(str(cm.exception), 'No USB audio found. Please connect it before enabling it')

    def test_enable_invalid_cardid_deviceid(self):
        self.init_session()
        self.driver.get_cardid_deviceid = Mock(return_value=(None, None))

        self.assertFalse(self.driver.enable())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_enable_asoundconf_saving_failed(self, mock_asoundconf):
        mock_asoundconf.return_value.save_default_file.return_value = False
        self.init_session()
        self.driver.get_cardid_deviceid = Mock(return_value=(1,1))
        self.driver.alsa = Mock()

        self.assertFalse(self.driver.enable())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_disable(self, mock_asoundconf):
        mock_asoundconf.return_value.delete.return_value = True
        self.init_session()

        self.assertTrue(self.driver.disable())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_disable_asound_failed(self, mock_asoundconf):
        mock_asoundconf.return_value.delete.return_value = False
        self.init_session()

        self.assertFalse(self.driver.disable())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_is_enabled(self, mock_asoundconf):
        mock_asoundconf.return_value.exists.return_value = True
        self.init_session()
        self.driver.is_card_enabled = Mock(return_value=True)

        self.assertTrue(self.driver.is_enabled())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_is_enabled_asound_file_does_not_exist(self, mock_asoundconf):
        mock_asoundconf.return_value.exists.return_value = False
        self.init_session()
        self.driver.is_card_enabled = Mock(return_value=True)

        self.assertFalse(self.driver.is_enabled())

    @patch('backend.usbaudiodriver.EtcAsoundConf')
    def test_is_enabled_card_disabled(self, mock_asoundconf):
        mock_asoundconf.return_value.exists.return_value = True
        self.init_session()
        self.driver.is_card_enabled = Mock(return_value=False)

        self.assertFalse(self.driver.is_enabled())

    def test__set_volumes_controls(self):
        self.init_session()
        self.driver.alsa = Mock()
        self.driver.alsa.get_simple_controls.return_value = ['PCM']
        self.driver.get_control_numid = Mock(return_value=3)

        self.driver._set_volumes_controls()

        self.assertEqual(self.driver.volume_control, 'PCM')
        self.assertEqual(self.driver.volume_control_numid, 3)

    def test_get_volumes(self):
        self.init_session()
        self.driver.alsa = Mock()
        self.driver.alsa.get_volume.return_value = 12

        result = self.driver.get_volumes()

        self.assertDictEqual(result, {
            'playback': 12,
            'capture': None,
        })

    def test_set_volumes(self):
        self.init_session()
        self.driver.alsa = Mock()
        self.driver.alsa.set_volume.return_value = 34
        self.driver.volume_control = 'VOL_CTRL'

        result = self.driver.set_volumes(12,34)

        self.assertDictEqual(result, {
            'playback': 34,
            'capture': None,
        })
        self.driver.alsa.set_volume.assert_called_with('VOL_CTRL', self.driver.VOLUME_PATTERN, 12)

    def test_require_reboot(self):
        self.init_session()
        
        self.assertFalse(self.driver.require_reboot())


if __name__ == "__main__":
    # coverage run --omit="*lib/python*/*","test_*" --concurrency=thread test_audio.py; coverage report -m -i
    unittest.main()
    
