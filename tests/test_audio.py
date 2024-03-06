import unittest
import logging
import sys

sys.path.append("../")
from backend.audio import Audio
from backend.bcm2835audiodriver import Bcm2835AudioDriver
from backend.usbaudiodriver import UsbAudioDriver
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


class TestAudio(unittest.TestCase):
    def setUp(self):
        self.session = session.TestSession(self)
        logging.basicConfig(
            level=LOG_LEVEL,
            format=u"%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s",
        )

    def tearDown(self):
        self.session.clean()

    def init_session(self, bootstrap={}):
        # force cleep_filesystem
        if "cleep_filesystem" not in bootstrap:
            cleep_filesystem = MagicMock()
            cleep_filesystem.open.return_value.read.return_value = "dtparam=audio=on"
            bootstrap["cleep_filesystem"] = cleep_filesystem

        self.module = self.session.setup(Audio, bootstrap=bootstrap, mock_on_start=False, mock_on_stop=False)
        mock_command = self.session.make_mock_command("restart_cleep")
        self.session.add_mock_command(mock_command)
        self.session.start_module(self.module)

    def test_init(self):
        self.init_session()
        self.assertIsNotNone(self.module.bcm2835_driver)
        self.assertTrue(isinstance(self.module.bcm2835_driver, Bcm2835AudioDriver))

    @patch("backend.audio.Tools")
    def test_init_no_audio_on_device(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": False}
        drivers_mock = Mock()
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )

        self.assertFalse(drivers_mock.get_drivers.called)

    def test_init_configured_driver_not_available(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = False
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [None, default_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )

    def test_init_driver_disabled(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = True
        default_driver.is_enabled.return_value = False
        default_driver.enable.return_value = False
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [None, default_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )

    def test_init_no_driver_available(self):
        default_driver = Mock()
        default_driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )

    def test_get_module_config(self):
        self.init_session()
        conf = self.module.get_module_config()
        logging.debug("Conf: %s" % conf)

        self.assertTrue("devices" in conf)
        self.assertTrue("playback" in conf["devices"])
        self.assertTrue("capture" in conf["devices"])
        self.assertTrue("volumes" in conf)
        self.assertTrue("playback" in conf["volumes"])
        self.assertTrue("capture" in conf["volumes"])

        self.assertEqual(
            conf["devices"]["playback"][0]["label"], "Raspberry pi soundcard"
        )
        # breaks tests during CI (no audio)
        # self.assertEqual(conf['devices']['playback'][0]['enabled'], True)
        # self.assertEqual(conf['devices']['playback'][0]['installed'], True)
        # self.assertEqual(conf['devices']['playback'][0]['device']['deviceid'], 0)
        # self.assertEqual(conf['devices']['playback'][0]['device']['playback'], True)
        # self.assertTrue(conf['devices']['playback'][0]['device']['cardname'].startswith('bcm2835'))
        # self.assertEqual(conf['devices']['playback'][0]['device']['capture'], False)
        # self.assertEqual(conf['devices']['playback'][0]['device']['cardid'], 0)

        # self.assertTrue(isinstance(conf['volumes']['playback'], int))
        # self.assertIsNone(conf['volumes']['capture'])

    def test_get_module_config_error_loading_driver(self):
        bad_driver = Mock()
        bad_driver.get_device_infos.side_effect = Exception("Test exception")
        good_driver = Mock()
        good_driver.get_device_infos.return_value = {
            "playback": "playback-device",
            "capture": "capture-device",
        }
        good_driver.get_card_name.return_value = "good card name"
        good_driver.is_enabled.return_value = True
        good_driver.is_installed.return_value = True
        good_driver.get_volumes.return_value = "volumes"
        drivers_mock = Mock()
        drivers_mock.get_drivers.return_value = {"bad": bad_driver, "good": good_driver}
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )

        conf = self.module.get_module_config()
        logging.debug("Conf: %s", conf)

        self.assertDictEqual(
            conf,
            {
                "devices": {
                    "playback": [
                        {
                            "name": "good card name",
                            "label": "good",
                            "device": {
                                "playback": "playback-device",
                                "capture": "capture-device",
                            },
                            "enabled": True,
                            "installed": True,
                        }
                    ],
                    "capture": [
                        {
                            "name": "good card name",
                            "label": "good",
                            "device": {
                                "playback": "playback-device",
                                "capture": "capture-device",
                            },
                            "enabled": True,
                            "installed": True,
                        }
                    ],
                },
                "volumes": "volumes",
            },
        )

    @patch("backend.audio.Tools")
    def test_select_device(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock(name="olddriver")
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock(name="newdriver")
        # add mock class variable
        attrs = {"name": "dummydriver"}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="selecteddriver")
        self.module._set_config_field = Mock()

        self.module.select_device("dummydriver")

        self.assertTrue(old_driver.disable.called)
        self.assertTrue(new_driver.enable.called)
        self.module._set_config_field.assert_called_with("driver", "dummydriver")

    @patch("backend.audio.Tools")
    def test_select_device_fallback_old_driver_if_error(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {"name": "dummydriver"}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = False
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="selecteddriver")
        self.module._set_config_field = Mock()

        with self.assertRaises(CommandError) as cm:
            self.module.select_device("dummydriver")
        self.assertEqual(str(cm.exception), "Unable to enable selected device")

    def test_select_device_invalid_parameters(self):
        self.init_session()

        with self.assertRaises(MissingParameter) as cm:
            self.module.select_device(None)
        self.assertEqual(str(cm.exception), 'Parameter "driver_name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.select_device("")
        self.assertEqual(
            str(cm.exception), 'Parameter "driver_name" is invalid (specified="")'
        )

    @patch("backend.audio.Tools")
    def test_select_device_unknown_new_driver(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock()
        # add mock class variable
        attrs = {"name": "dummydriver"}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, None]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="selecteddriver")
        self.module._set_config_field = Mock()

        with self.assertRaises(InvalidParameter) as cm:
            self.module.select_device("dummydriver")
        self.assertEqual(str(cm.exception), "Specified driver does not exist")

    @patch("backend.audio.Tools")
    def test_select_device_new_driver_not_installed(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock(name="olddriver")
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        new_driver = Mock(name="newdriver")
        # add mock class variable
        attrs = {"name": "dummydriver"}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = False
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="drivername")
        self.module._set_config_field = Mock()

        with self.assertRaises(InvalidParameter) as cm:
            self.module.select_device("dummydriver")
        self.assertEqual(
            str(cm.exception),
            "Can't selected device because its driver seems not to be installed",
        )

    @patch("backend.audio.Tools")
    def test_select_device_unable_to_disable_old_driver(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock(name="olddriver")
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = False
        new_driver = Mock(name="newdriver")
        # add mock class variable
        attrs = {"name": "dummydriver"}
        new_driver.configure_mock(**attrs)
        new_driver.is_installed.return_value = True
        new_driver.enable.return_value = True
        new_driver.is_card_enabled.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.side_effect = [old_driver, old_driver, new_driver]
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="selecteddriver")
        self.module._set_config_field = Mock()

        with self.assertRaises(CommandError) as cm:
            self.module.select_device("dummydriver")
        self.assertEqual(str(cm.exception), "Unable to disable current driver")

    def test_set_volumes(self):
        driver = Mock()
        driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = driver
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="dummydriver")

        self.module.set_volumes(12, 34)

        driver.set_volumes.assert_called_with(12, 34)

    @patch("backend.audio.Tools")
    def test_set_volumes_invalid_parameters(self, mock_tools):
        mock_tools.raspberry_pi_infos.return_value = {"audio": True}
        old_driver = Mock()
        old_driver.is_installed.return_value = True
        old_driver.disable.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = old_driver
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="selecteddriver")
        self.init_session()

        with self.assertRaises(MissingParameter) as cm:
            self.module.set_volumes(None, 12)
        self.assertEqual(str(cm.exception), 'Parameter "volume" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(12, "12")
        self.assertEqual(str(cm.exception), 'Parameter "capture" must be of type "int"')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(-12, 12)
        self.assertEqual(
            str(cm.exception), 'Parameter "playback" must be 0<=playback<=100'
        )
        with self.assertRaises(InvalidParameter) as cm:
            self.module.set_volumes(12, 102)
        self.assertEqual(
            str(cm.exception), 'Parameter "capture" must be 0<=capture<=100'
        )

    def test_set_volumes_no_driver_selected(self):
        driver = Mock()
        driver.is_installed.return_value = True
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value=None)

        volumes = self.module.set_volumes(12, 34)
        logging.debug("Volumes: %s" % volumes)

        self.assertEqual(volumes, {"playback": None, "capture": None})
        self.assertFalse(driver.set_volumes.called)

    def test_set_volumes_no_driver_found(self):
        drivers_mock = Mock()
        drivers_mock.get_driver.return_value = None
        self.init_session(
            bootstrap={
                "drivers": drivers_mock,
            }
        )
        self.module._get_config_field = Mock(return_value="dummydriver")

        volumes = self.module.set_volumes(12, 34)
        logging.debug("Volumes: %s" % volumes)

        self.assertEqual(volumes, {"playback": None, "capture": None})

    @patch("backend.audio.Alsa")
    def test_test_playing(self, mock_alsa):
        self.init_session()
        self.module.test_playing()

        time.sleep(1.0)
        self.assertTrue(mock_alsa.return_value.play_sound.called)

    @patch("backend.audio.Alsa")
    def test_test_playing_failed(self, mock_alsa):
        mock_alsa.return_value.play_sound.return_value = False
        self.init_session()
        self.module.test_playing()

        time.sleep(1.0)
        self.assertTrue(mock_alsa.return_value.play_sound.called)

    @patch("backend.audio.Alsa")
    def test_test_recording(self, mock_alsa):
        self.init_session()
        self.module.test_recording()

        self.assertTrue(mock_alsa.return_value.record_sound.called)

    @patch("backend.audio.Alsa")
    def test_test_recording_failed(self, mock_alsa):
        mock_alsa.return_value.play_sound.return_value = False
        self.init_session()
        self.module.test_recording()

        self.assertTrue(mock_alsa.return_value.record_sound.called)

    def test_resource_acquired(self):
        self.init_session()
        self.module._resource_acquired("dummy.resource")


if __name__ == "__main__":
    # coverage run --omit="*lib/python*/*","test_*" --concurrency=thread test_audio.py; coverage report -m -i
    unittest.main()
