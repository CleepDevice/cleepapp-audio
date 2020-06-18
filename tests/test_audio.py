import unittest
import logging
import sys
sys.path.append('../')
from backend.audio import Audio
from backend.bcm2835audiodriver import Bcm2835AudioDriver
from cleep.exception import InvalidParameter, MissingParameter, CommandError, Unauthorized
from cleep.libs.tests import session, lib
import os
import time
from mock import Mock, MagicMock, patch

class TestAudio(unittest.TestCase):

    def setUp(self):
        self.session = session.TestSession()
        logging.basicConfig(level=logging.CRITICAL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')

    def tearDown(self):
        self.session.clean()

    def init_context(self, bootstrap={}):
        self.module = self.session.setup(Audio, bootstrap=bootstrap)

    def test_init(self):
        self.init_context()
        self.assertIsNotNone(self.module.bcm2835_driver)
        self.assertTrue(isinstance(self.module.bcm2835_driver, Bcm2835AudioDriver))

    @patch('backend.audio.Tools')
    def test_init_no_audio_on_device(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': False }
        self.init_context()

    def test_init_configured_driver_not_available(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = False
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [None, default_driver]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })

    def test_init_driver_disabled(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = True
        default_driver.is_enabled.return_value = False
        default_driver.enable.return_value = False
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [None, default_driver]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })

    def test_init_no_driver_available(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })

    def test_get_module_config(self):
        self.init_context()
        conf = self.module.get_module_config()
        logging.debug('Conf: %s' % conf)

        self.assertTrue('devices' in conf)
        self.assertTrue('playback' in conf['devices'])
        self.assertTrue('capture' in conf['devices'])
        self.assertTrue('volumes' in conf)
        self.assertTrue('playback' in conf['volumes'])
        self.assertTrue('capture' in conf['volumes'])
        
        self.assertEqual(conf['devices']['playback'][0]['label'], 'Raspberry pi soundcard')
        self.assertEqual(conf['devices']['playback'][0]['enabled'], True)
        self.assertEqual(conf['devices']['playback'][0]['installed'], True)
        self.assertEqual(conf['devices']['playback'][0]['device']['deviceid'], 0)
        self.assertEqual(conf['devices']['playback'][0]['device']['playback'], True)
        self.assertEqual(conf['devices']['playback'][0]['device']['cardname'], 'bcm2835 ALSA')
        self.assertEqual(conf['devices']['playback'][0]['device']['capture'], False)
        self.assertEqual(conf['devices']['playback'][0]['device']['cardid'], 0)

        self.assertTrue(isinstance(conf['volumes']['playback'], int))
        self.assertIsNone(conf['volumes']['capture'])

    def test_select_device(self):
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {'name': 'dummydriver'}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._set_config_field = Mock()

        self.module.select_device('dummydriver')
        self.assertTrue(old_driver.disable.called)
        self.assertTrue(new_driver.enable.called)
        self.module._set_config_field.assert_called_with('driver', 'dummydriver')

    def test_select_device_fallback_old_driver_if_error(self):
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {'name': 'dummydriver'}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = False
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._set_config_field = Mock()

        with self.assertRaises(CommandError) as cm:
            self.module.select_device('dummydriver')
        self.assertEqual(str(cm.exception), 'Unable to enable selected device')

    def test_select_device_invalid_parameters(self):
        self.init_context()

        with self.assertRaises(MissingParameter) as cm:
            self.module.select_device(None)
        self.assertEqual(str(cm.exception), 'Parameter "driver_name" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.select_device('')
        self.assertEqual(str(cm.exception), 'Parameter "driver_name" is missing')

    def test_select_device_unknown_new_driver(self):
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {'name': 'dummydriver'}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, None]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._set_config_field = Mock()

        with self.assertRaises(InvalidParameter) as cm:
            self.module.select_device('dummydriver')
        self.assertEqual(str(cm.exception), 'Specified driver does not exist')

    def test_select_device_new_driver_not_installed(self):
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {'name': 'dummydriver'}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = False
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._set_config_field = Mock()

        with self.assertRaises(InvalidParameter) as cm:
            self.module.select_device('dummydriver')
        self.assertEqual(str(cm.exception), 'Can\'t selected device because its driver seems not to be installed')

    def test_set_volumes(self):
        driver = Mock()
        driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = driver
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._get_config_field = Mock(return_value='dummydriver')

        self.module.set_volumes(12, 34)

        driver.set_volumes.assert_called_with(12, 34)

    def test_set_volumes_invalid_parameters(self):
        self.init_context()

        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(None, 12)
        self.assertEqual(str(cm.exception), 'Parameter "playback" has invalid type')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(12, '12')
        self.assertEqual(str(cm.exception), 'Parameter "capture" has invalid type')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(-12, 12)
        self.assertEqual(str(cm.exception), 'Parameter "playback" must be a valid percentage')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(12, 102)
        self.assertEqual(str(cm.exception), 'Parameter "capture" must be a valid percentage')

    def test_set_volumes_no_driver_selected(self):
        driver = Mock()
        driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._get_config_field = Mock(return_value=None)

        volumes = self.module.set_volumes(12, 34)
        logging.debug('Volumes: %s' % volumes)

        self.assertEqual(volumes, { 'playback': None, 'capture': None })
        self.assertFalse(driver.set_volumes.called)

    def test_set_volumes_no_driver_found(self):
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_context(bootstrap={
            'drivers': drivers_mock,
        })
        self.module._get_config_field = Mock(return_value='dummydriver')

        volumes = self.module.set_volumes(12, 34)
        logging.debug('Volumes: %s' % volumes)

        self.assertEqual(volumes, { 'playback': None, 'capture': None })

    @patch('backend.audio.Alsa')
    def test_test_playing(self, mock_alsa):
        self.init_context()
        self.module.test_playing()

        time.sleep(1.0)
        self.assertTrue(mock_alsa.return_value.play_sound.called)

    @patch('backend.audio.Alsa')
    def test_test_playing_failed(self, mock_alsa):
        mock_alsa.return_value.play_sound.return_value = False
        self.init_context()
        self.module.test_playing()

        time.sleep(1.0)
        self.assertTrue(mock_alsa.return_value.play_sound.called)

    @patch('backend.audio.Alsa')
    def test_test_recording(self, mock_alsa):
        self.init_context()
        self.module.test_recording()

        self.assertTrue(mock_alsa.return_value.record_sound.called)

    @patch('backend.audio.Alsa')
    def test_test_recording_failed(self, mock_alsa):
        mock_alsa.return_value.play_sound.return_value = False
        self.init_context()
        self.module.test_recording()

        self.assertTrue(mock_alsa.return_value.record_sound.called)

    def test_resource_acquired(self):
        self.init_context()
        self.module._resource_acquired('dummy.resource')





class TestBcm2835AudioDriver(unittest.TestCase):
    def setUp(self):
        self.session = lib.TestLib()
        logging.basicConfig(level=logging.CRITICAL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')

    def tearDown(self):
        pass

    def init_context(self):
        self.fs = Mock()
        self.driver = Bcm2835AudioDriver(self.fs)

    @patch('backend.bcm2835audiodriver.Tools')
    @patch('backend.bcm2835audiodriver.ConfigTxt')
    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    def test_install(self, mock_asound, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': True }
        self.init_context()
        self.driver._install()
        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_configtxt.return_value.enable_audio.called)

    @patch('backend.bcm2835audiodriver.Tools')
    @patch('backend.bcm2835audiodriver.ConfigTxt')
    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    def test_install_enable_audio_failed(self, mock_asound, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': True }
        mock_configtxt.return_value.enable_audio.return_value = False
        self.init_context()

        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), 'Error enabling raspberry pi audio')
        self.assertTrue(mock_asound.return_value.delete.called)

    @patch('backend.bcm2835audiodriver.Tools')
    def test_install_with_no_audio_supported(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': False }
        self.init_context()

        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), 'Raspberry pi has no onboard audio device')

    @patch('backend.bcm2835audiodriver.Tools')
    @patch('backend.bcm2835audiodriver.ConfigTxt')
    def test_uninstall(self, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': True }
        self.init_context()
        self.driver._uninstall()
        self.assertTrue(mock_configtxt.return_value.disable_audio.called)

    @patch('backend.bcm2835audiodriver.Tools')
    @patch('backend.bcm2835audiodriver.ConfigTxt')
    def test_uninstall_disable_audio_failed(self, mock_configtxt, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': True }
        mock_configtxt.return_value.disable_audio.return_value = False
        self.init_context()

        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), 'Error disabling raspberry pi audio')
        
    @patch('backend.bcm2835audiodriver.Tools')
    def test_uninstall_with_no_audio_supported(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = { 'audio': False }
        self.init_context()

        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), 'Raspberry pi has no onboard audio device')

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_enable(self, mock_alsa, mock_asound):
        self.init_context()
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))
    
        self.assertTrue(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertTrue(mock_alsa.return_value.amixer_control.called)
        self.assertTrue(mock_alsa.return_value.save.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_enable_no_card_infos(self, mock_alsa, mock_asound):
        self.init_context()
        self.driver.get_cardid_deviceid = Mock(return_value=(None, None))
    
        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertFalse(mock_asound.return_value.save_default_file.called)
        self.assertFalse(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_alsa.return_value.save.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_enable_alsa_save_default_file_failed(self, mock_alsa, mock_asound):
        mock_asound.return_value.save_default_file.return_value = False
        self.init_context()
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))
    
        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertFalse(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_alsa.return_value.save.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_enable_alsa_amixer_control_failed(self, mock_alsa, mock_asound):
        mock_alsa.return_value.amixer_control.return_value = False
        self.init_context()
        self.driver.get_cardid_deviceid = Mock(return_value=(0, 0))
    
        self.assertFalse(self.driver.enable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_asound.return_value.save_default_file.called)
        self.assertTrue(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_alsa.return_value.save.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_disable(self, mock_alsa, mock_asound):
        self.init_context()
    
        self.assertTrue(self.driver.disable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_alsa.return_value.amixer_control.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_disable_alsa_amixer_control_failed(self, mock_alsa, mock_asound):
        mock_alsa.return_value.amixer_control.return_value = False
        self.init_context()
    
        self.assertFalse(self.driver.disable())

        self.assertTrue(mock_alsa.return_value.amixer_control.called)
        self.assertFalse(mock_asound.return_value.delete.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    @patch('backend.bcm2835audiodriver.Alsa')
    def test_disable_asound_delete_failed(self, mock_alsa, mock_asound):
        mock_asound.return_value.delete.return_value = False
        self.init_context()
    
        self.assertFalse(self.driver.disable())

        self.assertTrue(mock_asound.return_value.delete.called)
        self.assertTrue(mock_alsa.return_value.amixer_control.called)

    @patch('backend.bcm2835audiodriver.EtcAsoundConf')
    def test_is_enabled(self, mock_asound):
        self.init_context()

        self.driver.is_card_enabled = Mock(return_value=True)
        mock_asound.return_value.exists.return_value = True
        self.assertTrue(self.driver.is_enabled())

        self.driver.is_card_enabled = Mock(return_value=False)
        mock_asound.return_value.exists.return_value = True
        self.assertFalse(self.driver.is_enabled())

        self.driver.is_card_enabled = Mock(return_value=True)
        mock_asound.return_value.exists.return_value = False
        self.assertFalse(self.driver.is_enabled())

    @patch('backend.bcm2835audiodriver.Alsa')
    def test_get_volumes(self, mock_alsa):
        self.init_context()

        mock_alsa.return_value.get_volume.return_value = 66
        vols =  self.driver.get_volumes()
        self.assertEqual(vols, { 'playback': 66, 'capture': None })

    @patch('backend.bcm2835audiodriver.Alsa')
    def test_set_volumes(self, mock_alsa):
        self.init_context()

        mock_alsa.return_value.set_volume.return_value = 99
        vols = self.driver.set_volumes(playback=12, capture=34)
        self.assertEqual(vols, { 'playback': 99, 'capture': None })



if __name__ == "__main__":
    # coverage run --omit="*lib/python*/*","test_*" --concurrency=thread test_audio.py; coverage report -m -i
    unittest.main()
    
